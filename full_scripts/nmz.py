import ast
import json
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import queue

import pyautogui
from pynput import keyboard


class HotkeyManager:
    def __init__(self, app):
        self.app = app
        self.hotkeys = {}
        self.listener = None
        self.current_keys = set()
        self.pressed_hotkeys = set()

    def register_hotkeys(self, macros):
        if self.listener:
            self.listener.stop()
        self.hotkeys.clear()
        self.hotkeys[frozenset(['F1'])] = self.app.toggle_macros

        for macro in macros:
            if macro.hotkey:
                hotkey = macro.hotkey.upper()
                keys = hotkey.replace(' ', '').split('+')
                key_set = frozenset(keys)
                self.hotkeys[key_set] = macro

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
                            action.toggle_execution()

    def on_release(self, key):
        try:
            if isinstance(key, keyboard.KeyCode):
                self.current_keys.discard(key.char.upper())
            elif isinstance(key, keyboard.Key):
                self.current_keys.discard(key.name.upper())
        except AttributeError:
            pass

        to_remove = set()
        for hotkey_keys in self.pressed_hotkeys:
            if not hotkey_keys.issubset(self.current_keys):
                to_remove.add(hotkey_keys)
        self.pressed_hotkeys -= to_remove


class Macro:
    def __init__(self, config, app):
        self.name = config["name"]
        self.hotkey = config.get("hotkey", None)
        self.actions = config["actions"]
        self.is_dose_macro = config.get("is_dose_macro", False)
        self.dose_count = config.get("dose_count", 4) if self.is_dose_macro else None

        self.call_count = config.get("call_count", 0)
        self.current_position_index = config.get("current_position_index", 0)

        self.is_loop_macro = config.get("is_loop_macro", False)
        self.loop_count = config.get("loop_count", 1) if self.is_loop_macro else 1
        self.current_loop_index = 0

        self.app = app

        self.is_scheduled = config.get("is_scheduled", False)
        self.schedule_interval = config.get("schedule_interval", 0)
        self.scheduler_thread = None
        self.scheduling_lock = threading.Lock()

        self.is_running = False
        self.is_active = False  # Flag to track if the macro is active (started)

    def toggle_execution(self):
        if self.is_active:
            self.stop_macro()
        else:
            self.start_macro()

    def start_macro(self):
        self.is_active = True
        if self.is_scheduled:
            self.start_scheduler()
            self.app.log(f"Scheduled macro '{self.name}' started.")
        else:
            self.app.macro_queue.put(self)
            self.app.log(f"Macro '{self.name}' queued for execution.")

    def stop_macro(self):
        self.is_active = False
        if self.is_scheduled:
            self.stop_scheduler()
            self.app.log(f"Scheduled macro '{self.name}' stopped.")
        else:
            self.is_running = False  # Stop the macro if it's running
            self.app.log(f"Macro '{self.name}' stopped.")

    def run_macro(self):
        if not self.app.macros_enabled or not self.is_active:
            self.is_running = False
            return
        self.is_running = True

        total_loops = self.loop_count if self.is_loop_macro else 1
        infinite_loop = self.loop_count == -1
        total_log = []
        start_time = time.time()

        try:
            while self.is_active and (infinite_loop or self.current_loop_index < total_loops):
                if not self.app.macros_enabled:
                    break

                self.current_loop_index += 1
                loop_start_time = time.time()
                log = []

                original_position = pyautogui.position()
                log.append(f"Original mouse position: {original_position}")

                self.run_actions(self.actions, original_position, log)

                loop_end_time = time.time()
                loop_total_time = loop_end_time - loop_start_time
                total_log.append(
                    f"Loop {self.current_loop_index}/{total_loops if not infinite_loop else '∞'} executed in {loop_total_time:.3f} seconds")
                total_log.extend(log)

                if self.is_loop_macro and not infinite_loop:
                    loops_remaining = total_loops - self.current_loop_index
                    average_time_per_loop = (loop_end_time - start_time) / self.current_loop_index
                    estimated_time_remaining = loops_remaining * average_time_per_loop
                    self.app.after(0, self.app.update_eta_tracker, estimated_time_remaining)
        finally:
            end_time = time.time()
            total_time = end_time - start_time

            self.app.after(0, self.app.log_macro_execution, self.name, total_log, total_time)
            self.current_loop_index = 0
            if self.is_loop_macro:
                self.app.after(0, self.app.reset_eta_tracker)
            self.is_running = False

    def run_actions(self, actions, original_position, log):
        for action in actions:
            if not self.app.macros_enabled or not self.is_active:
                break

            action_type = action.get('type')
            action_start_time = time.time()
            annotation = action.get('annotation', '')

            if action_type == 'press_panel_key':
                key = action.get('key', self.app.panel_key)
                pyautogui.press(key)
                action_end_time = time.time()
                action_time = action_end_time - action_start_time
                log.append(
                    f"Pressed panel key '{key}' {f'({annotation})' if annotation else ''} (took {action_time:.3f} seconds)")

            elif action_type == 'press_specific_panel_key':
                panel = action.get('panel')
                if panel == 'Custom':
                    key = action.get('custom_key')
                else:
                    specific_panel_keys = {
                        'Inventory': self.app.inventory_key,
                        'Prayer': self.app.prayer_key,
                        'Spells': self.app.spells_key
                    }
                    key = specific_panel_keys.get(panel)
                pyautogui.press(key)
                action_end_time = time.time()
                action_time = action_end_time - action_start_time
                log.append(
                    f"Pressed specific panel key '{key}' for panel '{panel}' {f'({annotation})' if annotation else ''} (took {action_time:.3f} seconds)")

            elif action_type == 'click':
                positions = action.get('positions', [])
                use_saved_target = action.get('use_saved_target', False)
                modifiers = action.get('modifiers', [])
                modifier_keys = {'Shift': 'shift', 'Ctrl': 'ctrl', 'Alt': 'alt'}

                for mod in modifiers:
                    pyautogui.keyDown(modifier_keys[mod])

                if use_saved_target:
                    pos = original_position
                else:
                    if self.is_dose_macro:
                        pos_index = self.current_position_index % len(positions)
                        pos = positions[pos_index]
                    else:
                        pos = positions

                if isinstance(pos[0], (list, tuple)):
                    for p in pos:
                        pyautogui.moveTo(p[0], p[1], duration=self.app.mouse_move_duration)
                        pyautogui.click()
                        action_end_time = time.time()
                        action_time = action_end_time - action_start_time
                        log.append(
                            f"Clicked at position {p} with modifiers {modifiers} {f'({annotation})' if annotation else ''} (took {action_time:.3f} seconds)")
                        action_start_time = time.time()
                else:
                    pyautogui.moveTo(pos[0], pos[1], duration=self.app.mouse_move_duration)
                    pyautogui.click()
                    action_end_time = time.time()
                    action_time = action_end_time - action_start_time
                    log.append(
                        f"Clicked at position {pos} with modifiers {modifiers} {f'({annotation})' if annotation else ''} (took {action_time:.3f} seconds)")

                for mod in modifiers:
                    pyautogui.keyUp(modifier_keys[mod])

                if self.is_dose_macro:
                    self.call_count += 1
                    self.app.after(0, self.app.update_macro_call_count, self)
                    if self.call_count % self.dose_count == 0:
                        self.current_position_index = (self.current_position_index + 1) % self.get_total_positions()
                        log.append(f"Cycled to next position index: {self.current_position_index}")

            elif action_type == 'return_mouse':
                pyautogui.moveTo(original_position[0], original_position[1],
                                 duration=self.app.mouse_move_duration)
                action_end_time = time.time()
                action_time = action_end_time - action_start_time
                log.append(
                    f"Mouse returned to original position {f'({annotation})' if annotation else ''} (took {action_time:.3f} seconds)")
                click_after_return = action.get('click_after_return', False)
                if click_after_return:
                    pyautogui.click()
                    action_end_time = time.time()
                    action_time = action_end_time - action_start_time
                    log.append(
                        f"Clicked after returning to original position {f'({annotation})' if annotation else ''} (took {action_time:.3f} seconds)")

            elif action_type == 'wait':
                duration = action.get('duration', self.app.action_registration_time())
                if isinstance(duration, str):
                    duration = self.app.wait_times.get(duration, self.app.action_registration_time())
                time.sleep(duration)
                action_end_time = time.time()
                action_time = action_end_time - action_start_time
                log.append(
                    f"Waited for {duration} seconds {f'({annotation})' if annotation else ''} (took {action_time:.3f} seconds)")

            elif action_type == 'run_macro':
                macro_name = action.get('macro_name')
                sub_macro = next((m for m in self.app.macro_list_data if m.name == macro_name), None)
                if sub_macro:
                    if sub_macro == self:
                        log.append(f"Cannot run macro '{macro_name}' recursively.")
                    else:
                        sub_macro.run_actions(sub_macro.actions, original_position, log)
                        action_end_time = time.time()
                        action_time = action_end_time - action_start_time
                        log.append(
                            f"Ran sub-macro '{macro_name}' {f'({annotation})' if annotation else ''} (took {action_time:.3f} seconds)")
                else:
                    log.append(f"Macro '{macro_name}' not found.")

            else:
                log.append(f"Unknown action type: {action_type}")

    def get_total_positions(self):
        total_positions = 0
        for action in self.actions:
            if action.get('type') == 'click':
                positions = action.get('positions', [])
                total_positions = max(total_positions, len(positions))
        return total_positions if total_positions > 0 else 1

    def reset_call_count(self):
        self.call_count = 0
        if self.is_dose_macro:
            self.current_position_index = 0
            self.app.update_macro_call_count(self)
        self.app.log(f"Call count for macro '{self.name}' has been reset.")
        self.app.config_save_required = True

    # The following methods have been updated to ensure immediate start
    def start_scheduler(self):
        if self.is_scheduled and self.is_active:
            self.schedule_next_run(initial=True)

    def schedule_next_run(self, initial=False):
        if not self.app.macros_enabled or not self.is_active:
            return
        with self.scheduling_lock:
            if self.scheduler_thread:
                self.scheduler_thread.cancel()
            delay = 0 if initial else self.schedule_interval
            self.scheduler_thread = threading.Timer(delay, self.run_scheduled_macro)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()

    def run_scheduled_macro(self):
        if not self.app.macros_enabled or not self.is_active:
            return
        self.app.macro_queue.put(self)
        self.schedule_next_run()

    def stop_scheduler(self):
        with self.scheduling_lock:
            if self.scheduler_thread:
                self.scheduler_thread.cancel()
                self.scheduler_thread = None


def load_macros(app):
    macros = []
    for macro_config in app.config["macros"]:
        macro = Macro(macro_config, app)
        macros.append(macro)
    return macros


class MacroApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python Macro Application")
        self.geometry("800x900")
        self.config_load()

        # Timing configurations
        self.interface_switch_time = self.config.get("interface_switch_time", 0.02)
        self.action_registration_time_min = self.config.get("action_registration_time_min", 0.02)
        self.action_registration_time_max = self.config.get("action_registration_time_max", 0.02)
        self.mouse_move_duration = self.config.get("mouse_move_duration", 0)

        # Wait times
        self.wait_times = self.config.get("wait_times", {"tick_time": 0.6})

        # Panel keys
        self.panel_key = self.config.get("panel_key", "q")
        self.inventory_key = self.config.get("specific_panel_keys", {}).get("Inventory", "w")
        self.prayer_key = self.config.get("specific_panel_keys", {}).get("Prayer", "e")
        self.spells_key = self.config.get("specific_panel_keys", {}).get("Spells", "r")

        # Macros enabled
        self.macros_enabled = True

        # Task queue delay
        self.task_queue_delay = self.config.get("task_queue_delay", 0)

        # Initialize HotkeyManager
        self.hotkey_manager = HotkeyManager(self)

        # Initialize macros
        self.initialize_macros()

        # Set pyautogui pause to eliminate default delay
        pyautogui.PAUSE = 0.025

        self.macro_queue = queue.Queue()
        self.macro_worker_thread = threading.Thread(target=self.macro_queue_worker, daemon=True)
        self.macro_worker_thread.start()

        self.create_widgets()
        self.update_mouse_position()
        self.register_hotkeys()

        # Periodically save config if required
        self.config_save_required = False
        self.after(5000, self.periodic_save_config)

    def macro_queue_worker(self):
        while True:
            macro = self.macro_queue.get()
            if macro is None:
                break  # Stop the worker if None is received
            if macro.is_active and self.macros_enabled:
                macro.run_macro()
            else:
                self.log(f"Macro '{macro.name}' was skipped because it is not active or macros are disabled.")
            self.macro_queue.task_done()
            if self.task_queue_delay > 0:
                time.sleep(self.task_queue_delay)

    def config_load(self):
        try:
            with open('config.json', 'r') as file:
                self.config = json.load(file)
        except FileNotFoundError:
            self.config = {
                "interface_switch_time": 0.02,
                "action_registration_time_min": 0.02,
                "action_registration_time_max": 0.02,
                "mouse_move_duration": 0,
                "panel_key": "q",
                "specific_panel_keys": {
                    "Inventory": "w",
                    "Prayer": "e",
                    "Spells": "r"
                },
                "wait_times": {"tick_time": 0.6},
                "macros": [],
                "task_queue_delay": 0
            }
            self.save_config()
        self.task_queue_delay = self.config.get("task_queue_delay", 0)

    def save_config(self):
        self.config['task_queue_delay'] = self.task_queue_delay
        with open('config.json', 'w') as file:
            json.dump(self.config, file, indent=4)

    def periodic_save_config(self):
        if self.config_save_required:
            self.save_config()
            self.config_save_required = False
        self.after(5000, self.periodic_save_config)

    def initialize_macros(self):
        pass

    def load_config_macros(self):
        return load_macros(self)

    def register_hotkeys(self):
        self.macro_list_data = self.load_config_macros()
        self.hotkey_manager.register_hotkeys(self.macro_list_data)
        for macro in self.macro_list_data:
            if macro.is_scheduled and macro.is_active:
                macro.start_scheduler()

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
        self.log_text = tk.Text(self, height=15)
        self.log_text.pack(expand=True, fill='both', side='bottom')
        self.log_text.tag_configure('timestamp', foreground='grey')
        self.log_text.tag_configure('macro_name', foreground='blue')
        self.log_text.tag_configure('action', foreground='black')
        self.log_text.tag_configure('error', foreground='red')
        self.log_text.tag_configure('success', foreground='green')

        # Add Enable/Disable Macros button
        self.toggle_macros_button = ttk.Button(self, text="Disable Macros", command=self.toggle_macros)
        self.toggle_macros_button.pack(pady=5)

        # ETA Label
        self.eta_label = ttk.Label(self, text="Estimated Time Remaining: N/A")
        self.eta_label.pack(padx=5, pady=5)

        # Macros tab content
        self.create_macros_tab()

        # Settings tab content
        self.create_settings_tab()

    def create_macros_tab(self):
        self.macro_list = ttk.Treeview(self.macro_frame,
                                       columns=(
                                           'Name', 'Hotkey', 'Scheduled', 'Active', 'Doses', 'Call Count', 'Reset'),
                                       show='headings')
        self.macro_list.heading('Name', text='Name')
        self.macro_list.heading('Hotkey', text='Hotkey')
        self.macro_list.heading('Scheduled', text='Scheduled')
        self.macro_list.heading('Active', text='Active')
        self.macro_list.heading('Doses', text='Doses')
        self.macro_list.heading('Call Count', text='Call Count')
        self.macro_list.heading('Reset', text='Reset')
        self.macro_list.pack(expand=True, fill='both')
        self.macro_list.column('Name', width=150)
        self.macro_list.column('Hotkey', width=100)
        self.macro_list.column('Scheduled', width=80)
        self.macro_list.column('Active', width=60)
        self.macro_list.column('Doses', width=60)
        self.macro_list.column('Call Count', width=80)
        self.macro_list.column('Reset', width=60)

        # Populate the treeview with existing macros
        for macro in self.config['macros']:
            doses = macro['dose_count'] if macro.get('is_dose_macro', False) else "N/A"
            call_count = macro.get('call_count', 0) if macro.get('is_dose_macro', False) else ""
            reset_text = 'Reset' if macro.get('is_dose_macro', False) else ""
            scheduled = 'Yes' if macro.get('is_scheduled', False) else 'No'
            active = 'No'
            self.macro_list.insert('', 'end',
                                   values=(macro['name'], macro.get('hotkey', ''), scheduled, active, doses, call_count,
                                           reset_text))

        # Bind double-click event
        self.macro_list.bind('<Double-1>', self.on_macro_double_click)
        # Bind click event
        self.macro_list.bind('<ButtonRelease-1>', self.on_macro_click)

        # Buttons
        btn_frame = ttk.Frame(self.macro_frame)
        btn_frame.pack(pady=10)

        add_macro_btn = ttk.Button(btn_frame, text="Add Macro", command=self.add_macro)
        add_macro_btn.pack(side='left', padx=5)

        edit_macro_btn = ttk.Button(btn_frame, text="Edit Macro", command=self.edit_macro)
        edit_macro_btn.pack(side='left', padx=5)

        del_macro_btn = ttk.Button(btn_frame, text="Delete Macro", command=self.delete_macro)
        del_macro_btn.pack(side='left', padx=5)

        start_macro_btn = ttk.Button(btn_frame, text="Start Macro", command=self.start_selected_macro)
        start_macro_btn.pack(side='left', padx=5)

        stop_macro_btn = ttk.Button(btn_frame, text="Stop Macro", command=self.stop_selected_macro)
        stop_macro_btn.pack(side='left', padx=5)

    def on_macro_double_click(self, event):
        self.edit_macro()

    def on_macro_click(self, event):
        item = self.macro_list.identify_row(event.y)
        column = self.macro_list.identify_column(event.x)
        if not item:
            return
        if column == '#7':
            values = self.macro_list.item(item, 'values')
            macro_name = values[0]
            macro = next((m for m in self.macro_list_data if m.name == macro_name), None)
            if macro and macro.is_dose_macro:
                macro.reset_call_count()
                self.save_config()
                self.log(f"Call count for macro '{macro_name}' has been reset.")
                self.update_macro_call_count(macro)

    def start_selected_macro(self):
        selected_item = self.macro_list.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a macro to start.")
            return
        values = self.macro_list.item(selected_item, 'values')
        macro_name = values[0]
        macro = next((m for m in self.macro_list_data if m.name == macro_name), None)
        if macro:
            macro.start_macro()
            self.update_macro_active_status(macro)

    def stop_selected_macro(self):
        selected_item = self.macro_list.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a macro to stop.")
            return
        values = self.macro_list.item(selected_item, 'values')
        macro_name = values[0]
        macro = next((m for m in self.macro_list_data if m.name == macro_name), None)
        if macro:
            macro.stop_macro()
            self.update_macro_active_status(macro)

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

        # Mouse Move Duration
        ttk.Label(self.settings_frame, text="Mouse Move Duration (s):").grid(row=row, column=0, sticky='e', padx=5,
                                                                             pady=5)
        self.mouse_move_duration_entry = ttk.Entry(self.settings_frame)
        self.mouse_move_duration_entry.insert(0, str(self.mouse_move_duration))
        self.mouse_move_duration_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Panel Key
        ttk.Label(self.settings_frame, text="Panel Key:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.panel_key_entry = ttk.Entry(self.settings_frame)
        self.panel_key_entry.insert(0, self.panel_key)
        self.panel_key_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Specific Panel Keys
        ttk.Label(self.settings_frame, text="Inventory Panel Key:").grid(row=row, column=0, sticky='e', padx=5,
                                                                         pady=5)
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

        # Task Queue Delay
        ttk.Label(self.settings_frame, text="Task Queue Delay (s):").grid(row=row, column=0, sticky='e', padx=5,
                                                                          pady=5)
        self.task_queue_delay_entry = ttk.Entry(self.settings_frame)
        self.task_queue_delay_entry.insert(0, str(self.task_queue_delay))
        self.task_queue_delay_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Wait Times
        ttk.Label(self.settings_frame, text="Wait Times:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
        row += 1
        self.wait_time_entries = {}
        for wait_name in self.wait_times:
            ttk.Label(self.settings_frame, text=f"{wait_name}:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
            entry = ttk.Entry(self.settings_frame)
            entry.insert(0, str(self.wait_times[wait_name]))
            entry.grid(row=row, column=1, padx=5, pady=5)
            self.wait_time_entries[wait_name] = entry
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
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", 'timestamp')
        self.log_text.see(tk.END)

    def log_macro_execution(self, macro_name, log_messages, total_time):
        self.log_text.insert(tk.END, f"Macro '{macro_name}' executed in {total_time:.3f} seconds\n", 'macro_name')
        for msg in log_messages:
            self.log_text.insert(tk.END, f"    {msg}\n", 'action')
        self.log_text.see(tk.END)

    def save_settings(self):
        try:
            self.interface_switch_time = float(self.interface_switch_time_entry.get())
            self.action_registration_time_min = float(self.action_time_min_entry.get())
            self.action_registration_time_max = float(self.action_time_max_entry.get())
            self.mouse_move_duration = float(self.mouse_move_duration_entry.get())

            self.panel_key = self.panel_key_entry.get()
            self.inventory_key = self.inventory_key_entry.get()
            self.prayer_key = self.prayer_key_entry.get()
            self.spells_key = self.spells_key_entry.get()

            self.task_queue_delay = float(self.task_queue_delay_entry.get())

            self.config['interface_switch_time'] = self.interface_switch_time
            self.config['action_registration_time_min'] = self.action_registration_time_min
            self.config['action_registration_time_max'] = self.action_registration_time_max
            self.config['mouse_move_duration'] = self.mouse_move_duration
            self.config['panel_key'] = self.panel_key
            self.config['specific_panel_keys'] = {
                'Inventory': self.inventory_key,
                'Prayer': self.prayer_key,
                'Spells': self.spells_key
            }
            self.config['task_queue_delay'] = self.task_queue_delay

            # Save wait times
            for wait_name, entry in self.wait_time_entries.items():
                try:
                    self.wait_times[wait_name] = float(entry.get())
                except ValueError:
                    messagebox.showerror("Invalid Input", f"Wait time '{wait_name}' must be a number.")
                    return
            self.config['wait_times'] = self.wait_times

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
            for macro in self.macro_list_data:
                if macro.is_scheduled and macro.is_active:
                    macro.start_scheduler()
        else:
            self.toggle_macros_button.config(text="Enable Macros")
            self.log("Macros disabled via killswitch.")
            for macro in self.macro_list_data:
                if macro.is_scheduled and macro.is_active:
                    macro.stop_scheduler()
                else:
                    macro.is_running = False  # Stop any running macros

    def update_macro_call_count(self, macro):
        for item in self.macro_list.get_children():
            values = self.macro_list.item(item, 'values')
            if values[0] == macro.name:
                doses = macro.dose_count if macro.is_dose_macro else "N/A"
                call_count = macro.call_count if macro.is_dose_macro else ""
                reset_text = 'Reset' if macro.is_dose_macro else ""
                scheduled = 'Yes' if macro.is_scheduled else 'No'
                active = 'Yes' if macro.is_active else 'No'
                self.macro_list.item(item, values=(
                    macro.name, macro.hotkey or '', scheduled, active, doses, call_count, reset_text))
                break

    def update_macro_active_status(self, macro):
        for item in self.macro_list.get_children():
            values = self.macro_list.item(item, 'values')
            if values[0] == macro.name:
                active = 'Yes' if macro.is_active else 'No'
                self.macro_list.set(item, 'Active', active)
                break

    def update_eta_tracker(self, estimated_time_remaining):
        minutes, seconds = divmod(int(estimated_time_remaining), 60)
        time_str = f"{minutes}m {seconds}s remaining"
        self.eta_label.config(text=f"Estimated Time Remaining: {time_str}")

    def reset_eta_tracker(self):
        self.eta_label.config(text="Estimated Time Remaining: N/A")


# MacroEditor Class
class MacroEditor(tk.Toplevel):
    def __init__(self, parent, macro_config):
        super().__init__(parent)
        self.parent = parent
        self.macro_config = macro_config
        self.title("Macro Editor")
        self.geometry("600x700")
        self.create_widgets()

    def create_widgets(self):
        instruction_label = ttk.Label(self,
                                      text="Fill in the details for the macro. Use 'Add Action' to set up the action sequence.")
        instruction_label.grid(row=0, column=0, columnspan=3, padx=10, pady=10)

        # Name
        ttk.Label(self, text="Macro Name:").grid(row=1, column=0, padx=10, pady=5, sticky='e')
        self.name_entry = ttk.Entry(self, width=30)
        self.name_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky='w')

        # Hotkey
        ttk.Label(self, text="Hotkey (optional):").grid(row=2, column=0, padx=10, pady=5, sticky='e')
        self.hotkey_entry = ttk.Entry(self, width=30)
        self.hotkey_entry.grid(row=2, column=1, columnspan=2, padx=10, pady=5, sticky='w')

        # Dose-Counting Macro Checkbox
        self.is_dose_macro_var = tk.BooleanVar(value=False)
        self.is_dose_macro_check = ttk.Checkbutton(self, text="Enable Dose-Counting", variable=self.is_dose_macro_var,
                                                   command=self.toggle_dose_count_entry)
        self.is_dose_macro_check.grid(row=3, column=0, columnspan=3, padx=10, pady=5, sticky='w')

        # Number of Doses Entry (only visible if dose-counting is enabled)
        ttk.Label(self, text="Number of Doses:").grid(row=4, column=0, padx=10, pady=5, sticky='e')
        self.dose_count_entry = ttk.Entry(self, width=10)
        self.dose_count_entry.grid(row=4, column=1, padx=10, pady=5, sticky='w')
        self.dose_count_entry.config(state='disabled')  # Initially disabled

        # Looping Macro Checkbox
        self.is_loop_macro_var = tk.BooleanVar(value=False)
        self.is_loop_macro_check = ttk.Checkbutton(self, text="Enable Looping", variable=self.is_loop_macro_var,
                                                   command=self.toggle_loop_count_entry)
        self.is_loop_macro_check.grid(row=5, column=0, columnspan=3, padx=10, pady=5, sticky='w')

        # Number of Loops Entry
        ttk.Label(self, text="Number of Loops:").grid(row=6, column=0, padx=10, pady=5, sticky='e')
        self.loop_count_entry = ttk.Entry(self, width=10)
        self.loop_count_entry.grid(row=6, column=1, padx=10, pady=5, sticky='w')
        self.loop_count_entry.config(state='disabled')  # Initially disabled

        # Actions List
        ttk.Label(self, text="Actions:").grid(row=7, column=0, padx=10, pady=5, sticky='ne')
        self.actions_listbox = tk.Listbox(self, height=15, width=50)
        self.actions_listbox.grid(row=7, column=1, padx=10, pady=5, sticky='w')

        # Bind double-click event
        self.actions_listbox.bind('<Double-1>', self.on_action_double_click)

        # Buttons for actions
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=7, column=2, padx=10, pady=5, sticky='n')

        add_action_btn = ttk.Button(btn_frame, text="Add Action", command=self.add_action)
        add_action_btn.pack(side='top', padx=5, pady=2)

        edit_action_btn = ttk.Button(btn_frame, text="Edit Action", command=self.edit_action)
        edit_action_btn.pack(side='top', padx=5, pady=2)

        del_action_btn = ttk.Button(btn_frame, text="Delete Action", command=self.delete_action)
        del_action_btn.pack(side='top', padx=5, pady=2)

        move_up_btn = ttk.Button(btn_frame, text="Move Up", command=self.move_action_up)
        move_up_btn.pack(side='top', padx=5, pady=2)

        move_down_btn = ttk.Button(btn_frame, text="Move Down", command=self.move_action_down)
        move_down_btn.pack(side='top', padx=5, pady=2)

        # Scheduling Checkbox
        self.is_scheduled_var = tk.BooleanVar(value=False)
        self.is_scheduled_check = ttk.Checkbutton(self, text="Enable Scheduling", variable=self.is_scheduled_var,
                                                  command=self.toggle_schedule_entry)
        self.is_scheduled_check.grid(row=8, column=0, columnspan=3, padx=10, pady=5, sticky='w')

        # Schedule Interval Entry
        ttk.Label(self, text="Schedule Interval:").grid(row=9, column=0, padx=10, pady=5, sticky='e')
        self.schedule_interval_entry = ttk.Entry(self, width=20)
        self.schedule_interval_entry.grid(row=9, column=1, padx=10, pady=5, sticky='w')
        self.schedule_interval_entry.config(state='disabled')  # Initially disabled

        # Save Button
        save_btn = ttk.Button(self, text="Save Macro", command=self.save_macro)
        save_btn.grid(row=10, column=0, columnspan=3, pady=20)

        self.actions_list = []  # List to store actions

        # Load macro data if editing
        if self.macro_config:
            self.load_macro_data()

    def on_action_double_click(self, event):
        self.edit_action()

    def toggle_dose_count_entry(self):
        if self.is_dose_macro_var.get():
            self.dose_count_entry.config(state='normal')
            self.dose_count_entry.focus()
        else:
            self.dose_count_entry.delete(0, tk.END)
            self.dose_count_entry.config(state='disabled')

    def toggle_loop_count_entry(self):
        if self.is_loop_macro_var.get():
            self.loop_count_entry.config(state='normal')
            self.loop_count_entry.focus()
        else:
            self.loop_count_entry.delete(0, tk.END)
            self.loop_count_entry.config(state='disabled')

    def toggle_schedule_entry(self):
        if self.is_scheduled_var.get():
            self.schedule_interval_entry.config(state='normal')
            self.schedule_interval_entry.focus()
        else:
            self.schedule_interval_entry.delete(0, tk.END)
            self.schedule_interval_entry.config(state='disabled')

    def get_action_description(self, action):
        action_type = action.get('type')
        annotation = action.get('annotation', '')
        if action_type == 'press_panel_key':
            return f"Press Panel Key '{action.get('key')}' {f'({annotation})' if annotation else ''}"
        elif action_type == 'press_specific_panel_key':
            if action.get('panel') == 'Custom':
                return f"Press Specific Panel Key '{action.get('custom_key')}' {f'({annotation})' if annotation else ''}"
            else:
                return f"Press Specific Panel Key '{action.get('panel')}' {f'({annotation})' if annotation else ''}"
        elif action_type == 'click':
            if action.get('use_saved_target', False):
                return f"Click at Saved Target Position {f'({annotation})' if annotation else ''}"
            else:
                positions = action.get('positions', [])
                modifiers = action.get('modifiers', [])
                return f"Click at Positions {positions} with modifiers {modifiers} {f'({annotation})' if annotation else ''}"
        elif action_type == 'return_mouse':
            return "Return Mouse to Original Position" + (
                " and Click" if action.get('click_after_return', False) else "") + (
                       f" ({annotation})" if annotation else "")
        elif action_type == 'wait':
            return f"Wait for {action.get('duration')} seconds {f'({annotation})' if annotation else ''}"
        else:
            return "Unknown Action"

    def load_macro_data(self):
        self.name_entry.insert(0, self.macro_config['name'])
        self.hotkey_entry.insert(0, self.macro_config.get('hotkey', ''))
        if self.macro_config.get('is_dose_macro', False):
            self.is_dose_macro_var.set(True)
            self.dose_count_entry.config(state='normal')
            self.dose_count_entry.insert(0, str(self.macro_config.get('dose_count', 4)))
        if self.macro_config.get('is_loop_macro', False):
            self.is_loop_macro_var.set(True)
            self.loop_count_entry.config(state='normal')
            self.loop_count_entry.insert(0, str(self.macro_config.get('loop_count', 1)))
        if self.macro_config.get('is_scheduled', False):
            self.is_scheduled_var.set(True)
            self.schedule_interval_entry.config(state='normal')
            schedule_interval = self.macro_config.get('schedule_interval', 0)
            self.schedule_interval_entry.insert(0, self.format_time_string(schedule_interval))
        self.actions_list = self.macro_config.get('actions', [])
        for action in self.actions_list:
            self.actions_listbox.insert('end', self.get_action_description(action))

    def add_action(self):
        ActionEditor(self, None)

    def edit_action(self):
        selected = self.actions_listbox.curselection()
        if selected:
            index = selected[0]
            action = self.actions_list[index]
            ActionEditor(self, action, index)
        else:
            messagebox.showwarning("No Selection", "Please select an action to edit.")

    def delete_action(self):
        selected = self.actions_listbox.curselection()
        if selected:
            index = selected[0]
            self.actions_list.pop(index)
            self.actions_listbox.delete(index)
        else:
            messagebox.showwarning("No Selection", "Please select an action to delete.")

    def move_action_up(self):
        selected = self.actions_listbox.curselection()
        if selected and selected[0] > 0:
            index = selected[0]
            self.actions_list[index - 1], self.actions_list[index] = self.actions_list[index], self.actions_list[
                index - 1]
            action_text = self.actions_listbox.get(index)
            self.actions_listbox.delete(index)
            self.actions_listbox.insert(index - 1, action_text)
            self.actions_listbox.selection_set(index - 1)
        else:
            messagebox.showwarning("Cannot Move", "Cannot move the selected action up.")

    def move_action_down(self):
        selected = self.actions_listbox.curselection()
        if selected and selected[0] < len(self.actions_list) - 1:
            index = selected[0]
            self.actions_list[index + 1], self.actions_list[index] = self.actions_list[index], self.actions_list[
                index + 1]
            action_text = self.actions_listbox.get(index)
            self.actions_listbox.delete(index)
            self.actions_listbox.insert(index + 1, action_text)
            self.actions_listbox.selection_set(index + 1)
        else:
            messagebox.showwarning("Cannot Move", "Cannot move the selected action down.")

    def save_macro(self):
        name = self.name_entry.get().strip()
        hotkey = self.hotkey_entry.get().strip()
        is_dose_macro = self.is_dose_macro_var.get()
        dose_count = None

        is_loop_macro = self.is_loop_macro_var.get()
        loop_count = None

        is_scheduled = self.is_scheduled_var.get()
        schedule_interval = None

        if is_dose_macro:
            dose_count_str = self.dose_count_entry.get().strip()
            if not dose_count_str.isdigit() or int(dose_count_str) <= 0:
                messagebox.showerror("Invalid Input", "Number of Doses must be a positive integer.")
                return
            dose_count = int(dose_count_str)

        if is_loop_macro:
            loop_count_str = self.loop_count_entry.get().strip()
            if not loop_count_str.isdigit() or int(loop_count_str) <= 0:
                messagebox.showerror("Invalid Input", "Number of Loops must be a positive integer.")
                return
            loop_count = int(loop_count_str)

        if is_scheduled:
            schedule_interval_str = self.schedule_interval_entry.get().strip()
            try:
                schedule_interval = self.parse_time_string(schedule_interval_str)
            except ValueError:
                messagebox.showerror("Invalid Input",
                                     "Schedule Interval must be a valid time duration (e.g., '30s', '5m1s').")
                return

        if not name:
            messagebox.showerror("Missing Information", "Please fill in the Macro Name.")
            return

        # Check for unique macro name
        existing_names = [m['name'] for m in self.parent.config['macros']]
        if self.macro_config:
            # If editing, remove the current macro's name from the list to allow renaming to itself
            existing_names.remove(self.macro_config['name'])
        if name in existing_names:
            messagebox.showerror("Duplicate Name",
                                 "A macro with this name already exists. Please choose a different name.")
            return

        new_macro = {
            "name": name,
            "hotkey": hotkey if hotkey else None,
            "actions": self.actions_list,
            "is_dose_macro": is_dose_macro,
            "is_loop_macro": is_loop_macro,
            "is_scheduled": is_scheduled
        }

        if is_dose_macro:
            new_macro["dose_count"] = dose_count
            new_macro["call_count"] = self.macro_config.get("call_count", 0) if self.macro_config else 0
            new_macro["current_position_index"] = self.macro_config.get("current_position_index",
                                                                        0) if self.macro_config else 0
        else:
            # Ensure call_count and current_position_index are set to 0 for consistency
            new_macro["call_count"] = 0
            new_macro["current_position_index"] = 0

        if is_loop_macro:
            new_macro["loop_count"] = loop_count if is_loop_macro else 1
        else:
            new_macro["loop_count"] = 1

        if is_scheduled:
            new_macro["schedule_interval"] = schedule_interval

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
            call_count = macro.get('call_count', 0) if macro.get('is_dose_macro', False) else ""
            reset_text = 'Reset' if macro.get('is_dose_macro', False) else ""
            scheduled = 'Yes' if macro.get('is_scheduled', False) else 'No'
            active = 'No'
            self.parent.macro_list.insert('', 'end',
                                          values=(macro['name'], macro.get('hotkey', ''), scheduled, active, doses, call_count,
                                                  reset_text))
        self.parent.register_hotkeys()
        self.parent.log(f"Macro '{name}' has been saved.")
        self.destroy()

    def parse_time_string(self, time_str):
        import re
        pattern = r'(\d+\.?\d*)\s*([smhd])'
        matches = re.findall(pattern, time_str.lower())
        if not matches:
            raise ValueError("Invalid time string")
        total_seconds = 0
        for value, unit in matches:
            value = float(value)
            if unit == 's':
                total_seconds += value
            elif unit == 'm':
                total_seconds += value * 60
            elif unit == 'h':
                total_seconds += value * 3600
            elif unit == 'd':
                total_seconds += value * 86400
            else:
                raise ValueError("Invalid time unit")
        return total_seconds

    def format_time_string(self, total_seconds):
        # Format total_seconds into a string like '5m1s', '2h'
        seconds = int(total_seconds)
        time_str = ''
        if seconds >= 86400:
            days = seconds // 86400
            time_str += f'{days}d'
            seconds %= 86400
        if seconds >= 3600:
            hours = seconds // 3600
            time_str += f'{hours}h'
            seconds %= 3600
        if seconds >= 60:
            minutes = seconds // 60
            time_str += f'{minutes}m'
            seconds %= 60
        if seconds > 0:
            time_str += f'{seconds}s'
        if not time_str:
            time_str = '0s'
        return time_str


# ActionEditor Class
class ActionEditor(tk.Toplevel):
    def __init__(self, parent, action=None, index=None):
        super().__init__(parent)
        self.parent = parent
        self.action = action
        self.index = index
        self.title("Action Editor")
        self.geometry("500x500")
        self.create_widgets()

    def create_widgets(self):
        # Action Type
        ttk.Label(self, text="Action Type:").grid(row=0, column=0, padx=10, pady=5, sticky='e')
        self.action_types = ["Press Panel Key", "Press Specific Panel Key", "Click", "Return Mouse", "Wait"]
        self.selected_action_type = tk.StringVar()
        self.selected_action_type.set(self.action_types[0])
        self.action_type_menu = ttk.OptionMenu(self, self.selected_action_type, self.action_types[0],
                                               *self.action_types, command=self.update_action_fields)
        self.action_type_menu.grid(row=0, column=1, padx=10, pady=5, sticky='w')

        # Parameters Frame
        self.params_frame = ttk.Frame(self)
        self.params_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5)

        # Annotation
        ttk.Label(self, text="Annotation:").grid(row=2, column=0, padx=10, pady=5, sticky='e')
        self.annotation_entry = ttk.Entry(self, width=50)
        self.annotation_entry.grid(row=2, column=1, columnspan=2, padx=10, pady=5, sticky='w')

        # Save Button
        save_btn = ttk.Button(self, text="Save Action", command=self.save_action)
        save_btn.grid(row=3, column=0, columnspan=2, pady=20)

        if self.action:
            # Load action data
            self.selected_action_type.set(self.action.get('type').replace('_', ' ').title())
            self.update_action_fields(None)
            # Populate fields based on action
            self.load_action_data()
        else:
            self.update_action_fields(None)

    def update_action_fields(self, *args):
        # Clear the params_frame
        for widget in self.params_frame.winfo_children():
            widget.destroy()

        action_type = self.selected_action_type.get()
        if action_type == "Press Panel Key":
            ttk.Label(self.params_frame, text="Key:").grid(row=0, column=0, padx=5, pady=5)
            self.key_entry = ttk.Entry(self.params_frame)
            self.key_entry.grid(row=0, column=1, padx=5, pady=5)
        elif action_type == "Press Specific Panel Key":
            ttk.Label(self.params_frame, text="Panel:").grid(row=0, column=0, padx=5, pady=5)
            self.panel_options = ["Inventory", "Prayer", "Spells", "Custom"]
            self.selected_panel = tk.StringVar()
            self.selected_panel.set("Inventory")
            self.panel_menu = ttk.OptionMenu(self.params_frame, self.selected_panel, self.panel_options[0],
                                             *self.panel_options, command=self.toggle_custom_panel_entry)
            self.panel_menu.grid(row=0, column=1, padx=5, pady=5)
            # Custom panel key entry
            self.custom_panel_key_entry = ttk.Entry(self.params_frame)
            self.custom_panel_key_entry.grid(row=1, column=1, padx=5, pady=5)
            self.custom_panel_key_entry.grid_remove()
        elif action_type == "Click":
            self.use_saved_target_var = tk.BooleanVar()
            self.use_saved_target_check = ttk.Checkbutton(self.params_frame, text="Use Saved Target Position",
                                                          variable=self.use_saved_target_var)
            self.use_saved_target_check.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky='w')

            ttk.Label(self.params_frame, text="Positions:").grid(row=1, column=0, padx=5, pady=5, sticky='ne')
            self.positions_listbox = tk.Listbox(self.params_frame, height=5, width=30)
            self.positions_listbox.grid(row=1, column=1, padx=5, pady=5, sticky='w')

            btn_frame = ttk.Frame(self.params_frame)
            btn_frame.grid(row=1, column=2, padx=5, pady=5, sticky='n')

            add_pos_btn = ttk.Button(btn_frame, text="Add Position", command=self.add_click_position)
            add_pos_btn.pack(side='top', padx=5, pady=2)

            del_pos_btn = ttk.Button(btn_frame, text="Delete Position", command=self.delete_click_position)
            del_pos_btn.pack(side='top', padx=5, pady=2)

            # Modifiers
            ttk.Label(self.params_frame, text="Modifiers:").grid(row=2, column=0, padx=5, pady=5, sticky='e')
            self.shift_var = tk.BooleanVar()
            self.ctrl_var = tk.BooleanVar()
            self.alt_var = tk.BooleanVar()
            self.shift_check = ttk.Checkbutton(self.params_frame, text="Shift", variable=self.shift_var)
            self.shift_check.grid(row=2, column=1, padx=5, pady=5, sticky='w')
            self.ctrl_check = ttk.Checkbutton(self.params_frame, text="Ctrl", variable=self.ctrl_var)
            self.ctrl_check.grid(row=2, column=1, padx=5, pady=5)
            self.alt_check = ttk.Checkbutton(self.params_frame, text="Alt", variable=self.alt_var)
            self.alt_check.grid(row=2, column=1, padx=5, pady=5, sticky='e')
        elif action_type == "Return Mouse":
            self.click_after_return_var = tk.BooleanVar()
            self.click_after_return_check = ttk.Checkbutton(self.params_frame, text="Click After Return",
                                                            variable=self.click_after_return_var)
            self.click_after_return_check.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky='w')
        elif action_type == "Wait":
            self.use_custom_wait_var = tk.BooleanVar(value=False)
            self.use_custom_wait_check = ttk.Checkbutton(self.params_frame, text="Use Custom Wait Time",
                                                         variable=self.use_custom_wait_var,
                                                         command=self.toggle_wait_duration_entry)
            self.use_custom_wait_check.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky='w')

            self.wait_time_options = list(self.parent.parent.wait_times.keys())
            self.selected_wait_time = tk.StringVar()
            self.selected_wait_time.set(self.wait_time_options[0])

            self.wait_time_menu = ttk.OptionMenu(self.params_frame, self.selected_wait_time, self.wait_time_options[0],
                                                 *self.wait_time_options)
            self.wait_time_menu.grid(row=1, column=1, padx=5, pady=5, sticky='w')
            self.wait_time_menu.grid_remove()

            ttk.Label(self.params_frame, text="Duration (s):").grid(row=1, column=0, padx=5, pady=5)
            self.duration_entry = ttk.Entry(self.params_frame)
            self.duration_entry.grid(row=1, column=1, padx=5, pady=5)

            self.toggle_wait_duration_entry()
        # No additional parameters for other actions

    def toggle_custom_panel_entry(self, *args):
        if self.selected_panel.get() == 'Custom':
            self.custom_panel_key_entry.grid()
        else:
            self.custom_panel_key_entry.grid_remove()

    def toggle_wait_duration_entry(self):
        if self.use_custom_wait_var.get():
            self.duration_entry.grid_remove()
            self.wait_time_menu.grid()
        else:
            self.wait_time_menu.grid_remove()
            self.duration_entry.grid()

    def load_action_data(self):
        action_type = self.action.get('type')
        if action_type == 'press_panel_key':
            self.key_entry.insert(0, self.action.get('key', ''))
        elif action_type == 'press_specific_panel_key':
            panel = self.action.get('panel', 'Inventory')
            self.selected_panel.set(panel)
            if panel == 'Custom':
                self.custom_panel_key_entry.insert(0, self.action.get('custom_key', ''))
                self.custom_panel_key_entry.grid()
            else:
                self.custom_panel_key_entry.grid_remove()
        elif action_type == 'click':
            self.use_saved_target_var.set(self.action.get('use_saved_target', False))
            positions = self.action.get('positions', [])
            for pos in positions:
                self.positions_listbox.insert('end', str(pos))
            modifiers = self.action.get('modifiers', [])
            self.shift_var.set('Shift' in modifiers)
            self.ctrl_var.set('Ctrl' in modifiers)
            self.alt_var.set('Alt' in modifiers)
        elif action_type == 'return_mouse':
            self.click_after_return_var.set(self.action.get('click_after_return', False))
        elif action_type == 'wait':
            duration = self.action.get('duration', 0)
            if isinstance(duration, str):
                self.use_custom_wait_var.set(True)
                self.selected_wait_time.set(duration)
                self.toggle_wait_duration_entry()
            else:
                self.duration_entry.insert(0, str(duration))
        # Load annotation
        self.annotation_entry.insert(0, self.action.get('annotation', ''))

    def add_click_position(self):
        self.info_label = ttk.Label(self, text="Move the mouse to the desired position and press 's' to set.")
        self.info_label.grid(row=4, column=0, columnspan=2, padx=10, pady=5)

        self.wait_for_position()

    def wait_for_position(self):
        def on_press(key):
            try:
                if key.char.lower() == 's':
                    x, y = pyautogui.position()
                    self.positions_listbox.insert('end', str((x, y)))
                    listener.stop()
                    self.info_label.destroy()
                elif key.char.lower() == 'c':
                    listener.stop()
                    self.info_label.destroy()
            except AttributeError:
                pass

        listener = keyboard.Listener(on_press=on_press)
        listener.start()

    def delete_click_position(self):
        selected = self.positions_listbox.curselection()
        if selected:
            self.positions_listbox.delete(selected)

    def save_action(self):
        action_type = self.selected_action_type.get()
        action = {}
        if action_type == "Press Panel Key":
            action = {
                'type': 'press_panel_key',
                'key': self.key_entry.get()
            }
        elif action_type == "Press Specific Panel Key":
            panel = self.selected_panel.get()
            if panel == 'Custom':
                custom_key = self.custom_panel_key_entry.get()
                if not custom_key:
                    messagebox.showerror("Missing Information", "Please enter a custom panel key.")
                    return
                action = {
                    'type': 'press_specific_panel_key',
                    'panel': 'Custom',
                    'custom_key': custom_key
                }
            else:
                action = {
                    'type': 'press_specific_panel_key',
                    'panel': panel
                }
        elif action_type == "Click":
            use_saved_target = self.use_saved_target_var.get()
            positions = []
            if not use_saved_target:
                try:
                    positions = [ast.literal_eval(pos) for pos in self.positions_listbox.get(0, 'end')]
                except (ValueError, SyntaxError):
                    messagebox.showerror("Invalid Positions", "Click positions must be in the format (x, y).")
                    return
            modifiers = []
            if self.shift_var.get():
                modifiers.append('Shift')
            if self.ctrl_var.get():
                modifiers.append('Ctrl')
            if self.alt_var.get():
                modifiers.append('Alt')
            action = {
                'type': 'click',
                'use_saved_target': use_saved_target,
                'positions': positions,
                'modifiers': modifiers
            }
        elif action_type == "Return Mouse":
            action = {
                'type': 'return_mouse',
                'click_after_return': self.click_after_return_var.get()
            }
        elif action_type == "Wait":
            if self.use_custom_wait_var.get():
                duration = self.selected_wait_time.get()
            else:
                try:
                    duration = float(self.duration_entry.get())
                except ValueError:
                    messagebox.showerror("Invalid Input", "Duration must be a number.")
                    return
            action = {
                'type': 'wait',
                'duration': duration
            }
        else:
            messagebox.showerror("Invalid Action", "Unknown action type.")
            return

        # Save annotation
        annotation = self.annotation_entry.get().strip()
        if annotation:
            action['annotation'] = annotation

        # Save the action to parent
        if self.action is not None:
            # Editing existing action
            self.parent.actions_list[self.index] = action
            self.parent.actions_listbox.delete(self.index)
            self.parent.actions_listbox.insert(self.index, self.parent.get_action_description(action))
        else:
            # Adding new action
            self.parent.actions_list.append(action)
            self.parent.actions_listbox.insert('end', self.parent.get_action_description(action))
        self.destroy()


# Main Execution
if __name__ == "__main__":
    app = MacroApp()
    # Run the GUI in the main thread
    app.mainloop()
