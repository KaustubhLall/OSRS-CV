import time
import pyautogui
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import json
from pynput import keyboard
import ast

# HotkeyManager Class
class HotkeyManager:
    def __init__(self, app):
        self.app = app
        self.hotkeys = {}
        self.listener = None
        self.current_keys = set()
        self.pressed_hotkeys = set()  # Set to keep track of hotkeys that have been activated

    def register_hotkeys(self, macros):
        # Stop any existing listener
        if self.listener:
            self.listener.stop()

        # Clear existing hotkeys
        self.hotkeys.clear()

        # Add hotkey to toggle macros on/off
        self.hotkeys[frozenset(['F1'])] = self.app.toggle_macros

        # Register macros
        for macro in macros:
            hotkey = macro.hotkey.upper()
            keys = hotkey.replace(' ', '').split('+')
            key_set = frozenset(keys)
            self.hotkeys[key_set] = macro

        # Start the listener in a separate thread
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

    def on_press(self, key):
        try:
            if isinstance(key, keyboard.KeyCode):
                self.current_keys.add(key.char.upper())
            elif isinstance(key, keyboard.Key):
                self.current_keys.add(key.name.upper())
        except AttributeError:
            pass

        for hotkey_keys, action in self.hotkeys.items():
            if hotkey_keys.issubset(self.current_keys):
                if hotkey_keys not in self.pressed_hotkeys:
                    self.pressed_hotkeys.add(hotkey_keys)
                    if callable(action):
                        threading.Thread(target=action).start()
                    else:
                        if self.app.macros_enabled:
                            action.execute()

    def on_release(self, key):
        try:
            if isinstance(key, keyboard.KeyCode):
                self.current_keys.discard(key.char.upper())
            elif isinstance(key, keyboard.Key):
                self.current_keys.discard(key.name.upper())
        except AttributeError:
            pass

        # Remove hotkeys that are no longer active
        to_remove = set()
        for hotkey_keys in self.pressed_hotkeys:
            if not hotkey_keys.issubset(self.current_keys):
                to_remove.add(hotkey_keys)
        self.pressed_hotkeys -= to_remove

# Macro Class
class Macro:
    def __init__(self, config, app):
        self.name = config["name"]
        self.hotkey = config["hotkey"]
        self.panel = config["panel"]
        self.click_positions = config["click_positions"]
        self.return_mouse = config["return_mouse"]
        self.return_to_inventory = config.get("return_to_inventory", False)
        self.click_after_return = config.get("click_after_return", False)
        self.press_panel_key = config.get("press_panel_key", True)
        self.is_dose_macro = config.get("is_dose_macro", False)  # Indicates if it's a dose-counting macro

        # Initialize call_count and current_position_index properly
        self.call_count = config.get("call_count")
        if self.call_count is None or not isinstance(self.call_count, int):
            self.call_count = 0

        self.current_position_index = config.get("current_position_index")
        if self.current_position_index is None or not isinstance(self.current_position_index, int):
            self.current_position_index = 0

        self.dose_count = config.get("dose_count", 4) if self.is_dose_macro else None  # Number of doses before cycling

        self.app = app  # Reference to the main application for logging and config

    def execute(self):
        threading.Thread(target=self.run_macro).start()

    def run_macro(self):
        if not self.app.macros_enabled:
            return

        start_time = time.time()
        log = []

        # Increment call count only for dose-counting macros
        if self.is_dose_macro:
            self.call_count += 1
            self.app.update_macro_call_count(self)
            self.app.config_save_required = True  # Flag to save config later

            # Determine if it's time to cycle click position
            if self.call_count % self.dose_count == 1 and self.call_count != 1:
                self.current_position_index = (self.current_position_index + 1) % len(self.click_positions)
                log.append(f"Cycled to next click position: {self.click_positions[self.current_position_index]}")

            current_click_position = self.click_positions[self.current_position_index]
        else:
            current_click_position = self.click_positions

        # Remember current mouse position
        original_position = pyautogui.position()
        log.append(f"Original mouse position: {original_position}")

        # Optional: Press panel key
        if self.press_panel_key:
            pyautogui.press(self.app.panel_key)
            log.append(f"Pressed panel key '{self.app.panel_key}'")
            time.sleep(self.app.interface_switch_time)

        # Get specific panel key
        specific_panel_keys = {
            'Inventory': self.app.inventory_key,
            'Prayer': self.app.prayer_key,
            'Spells': self.app.spells_key
        }
        specific_panel_key = specific_panel_keys.get(self.panel)

        # Press specific panel key
        pyautogui.press(specific_panel_key)
        log.append(f"Pressed specific panel key '{specific_panel_key}' for panel '{self.panel}'")
        time.sleep(self.app.action_registration_time())

        # Click configured positions
        if self.is_dose_macro:
            pos = current_click_position
            pyautogui.moveTo(pos[0], pos[1])
            pyautogui.click()
            log.append(f"Clicked at position {pos}")
            time.sleep(self.app.action_registration_time())
        else:
            for pos in current_click_position:
                pyautogui.moveTo(pos[0], pos[1])
                pyautogui.click()
                log.append(f"Clicked at position {pos}")
                time.sleep(self.app.action_registration_time())

        # Return mouse to original position
        if self.return_mouse:
            pyautogui.moveTo(original_position)
            log.append("Mouse returned to original position")
            # Optional click after returning mouse
            if self.click_after_return:
                pyautogui.click()
                log.append("Clicked after returning to original position")
            time.sleep(self.app.action_registration_time())

        # Optional: Return to Inventory
        if self.return_to_inventory:
            pyautogui.press(self.app.inventory_key)
            log.append(f"Pressed inventory key '{self.app.inventory_key}' to return to Inventory")
            time.sleep(self.app.interface_switch_time)

        end_time = time.time()
        total_time = end_time - start_time
        log.append(f"Macro '{self.name}' executed in {total_time:.3f} seconds")

        # Log to GUI using app.after to ensure thread safety
        log_message = "\n".join(log)
        self.app.after(0, self.app.log, log_message)

    def reset_call_count(self):
        self.call_count = 0
        if self.is_dose_macro:
            self.current_position_index = 0
            self.app.update_macro_call_count(self)
        self.app.log(f"Call count for macro '{self.name}' has been reset.")

# Functions to load macros
def load_macros(app):
    macros = []
    for macro_config in app.config["macros"]:
        macro = Macro(macro_config, app)
        macros.append(macro)
    return macros

# MacroApp Class
class MacroApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python Macro Application")
        self.geometry("800x900")
        self.config_load()

        # Timing configurations
        self.interface_switch_time = self.config.get("interface_switch_time", 0.3)
        self.action_registration_time_min = self.config.get("action_registration_time_min", 0.02)
        self.action_registration_time_max = self.config.get("action_registration_time_max", 0.05)

        # Panel keys
        self.panel_key = self.config.get("panel_key", "q")
        self.inventory_key = self.config.get("specific_panel_keys", {}).get("Inventory", "w")
        self.prayer_key = self.config.get("specific_panel_keys", {}).get("Prayer", "e")
        self.spells_key = self.config.get("specific_panel_keys", {}).get("Spells", "r")

        # Macros enabled
        self.macros_enabled = True

        # Initialize HotkeyManager
        self.hotkey_manager = HotkeyManager(self)

        # Initialize macros
        self.initialize_macros()

        self.create_widgets()
        self.update_mouse_position()
        self.register_hotkeys()

        # Periodically save config if required
        self.config_save_required = False  # Initialize flag
        self.after(5000, self.periodic_save_config)

    def config_load(self):
        try:
            with open('config.json', 'r') as file:
                self.config = json.load(file)
        except FileNotFoundError:
            # If config.json doesn't exist, create default config
            self.config = {
                "interface_switch_time": 0.3,
                "action_registration_time_min": 0.02,
                "action_registration_time_max": 0.05,
                "panel_key": "q",
                "specific_panel_keys": {
                    "Inventory": "w",
                    "Prayer": "e",
                    "Spells": "r"
                },
                "macros": []
            }
            self.save_config()

    def save_config(self):
        with open('config.json', 'w') as file:
            json.dump(self.config, file, indent=4)

    def periodic_save_config(self):
        if self.config_save_required:
            self.save_config()
            self.config_save_required = False
        self.after(5000, self.periodic_save_config)

    def initialize_macros(self):
        # No default macros are added automatically
        pass

    def load_config_macros(self):
        return load_macros(self)

    def register_hotkeys(self):
        self.macro_list_data = self.load_config_macros()
        self.hotkey_manager.register_hotkeys(self.macro_list_data)

    def create_widgets(self):
        main_instruction_label = ttk.Label(self,
                                           text="Use the 'Macros' tab to add or edit macros. Use the 'Settings' tab to configure timings and panel keys.")
        main_instruction_label.pack(padx=5, pady=5)

        # Notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill='both')

        # Macros tab
        self.macro_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.macro_frame, text='Macros')

        # Settings tab
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text='Settings')

        # Mouse position label
        self.mouse_pos_label = ttk.Label(self, text="Mouse Position: (0, 0)")
        self.mouse_pos_label.pack(side='bottom')

        # Log Display
        self.log_text = tk.Text(self, height=10)
        self.log_text.pack(expand=False, fill='x', side='bottom')

        # Add Enable/Disable Macros button
        self.toggle_macros_button = ttk.Button(self, text="Disable Macros", command=self.toggle_macros)
        self.toggle_macros_button.pack(pady=5)

        # Macros tab content
        self.create_macros_tab()

        # Settings tab content
        self.create_settings_tab()

    def create_macros_tab(self):
        # Treeview to display macros
        self.macro_list = ttk.Treeview(self.macro_frame, columns=('Name', 'Hotkey', 'Panel', 'Doses'), show='headings')
        self.macro_list.heading('Name', text='Name')
        self.macro_list.heading('Hotkey', text='Hotkey')
        self.macro_list.heading('Panel', text='Panel')
        self.macro_list.heading('Doses', text='Doses')  # Indicates dose-counting macros
        self.macro_list.pack(expand=True, fill='both')

        # Populate the treeview with existing macros
        for macro in self.config['macros']:
            doses = macro['dose_count'] if macro.get('is_dose_macro', False) else "N/A"
            self.macro_list.insert('', 'end', values=(macro['name'], macro['hotkey'], macro['panel'], doses))

        # Buttons
        btn_frame = ttk.Frame(self.macro_frame)
        btn_frame.pack(pady=10)

        add_macro_btn = ttk.Button(btn_frame, text="Add Macro", command=self.add_macro)
        add_macro_btn.pack(side='left', padx=5)

        edit_macro_btn = ttk.Button(btn_frame, text="Edit Macro", command=self.edit_macro)
        edit_macro_btn.pack(side='left', padx=5)

        del_macro_btn = ttk.Button(btn_frame, text="Delete Macro", command=self.delete_macro)
        del_macro_btn.pack(side='left', padx=5)

        reset_macro_btn = ttk.Button(btn_frame, text="Reset Call Count", command=self.reset_macro_call_count)
        reset_macro_btn.pack(side='left', padx=5)

    def create_settings_tab(self):
        row = 0
        # Interface Switch Time
        ttk.Label(self.settings_frame, text="Interface Switch Time (s):").grid(row=row, column=0, sticky='e', padx=5,
                                                                               pady=5)
        self.interface_switch_time_entry = ttk.Entry(self.settings_frame)
        self.interface_switch_time_entry.insert(0, str(self.interface_switch_time))
        self.interface_switch_time_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Action Registration Time Min
        ttk.Label(self.settings_frame, text="Action Registration Time Min (s):").grid(row=row, column=0, sticky='e',
                                                                                      padx=5, pady=5)
        self.action_time_min_entry = ttk.Entry(self.settings_frame)
        self.action_time_min_entry.insert(0, str(self.action_registration_time_min))
        self.action_time_min_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Action Registration Time Max
        ttk.Label(self.settings_frame, text="Action Registration Time Max (s):").grid(row=row, column=0, sticky='e',
                                                                                      padx=5, pady=5)
        self.action_time_max_entry = ttk.Entry(self.settings_frame)
        self.action_time_max_entry.insert(0, str(self.action_registration_time_max))
        self.action_time_max_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Panel Key
        ttk.Label(self.settings_frame, text="Panel Key:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.panel_key_entry = ttk.Entry(self.settings_frame)
        self.panel_key_entry.insert(0, self.panel_key)
        self.panel_key_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Specific Panel Keys
        ttk.Label(self.settings_frame, text="Inventory Panel Key:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.inventory_key_entry = ttk.Entry(self.settings_frame)
        self.inventory_key_entry.insert(0, self.inventory_key)
        self.inventory_key_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        ttk.Label(self.settings_frame, text="Prayer Panel Key:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.prayer_key_entry = ttk.Entry(self.settings_frame)
        self.prayer_key_entry.insert(0, self.prayer_key)
        self.prayer_key_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        ttk.Label(self.settings_frame, text="Spells Panel Key:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.spells_key_entry = ttk.Entry(self.settings_frame)
        self.spells_key_entry.insert(0, self.spells_key)
        self.spells_key_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Save Settings Button
        save_settings_btn = ttk.Button(self.settings_frame, text="Save Settings", command=self.save_settings)
        save_settings_btn.grid(row=row, column=0, columnspan=2, pady=10)

    def update_mouse_position(self):
        x, y = pyautogui.position()
        self.mouse_pos_label.config(text=f"Mouse Position: ({x}, {y})")
        self.after(100, self.update_mouse_position)

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

    def save_settings(self):
        try:
            self.interface_switch_time = float(self.interface_switch_time_entry.get())
            self.action_registration_time_min = float(self.action_time_min_entry.get())
            self.action_registration_time_max = float(self.action_time_max_entry.get())

            self.panel_key = self.panel_key_entry.get()
            self.inventory_key = self.inventory_key_entry.get()
            self.prayer_key = self.prayer_key_entry.get()
            self.spells_key = self.spells_key_entry.get()

            self.config['interface_switch_time'] = self.interface_switch_time
            self.config['action_registration_time_min'] = self.action_registration_time_min
            self.config['action_registration_time_max'] = self.action_registration_time_max
            self.config['panel_key'] = self.panel_key
            self.config['specific_panel_keys'] = {
                'Inventory': self.inventory_key,
                'Prayer': self.prayer_key,
                'Spells': self.spells_key
            }

            self.save_config()
            self.register_hotkeys()
            messagebox.showinfo("Settings Saved", "Settings have been saved successfully.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for the settings.")

    def action_registration_time(self):
        return (self.action_registration_time_min + self.action_registration_time_max) / 2

    def add_macro(self):
        MacroEditor(self, None)

    def edit_macro(self):
        selected_item = self.macro_list.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a macro to edit.")
            return
        values = self.macro_list.item(selected_item, 'values')
        macro_name = values[0]
        # Find the corresponding macro in config
        macro_config = next((m for m in self.config['macros'] if m['name'] == macro_name), None)
        if not macro_config:
            messagebox.showerror("Error", "Selected macro not found.")
            return
        MacroEditor(self, macro_config)

    def delete_macro(self):
        selected_item = self.macro_list.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a macro to delete.")
            return
        values = self.macro_list.item(selected_item, 'values')
        macro_name = values[0]
        # Find the corresponding macro in config
        macro_config = next((m for m in self.config['macros'] if m['name'] == macro_name), None)
        if not macro_config:
            messagebox.showerror("Error", "Selected macro not found.")
            return
        confirm = messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete macro '{macro_name}'?")
        if confirm:
            self.config['macros'].remove(macro_config)
            self.save_config()
            self.macro_list.delete(selected_item)
            self.register_hotkeys()
            self.log(f"Macro '{macro_name}' has been deleted.")

    def toggle_macros(self):
        self.macros_enabled = not self.macros_enabled
        if self.macros_enabled:
            self.toggle_macros_button.config(text="Disable Macros")
            self.log("Macros enabled.")
        else:
            self.toggle_macros_button.config(text="Enable Macros")
            self.log("Macros disabled via killswitch.")

    def register_hotkeys(self):
        self.macro_list_data = self.load_config_macros()
        self.hotkey_manager.register_hotkeys(self.macro_list_data)

    def update_macro_call_count(self, macro):
        # Find the macro in the treeview and update its 'Doses' column if it's a dose-counting macro
        for item in self.macro_list.get_children():
            values = self.macro_list.item(item, 'values')
            if values[0] == macro.name:
                doses = macro.dose_count if macro.is_dose_macro else "N/A"
                self.macro_list.item(item, values=(macro.name, macro.hotkey, macro.panel, doses))
                break

    def reset_macro_call_count(self):
        selected_item = self.macro_list.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a macro to reset call count.")
            return
        values = self.macro_list.item(selected_item, 'values')
        macro_name = values[0]
        # Find the corresponding macro in config
        macro = next((m for m in self.macro_list_data if m.name == macro_name), None)
        if not macro:
            messagebox.showerror("Error", "Selected macro not found.")
            return
        if macro.is_dose_macro:
            macro.reset_call_count()
            self.save_config()
            self.log(f"Call count for macro '{macro_name}' has been reset.")
        else:
            messagebox.showinfo("Not Applicable", "Call count reset is only applicable to dose-counting macros.")

# MacroEditor Class
class MacroEditor(tk.Toplevel):
    def __init__(self, parent, macro_config):
        super().__init__(parent)
        self.parent = parent
        self.macro_config = macro_config
        self.title("Macro Editor")
        self.geometry("500x600")
        self.create_widgets()

    def create_widgets(self):
        instruction_label = ttk.Label(self,
                                      text="Fill in the details for the macro. Use 'Add Position' to set click positions.")
        instruction_label.grid(row=0, column=0, columnspan=3, padx=10, pady=10)

        # Name
        ttk.Label(self, text="Macro Name:").grid(row=1, column=0, padx=10, pady=5, sticky='e')
        self.name_entry = ttk.Entry(self, width=30)
        self.name_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky='w')

        # Hotkey
        ttk.Label(self, text="Hotkey:").grid(row=2, column=0, padx=10, pady=5, sticky='e')
        self.hotkey_entry = ttk.Entry(self, width=30)
        self.hotkey_entry.grid(row=2, column=1, columnspan=2, padx=10, pady=5, sticky='w')

        # Select Panel
        ttk.Label(self, text="Select Panel:").grid(row=3, column=0, padx=10, pady=5, sticky='e')
        self.panel_options = ["Inventory", "Prayer", "Spells"]
        self.selected_panel = tk.StringVar()
        self.selected_panel.set(self.panel_options[0])
        self.panel_menu = ttk.OptionMenu(self, self.selected_panel, self.panel_options[0], *self.panel_options)
        self.panel_menu.grid(row=3, column=1, columnspan=2, padx=10, pady=5, sticky='w')

        # Press Panel Key Checkbox
        self.press_panel_key_var = tk.BooleanVar(value=True)
        self.press_panel_key_check = ttk.Checkbutton(self, text="Press Panel Key", variable=self.press_panel_key_var)
        self.press_panel_key_check.grid(row=4, column=0, columnspan=3, padx=10, pady=5, sticky='w')

        # Return Mouse Checkbox
        self.return_mouse_var = tk.BooleanVar(value=True)
        self.return_mouse_check = ttk.Checkbutton(self, text="Return Mouse to Original Position",
                                                  variable=self.return_mouse_var)
        self.return_mouse_check.grid(row=5, column=0, columnspan=3, padx=10, pady=5, sticky='w')

        # Click After Return Checkbox
        self.click_after_return_var = tk.BooleanVar(value=False)
        self.click_after_return_check = ttk.Checkbutton(self, text="Click After Returning Mouse",
                                                        variable=self.click_after_return_var)
        self.click_after_return_check.grid(row=6, column=0, columnspan=3, padx=10, pady=5, sticky='w')

        # Return to Inventory Checkbox
        self.return_to_inventory_var = tk.BooleanVar(value=False)
        self.return_to_inventory_check = ttk.Checkbutton(self, text="Return to Inventory",
                                                         variable=self.return_to_inventory_var)
        self.return_to_inventory_check.grid(row=7, column=0, columnspan=3, padx=10, pady=5, sticky='w')

        # Dose-Counting Macro Checkbox
        self.is_dose_macro_var = tk.BooleanVar(value=False)
        self.is_dose_macro_check = ttk.Checkbutton(self, text="Enable Dose-Counting", variable=self.is_dose_macro_var,
                                                   command=self.toggle_dose_count_entry)
        self.is_dose_macro_check.grid(row=8, column=0, columnspan=3, padx=10, pady=5, sticky='w')

        # Number of Doses Entry (only visible if dose-counting is enabled)
        ttk.Label(self, text="Number of Doses:").grid(row=9, column=0, padx=10, pady=5, sticky='e')
        self.dose_count_entry = ttk.Entry(self, width=10)
        self.dose_count_entry.grid(row=9, column=1, padx=10, pady=5, sticky='w')
        self.dose_count_entry.config(state='disabled')  # Initially disabled

        # Click Positions List
        ttk.Label(self, text="Click Positions:").grid(row=10, column=0, padx=10, pady=5, sticky='ne')
        self.click_positions_listbox = tk.Listbox(self, height=10, width=30)
        self.click_positions_listbox.grid(row=10, column=1, padx=10, pady=5, sticky='w')

        # Buttons for click positions
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=10, column=2, padx=10, pady=5, sticky='n')

        add_pos_btn = ttk.Button(btn_frame, text="Add Position", command=self.add_click_position)
        add_pos_btn.pack(side='top', padx=5, pady=2)

        del_pos_btn = ttk.Button(btn_frame, text="Delete Position", command=self.delete_click_position)
        del_pos_btn.pack(side='top', padx=5, pady=2)

        # Save Button
        save_btn = ttk.Button(self, text="Save Macro", command=self.save_macro)
        save_btn.grid(row=11, column=0, columnspan=3, pady=20)

        # Load macro data if editing
        if self.macro_config:
            self.load_macro_data()

    def toggle_dose_count_entry(self):
        if self.is_dose_macro_var.get():
            self.dose_count_entry.config(state='normal')
            self.dose_count_entry.focus()
        else:
            self.dose_count_entry.delete(0, tk.END)
            self.dose_count_entry.config(state='disabled')

    def load_macro_data(self):
        self.name_entry.insert(0, self.macro_config['name'])
        self.hotkey_entry.insert(0, self.macro_config['hotkey'])
        self.selected_panel.set(self.macro_config['panel'])
        self.return_mouse_var.set(self.macro_config['return_mouse'])
        self.click_after_return_var.set(self.macro_config.get('click_after_return', False))
        self.press_panel_key_var.set(self.macro_config.get('press_panel_key', True))
        self.return_to_inventory_var.set(self.macro_config.get('return_to_inventory', False))
        if self.macro_config.get('is_dose_macro', False):
            self.is_dose_macro_var.set(True)
            self.dose_count_entry.config(state='normal')
            self.dose_count_entry.insert(0, str(self.macro_config.get('dose_count', 4)))
        for pos in self.macro_config['click_positions']:
            self.click_positions_listbox.insert('end', str(pos))

    def add_click_position(self):
        self.info_label = ttk.Label(self, text="Move the mouse to the desired position and press 's' to set.")
        self.info_label.grid(row=12, column=0, columnspan=3, padx=10, pady=5)

        self.wait_for_position()

    def wait_for_position(self):
        def on_press(key):
            try:
                if key.char.lower() == 's':
                    x, y = pyautogui.position()
                    self.click_positions_listbox.insert('end', str((x, y)))
                    listener.stop()
                    self.info_label.destroy()
            except AttributeError:
                pass

        listener = keyboard.Listener(on_press=on_press)
        listener.start()

    def delete_click_position(self):
        selected = self.click_positions_listbox.curselection()
        if selected:
            self.click_positions_listbox.delete(selected)

    def save_macro(self):
        name = self.name_entry.get().strip()
        hotkey = self.hotkey_entry.get().strip()
        selected_panel = self.selected_panel.get()
        return_mouse = self.return_mouse_var.get()
        click_after_return = self.click_after_return_var.get()
        press_panel_key = self.press_panel_key_var.get()
        return_to_inventory = self.return_to_inventory_var.get()
        is_dose_macro = self.is_dose_macro_var.get()
        dose_count = None

        if is_dose_macro:
            dose_count_str = self.dose_count_entry.get().strip()
            if not dose_count_str.isdigit() or int(dose_count_str) <= 0:
                messagebox.showerror("Invalid Input", "Number of Doses must be a positive integer.")
                return
            dose_count = int(dose_count_str)

        try:
            click_positions = [ast.literal_eval(pos) for pos in self.click_positions_listbox.get(0, 'end')]
        except (ValueError, SyntaxError):
            messagebox.showerror("Invalid Positions", "Click positions must be in the format (x, y).")
            return

        if not name or not hotkey or not selected_panel:
            messagebox.showerror("Missing Information", "Please fill in all the required fields.")
            return

        # Check for unique macro name
        existing_names = [m['name'] for m in self.parent.config['macros']]
        if self.macro_config:
            # If editing, remove the current macro's name from the list to allow renaming to itself
            existing_names.remove(self.macro_config['name'])
        if name in existing_names:
            messagebox.showerror("Duplicate Name", "A macro with this name already exists. Please choose a different name.")
            return

        new_macro = {
            "name": name,
            "hotkey": hotkey,
            "panel": selected_panel,
            "click_positions": click_positions,
            "return_mouse": return_mouse,
            "click_after_return": click_after_return,
            "press_panel_key": press_panel_key,
            "return_to_inventory": return_to_inventory,
            "is_dose_macro": is_dose_macro
        }

        if is_dose_macro:
            new_macro["dose_count"] = dose_count
            new_macro["call_count"] = self.macro_config.get("call_count", 0) if self.macro_config else 0
            new_macro["current_position_index"] = self.macro_config.get("current_position_index", 0) if self.macro_config else 0
        else:
            # Ensure call_count and current_position_index are set to 0 for consistency
            new_macro["call_count"] = 0
            new_macro["current_position_index"] = 0

        if self.macro_config:
            # Update existing macro
            index = self.parent.config['macros'].index(self.macro_config)
            self.parent.config['macros'][index] = new_macro
        else:
            # Add new macro
            self.parent.config['macros'].append(new_macro)

        self.parent.save_config()
        # Refresh the macro list
        self.parent.macro_list.delete(*self.parent.macro_list.get_children())
        for macro in self.parent.config['macros']:
            doses = macro['dose_count'] if macro.get('is_dose_macro', False) else "N/A"
            self.parent.macro_list.insert('', 'end', values=(macro['name'], macro['hotkey'], macro['panel'], doses))
        self.parent.register_hotkeys()
        self.parent.log(f"Macro '{name}' has been saved.")
        self.destroy()

# Main Execution
if __name__ == "__main__":
    app = MacroApp()
    # Run the GUI in the main thread
    app.mainloop()
