# gui.py
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import pyautogui
import threading
import json

class MacroApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python Macro Application")
        self.geometry("600x400")
        self.config = self.load_config()

        # Timing configurations
        self.interface_switch_time = self.config.get("interface_switch_time", 0.3)
        self.action_time_min = self.config.get("action_registration_time_min", 0.02)
        self.action_time_max = self.config.get("action_registration_time_max", 0.05)

        self.create_widgets()
        self.update_mouse_position()

    def load_config(self):
        with open('config.json', 'r') as file:
            return json.load(file)

    def save_config(self):
        with open('config.json', 'w') as file:
            json.dump(self.config, file, indent=4)

    def create_widgets(self):
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

        # Macros tab content
        self.create_macros_tab()

        # Settings tab content
        self.create_settings_tab()

    def create_macros_tab(self):
        self.macro_list = ttk.Treeview(self.macro_frame, columns=('Hotkey', 'Panel Key', 'Specific Panel Key'), show='headings')
        self.macro_list.heading('Hotkey', text='Hotkey')
        self.macro_list.heading('Panel Key', text='Panel Key')
        self.macro_list.heading('Specific Panel Key', text='Specific Panel Key')
        self.macro_list.pack(expand=True, fill='both')

        for macro in self.config['macros']:
            self.macro_list.insert('', 'end', values=(macro['hotkey'], macro['panel_key'], macro['specific_panel_key']))

        # Buttons
        btn_frame = ttk.Frame(self.macro_frame)
        btn_frame.pack(pady=10)

        add_macro_btn = ttk.Button(btn_frame, text="Add Macro", command=self.add_macro)
        add_macro_btn.pack(side='left', padx=5)

        edit_macro_btn = ttk.Button(btn_frame, text="Edit Macro", command=self.edit_macro)
        edit_macro_btn.pack(side='left', padx=5)

        del_macro_btn = ttk.Button(btn_frame, text="Delete Macro", command=self.delete_macro)
        del_macro_btn.pack(side='left', padx=5)

    def create_settings_tab(self):
        # Interface Switch Time
        ttk.Label(self.settings_frame, text="Interface Switch Time (s):").grid(row=0, column=0, sticky='e', padx=5, pady=5)
        self.interface_switch_time_entry = ttk.Entry(self.settings_frame)
        self.interface_switch_time_entry.insert(0, str(self.interface_switch_time))
        self.interface_switch_time_entry.grid(row=0, column=1, padx=5, pady=5)

        # Action Registration Time Min
        ttk.Label(self.settings_frame, text="Action Registration Time Min (s):").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.action_time_min_entry = ttk.Entry(self.settings_frame)
        self.action_time_min_entry.insert(0, str(self.action_time_min))
        self.action_time_min_entry.grid(row=1, column=1, padx=5, pady=5)

        # Action Registration Time Max
        ttk.Label(self.settings_frame, text="Action Registration Time Max (s):").grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.action_time_max_entry = ttk.Entry(self.settings_frame)
        self.action_time_max_entry.insert(0, str(self.action_time_max))
        self.action_time_max_entry.grid(row=2, column=1, padx=5, pady=5)

        # Save Settings Button
        save_settings_btn = ttk.Button(self.settings_frame, text="Save Settings", command=self.save_settings)
        save_settings_btn.grid(row=3, column=0, columnspan=2, pady=10)

    def update_mouse_position(self):
        x, y = pyautogui.position()
        self.mouse_pos_label.config(text=f"Mouse Position: ({x}, {y})")
        self.after(100, self.update_mouse_position)

    def log(self, message):
        print(message)  # For simplicity, logs are printed to the console. You can implement a logging window if needed.

    def save_settings(self):
        try:
            self.interface_switch_time = float(self.interface_switch_time_entry.get())
            self.action_time_min = float(self.action_time_min_entry.get())
            self.action_time_max = float(self.action_time_max_entry.get())

            self.config['interface_switch_time'] = self.interface_switch_time
            self.config['action_registration_time_min'] = self.action_time_min
            self.config['action_registration_time_max'] = self.action_time_max

            self.save_config()
            messagebox.showinfo("Settings Saved", "Settings have been saved successfully.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for the settings.")

    def add_macro(self):
        MacroEditor(self, None)

    def edit_macro(self):
        selected_item = self.macro_list.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a macro to edit.")
            return
        index = self.macro_list.index(selected_item)
        macro_config = self.config['macros'][index]
        MacroEditor(self, macro_config)

    def delete_macro(self):
        selected_item = self.macro_list.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a macro to delete.")
            return
        index = self.macro_list.index(selected_item)
        del self.config['macros'][index]
        self.save_config()
        self.macro_list.delete(selected_item)

class MacroEditor(tk.Toplevel):
    def __init__(self, parent, macro_config):
        super().__init__(parent)
        self.parent = parent
        self.macro_config = macro_config
        self.title("Macro Editor")

        self.create_widgets()

    def create_widgets(self):
        # Name
        ttk.Label(self, text="Macro Name:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.name_entry = ttk.Entry(self)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)

        # Hotkey
        ttk.Label(self, text="Hotkey:").grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.hotkey_entry = ttk.Entry(self)
        self.hotkey_entry.grid(row=1, column=1, padx=5, pady=5)

        # Panel Key
        ttk.Label(self, text="Panel Key:").grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.panel_key_entry = ttk.Entry(self)
        self.panel_key_entry.grid(row=2, column=1, padx=5, pady=5)

        # Specific Panel Key
        ttk.Label(self, text="Specific Panel Key:").grid(row=3, column=0, padx=5, pady=5, sticky='e')
        self.specific_panel_key_entry = ttk.Entry(self)
        self.specific_panel_key_entry.grid(row=3, column=1, padx=5, pady=5)

        # Return Mouse Checkbox
        self.return_mouse_var = tk.BooleanVar(value=True)
        self.return_mouse_check = ttk.Checkbutton(self, text="Return Mouse to Original Position", variable=self.return_mouse_var)
        self.return_mouse_check.grid(row=4, column=0, columnspan=2, pady=5)

        # Click After Return Checkbox
        self.click_after_return_var = tk.BooleanVar(value=False)
        self.click_after_return_check = ttk.Checkbutton(self, text="Click After Returning Mouse", variable=self.click_after_return_var)
        self.click_after_return_check.grid(row=5, column=0, columnspan=2, pady=5)

        # Click Positions List
        ttk.Label(self, text="Click Positions:").grid(row=6, column=0, padx=5, pady=5, sticky='ne')
        self.click_positions_listbox = tk.Listbox(self, height=5)
        self.click_positions_listbox.grid(row=6, column=1, padx=5, pady=5, sticky='we')

        # Buttons for click positions
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=7, column=1, padx=5, pady=5, sticky='e')

        add_pos_btn = ttk.Button(btn_frame, text="Add Position", command=self.add_click_position)
        add_pos_btn.pack(side='left', padx=5)

        del_pos_btn = ttk.Button(btn_frame, text="Delete Position", command=self.delete_click_position)
        del_pos_btn.pack(side='left', padx=5)

        # Save Button
        save_btn = ttk.Button(self, text="Save Macro", command=self.save_macro)
        save_btn.grid(row=8, column=0, columnspan=2, pady=10)

        # Load macro data if editing
        if self.macro_config:
            self.load_macro_data()

    def load_macro_data(self):
        self.name_entry.insert(0, self.macro_config['name'])
        self.hotkey_entry.insert(0, self.macro_config['hotkey'])
        self.panel_key_entry.insert(0, self.macro_config['panel_key'])
        self.specific_panel_key_entry.insert(0, self.macro_config['specific_panel_key'])
        self.return_mouse_var.set(self.macro_config['return_mouse'])
        self.click_after_return_var.set(self.macro_config.get('click_after_return', False))
        for pos in self.macro_config['click_positions']:
            self.click_positions_listbox.insert('end', str(pos))

    def add_click_position(self):
        self.withdraw()
        messagebox.showinfo("Set Position", "Move the mouse to the desired position and press 's' to set.")
        self.wait_for_position()

    def wait_for_position(self):
        def on_press(event):
            if event.name == 's':
                x, y = pyautogui.position()
                self.click_positions_listbox.insert('end', str((x, y)))
                keyboard.unhook_all()
                self.deiconify()
        keyboard.on_press(on_press)

    def delete_click_position(self):
        selected = self.click_positions_listbox.curselection()
        if selected:
            self.click_positions_listbox.delete(selected)

    def save_macro(self):
        name = self.name_entry.get()
        hotkey = self.hotkey_entry.get()
        panel_key = self.panel_key_entry.get()
        specific_panel_key = self.specific_panel_key_entry.get()
        return_mouse = self.return_mouse_var.get()
        click_after_return = self.click_after_return_var.get()
        click_positions = [eval(pos) for pos in self.click_positions_listbox.get(0, 'end')]

        if not name or not hotkey or not panel_key or not specific_panel_key:
            messagebox.showerror("Missing Information", "Please fill in all the required fields.")
            return

        new_macro = {
            "name": name,
            "hotkey": hotkey,
            "panel_key": panel_key,
            "specific_panel_key": specific_panel_key,
            "click_positions": click_positions,
            "return_mouse": return_mouse,
            "click_after_return": click_after_return
        }

        if self.macro_config:
            # Update existing macro
            index = self.parent.config['macros'].index(self.macro_config)
            self.parent.config['macros'][index] = new_macro
        else:
            # Add new macro
            self.parent.config['macros'].append(new_macro)

        self.parent.save_config()
        self.parent.macro_list.insert('', 'end', values=(hotkey, panel_key, specific_panel_key))
        self.destroy()

