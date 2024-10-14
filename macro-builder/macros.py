import ast
import json
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

import pyautogui
from pynput import keyboard


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
                    if isinstance(action, Macro):
                        action.toggle()
                    elif callable(action):
                        threading.Thread(target=action).start()

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
        self.actions = config["actions"]  # List of actions
        self.is_dose_macro = config.get("is_dose_macro", False)
        self.dose_count = config.get("dose_count", 4) if self.is_dose_macro else None

        self.call_count = config.get("call_count", 0)
        self.current_position_index = config.get("current_position_index", 0)

        self.is_loop_macro = config.get("is_loop_macro", False)
        self.loop_count = config.get("loop_count", 1) if self.is_loop_macro else 1
        self.current_loop_index = 0

        self.schedule = config.get("schedule", None)
        self.repeat_interval = config.get("repeat_interval", None)
        self.app = app

        self.running = False  # Flag to indicate if the macro is running
        self.context = None  # Execution context for shared state

    def toggle(self):
        if not self.running:
            self.execute()
        else:
            self.stop()

    def stop(self):
        if self.context:
            self.context['should_stop'] = True

    def execute(self, threaded=True):
        # Add the macro to the task queue
        self.app.task_queue.put(self)

    def run_macro(self):
        if not self.app.macros_enabled:
            return
        if self.running:
            return
        self.running = True
        try:
            if self.is_loop_macro and self.loop_count == -1:
                infinite_loop = True
            else:
                infinite_loop = False

            total_loops = self.loop_count if self.is_loop_macro else 1
            self.current_loop_index = 0
            start_time = time.time()
            total_log = []

            # Initialize execution context
            if not self.context:
                self.context = {'should_stop': False}

            # Initialize local state for this macro
            if not hasattr(self, 'local_state') or self.local_state is None:
                self.local_state = {'call_count': self.call_count,
                                    'current_position_index': self.current_position_index}

            while infinite_loop or self.current_loop_index < total_loops:
                if self.context['should_stop']:
                    break
                if not self.app.macros_enabled:
                    break

                self.current_loop_index += 1
                loop_start_time = time.time()
                log = []

                original_position = pyautogui.position()
                log.append(f"Original mouse position: {original_position}")

                # Run actions with dose counting
                self.run_actions(self.actions, original_position, log, self.context, local_state=self.local_state)

                loop_end_time = time.time()
                loop_total_time = loop_end_time - loop_start_time
                total_log.append(
                    f"Loop {self.current_loop_index}/{total_loops} executed in {loop_total_time:.3f} seconds")
                total_log.extend(log)

                # Update ETA tracker
                if self.is_loop_macro and not infinite_loop:
                    loops_remaining = total_loops - self.current_loop_index
                    average_time_per_loop = (loop_end_time - start_time) / self.current_loop_index
                    estimated_time_remaining = loops_remaining * average_time_per_loop
                    self.app.after(0, self.app.update_eta_tracker, estimated_time_remaining)

            end_time = time.time()
            total_time = end_time - start_time

            self.app.after(0, self.app.log_macro_execution, self.name, total_log, total_time)
            self.current_loop_index = 0
            if self.is_loop_macro:
                self.app.after(0, self.app.reset_eta_tracker)

            # Update the macro's global call count and position index after execution
            if self.is_dose_macro:
                self.call_count = self.local_state['call_count']
                self.current_position_index = self.local_state['current_position_index']
                self.app.update_macro_call_count(self)
                self.app.config_save_required = True
        finally:
            self.running = False
            self.context = None  # Clear the context after execution
            self.local_state = None  # Clear local state

    def run_actions(self, actions, original_position, log, context, local_state=None):
        if local_state is None:
            local_state = {'call_count': self.call_count,
                           'current_position_index': self.current_position_index}

        for action in actions:
            if context['should_stop']:
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

                if not positions and not use_saved_target:
                    log.append("Error: No positions specified for click action.")
                    continue

                # Press down modifiers
                for mod in modifiers:
                    pyautogui.keyDown(modifier_keys[mod])

                if use_saved_target:
                    pos = original_position
                else:
                    if self.is_dose_macro:
                        pos_index = local_state['current_position_index'] % len(positions)
                        pos = positions[pos_index]
                    else:
                        pos = positions

                if isinstance(pos[0], (list, tuple)):
                    # List of positions
                    for p in pos:
                        pyautogui.moveTo(p[0], p[1], duration=self.app.mouse_move_duration)
                        pyautogui.click()
                        # Log time for each click
                        action_end_time = time.time()
                        action_time = action_end_time - action_start_time
                        log.append(
                            f"Clicked at position {p} with modifiers {modifiers} {f'({annotation})' if annotation else ''} (took {action_time:.3f} seconds)")
                        action_start_time = time.time()
                else:
                    # Single position
                    pyautogui.moveTo(pos[0], pos[1], duration=self.app.mouse_move_duration)
                    pyautogui.click()
                    action_end_time = time.time()
                    action_time = action_end_time - action_start_time
                    log.append(
                        f"Clicked at position {pos} with modifiers {modifiers} {f'({annotation})' if annotation else ''} (took {action_time:.3f} seconds)")

                # Release modifiers
                for mod in modifiers:
                    pyautogui.keyUp(modifier_keys[mod])

                # Handle dose counting for click actions
                if self.is_dose_macro:
                    local_state['call_count'] += 1
                    if local_state['call_count'] % self.dose_count == 0:
                        local_state['current_position_index'] = (local_state[
                                                                     'current_position_index'] + 1) % self.get_total_positions()
                        log.append(f"Cycled to next position index: {local_state['current_position_index']}")

            elif action_type == 'return_mouse':
                pyautogui.moveTo(original_position[0], original_position[1], duration=self.app.mouse_move_duration)
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
                        # Initialize local state for sub_macro if not already done
                        if getattr(sub_macro, 'local_state', None) is None:
                            sub_macro.local_state = {'call_count': sub_macro.call_count,
                                                     'current_position_index': sub_macro.current_position_index}

                        sub_macro.run_actions(sub_macro.actions, original_position, log, context,
                                              local_state=sub_macro.local_state)
                        action_end_time = time.time()
                        action_time = action_end_time - action_start_time
                        log.append(
                            f"Ran sub-macro '{macro_name}' {f'({annotation})' if annotation else ''} (took {action_time:.3f} seconds)")
                else:
                    log.append(f"Macro '{macro_name}' not found.")

            else:
                log.append(f"Unknown action type: {action_type}")

    def get_total_positions(self):
        # Returns the total number of positions for dose counting
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


# Functions to load macros
def load_macros(app):
    macros = []
    for macro_config in app.config["macros"]:
        macro = Macro(macro_config, app)
        macros.append(macro)
        # Schedule the macro if it has a schedule
        if macro.schedule:
            delay = parse_time(macro.schedule)
            if delay is not None:
                repeat_interval = parse_time(macro.repeat_interval) if macro.repeat_interval else None
                app.scheduler.schedule_macro(macro, delay, repeat_interval)
            else:
                app.log(f"Invalid schedule format for macro '{macro.name}'.")
    return macros


def parse_time(time_str):
    regex = r'((?P<hours>\d+)h)?\s*((?P<minutes>\d+)m)?\s*((?P<seconds>\d+)s)?'
    match = re.match(regex, time_str.strip())
    if not match:
        return None
    time_dict = match.groupdict()
    hours = int(time_dict.get('hours') or 0)
    minutes = int(time_dict.get('minutes') or 0)
    seconds = int(time_dict.get('seconds') or 0)
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds


class TaskExecutor(threading.Thread):
    def __init__(self, task_queue, delay_between_tasks, app):
        super().__init__()
        self.task_queue = task_queue
        self.delay_between_tasks = delay_between_tasks
        self.app = app
        self.daemon = True
        self.running = True

    def run(self):
        while self.running:
            macro = self.task_queue.get()
            if macro is None:
                break
            with self.app.running_macro_lock:
                macro_thread = threading.Thread(target=macro.run_macro)
                macro_thread.start()
                macro_thread.join()
            self.task_queue.task_done()
            time.sleep(self.delay_between_tasks)

    def stop(self):
        self.running = False
        # To unblock the queue.get() call
        self.task_queue.put(None)


class Scheduler(threading.Thread):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.daemon = True
        self.scheduled_tasks = []
        self.lock = threading.Lock()
        self.running = True

    def run(self):
        while self.running:
            now = time.time()
            with self.lock:
                for scheduled_task in self.scheduled_tasks[:]:
                    if scheduled_task['next_run'] <= now:
                        macro = scheduled_task['macro']
                        self.app.task_queue.put(macro)
                        if scheduled_task['repeat_interval'] is not None:
                            scheduled_task['next_run'] = now + scheduled_task['repeat_interval']
                        else:
                            self.scheduled_tasks.remove(scheduled_task)
            time.sleep(1)

    def schedule_macro(self, macro, delay, repeat_interval=None):
        next_run = time.time() + delay
        with self.lock:
            self.scheduled_tasks.append({
                'macro': macro,
                'next_run': next_run,
                'repeat_interval': repeat_interval
            })

    def stop(self):
        self.running = False


# MacroApp Class
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

        # Initialize HotkeyManager
        self.hotkey_manager = HotkeyManager(self)

        # Initialize macros
        self.initialize_macros()

        # Set pyautogui pause to 0.025 to eliminate default delay
        pyautogui.PAUSE = 0.025

        # Configurable delay between tasks
        self.task_execution_delay = self.config.get('task_execution_delay', 0.1)
        # Task queue and executor
        self.task_queue = queue.Queue()
        self.running_macro_lock = threading.Lock()
        self.task_executor = TaskExecutor(self.task_queue, self.task_execution_delay, self)
        self.task_executor.start()

        # Scheduler
        self.scheduler = Scheduler(self)
        self.scheduler.start()

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
                "task_execution_delay": 0.1
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
        self.log_text = tk.Text(self, height=15)
        self.log_text.pack(expand=True, fill='both', side='bottom')
        # Configure tags for coloring
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
        # Treeview to display macros
        self.macro_list = ttk.Treeview(self.macro_frame,
                                       columns=('Name', 'Hotkey', 'Doses', 'Call Count', 'Reset'),
                                       show='headings')
        self.macro_list.heading('Name', text='Name')
        self.macro_list.heading('Hotkey', text='Hotkey')
        self.macro_list.heading('Doses', text='Doses')  # Indicates dose-counting macros
        self.macro_list.heading('Call Count', text='Call Count')
        self.macro_list.heading('Reset', text='Reset')
        self.macro_list.pack(expand=True, fill='both')

        # Populate the treeview with existing macros
        for macro in self.config['macros']:
            doses = macro['dose_count'] if macro.get('is_dose_macro', False) else "N/A"
            call_count = macro.get('call_count', 0) if macro.get('is_dose_macro', False) else ""
            reset_text = 'Reset' if macro.get('is_dose_macro', False) else ""
            self.macro_list.insert('', 'end',
                                   values=(macro['name'], macro['hotkey'], doses, call_count, reset_text))

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

        copy_macro_btn = ttk.Button(btn_frame, text="Copy Macro", command=self.copy_macro)
        copy_macro_btn.pack(side='left', padx=5)

        del_macro_btn = ttk.Button(btn_frame, text="Delete Macro", command=self.delete_macro)
        del_macro_btn.pack(side='left', padx=5)

    def on_macro_double_click(self, event):
        self.edit_macro()

    def on_macro_click(self, event):
        item = self.macro_list.identify_row(event.y)
        column = self.macro_list.identify_column(event.x)
        if not item:
            return
        if column == '#5':  # Assuming 'Reset' is the 5th column
            values = self.macro_list.item(item, 'values')
            macro_name = values[0]
            macro = next((m for m in self.macro_list_data if m.name == macro_name), None)
            if macro and macro.is_dose_macro:
                macro.reset_call_count()
                self.save_config()
                self.log(f"Call count for macro '{macro_name}' has been reset.")
                self.update_macro_call_count(macro)

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

        # Delay Between Tasks
        ttk.Label(self.settings_frame, text="Delay Between Tasks (s):").grid(row=row, column=0, sticky='e', padx=5,
                                                                             pady=5)
        self.task_execution_delay_entry = ttk.Entry(self.settings_frame)
        self.task_execution_delay_entry.insert(0, str(self.task_execution_delay))
        self.task_execution_delay_entry.grid(row=row, column=1, padx=5, pady=5)
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
        # Insert messages into log_text widget with appropriate formatting and coloring

        # Start with a header
        self.log_text.insert(tk.END, f"Macro '{macro_name}' executed in {total_time:.3f} seconds\n", 'macro_name')

        # Insert each log message
        for msg in log_messages:
            self.log_text.insert(tk.END, f"    {msg}\n", 'action')

        # Scroll to end
        self.log_text.see(tk.END)

    def save_settings(self):
        try:
            self.interface_switch_time = float(self.interface_switch_time_entry.get())
            self.action_registration_time_min = float(self.action_time_min_entry.get())
            self.action_registration_time_max = float(self.action_time_max_entry.get())
            self.mouse_move_duration = float(self.mouse_move_duration_entry.get())

            self.task_execution_delay = float(self.task_execution_delay_entry.get())
            self.task_executor.delay_between_tasks = self.task_execution_delay
            self.config['task_execution_delay'] = self.task_execution_delay

            self.panel_key = self.panel_key_entry.get()
            self.inventory_key = self.inventory_key_entry.get()
            self.prayer_key = self.prayer_key_entry.get()
            self.spells_key = self.spells_key_entry.get()

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

    def copy_macro(self):
        selected_item = self.macro_list.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a macro to copy.")
            return
        values = self.macro_list.item(selected_item, 'values')
        macro_name = values[0]
        # Find the corresponding macro in config
        macro_config = next((m for m in self.config['macros'] if m['name'] == macro_name), None)
        if not macro_config:
            messagebox.showerror("Error", "Selected macro not found.")
            return
        # Create a deep copy of the macro_config
        import copy
        new_macro_config = copy.deepcopy(macro_config)
        # Modify the name to indicate it's a copy
        new_macro_config['name'] = macro_name + " Copy"
        # Open the MacroEditor with this new macro_config
        MacroEditor(self, new_macro_config, is_copy=True)

    def toggle_macros(self):
        self.macros_enabled = not self.macros_enabled
        if self.macros_enabled:
            self.toggle_macros_button.config(text="Disable Macros")
            self.log("Macros enabled.")
        else:
            self.toggle_macros_button.config(text="Enable Macros")
            self.log("Macros disabled via killswitch.")

    def update_macro_call_count(self, macro):
        # Find the macro in the treeview and update its 'Doses' and 'Call Count' columns
        for item in self.macro_list.get_children():
            values = self.macro_list.item(item, 'values')
            if values[0] == macro.name:
                doses = macro.dose_count if macro.is_dose_macro else "N/A"
                call_count = macro.call_count if macro.is_dose_macro else ""
                reset_text = 'Reset' if macro.is_dose_macro else ""
                self.macro_list.item(item, values=(macro.name, macro.hotkey, doses, call_count, reset_text))
                break

    def update_eta_tracker(self, estimated_time_remaining):
        minutes, seconds = divmod(int(estimated_time_remaining), 60)
        time_str = f"{minutes}m {seconds}s remaining"
        self.eta_label.config(text=f"Estimated Time Remaining: {time_str}")

    def reset_eta_tracker(self):
        self.eta_label.config(text="Estimated Time Remaining: N/A")


# MacroEditor Class
class MacroEditor(tk.Toplevel):
    def __init__(self, parent, macro_config, is_copy=False):
        super().__init__(parent)
        self.parent = parent
        self.macro_config = macro_config
        self.is_copy = is_copy
        self.title("Macro Editor")
        self.geometry("600x750")
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
        ttk.Label(self, text="Hotkey:").grid(row=2, column=0, padx=10, pady=5, sticky='e')
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
        ttk.Label(self, text="Number of Loops (-1 for infinite):").grid(row=6, column=0, padx=10, pady=5, sticky='e')
        self.loop_count_entry = ttk.Entry(self, width=10)
        self.loop_count_entry.grid(row=6, column=1, padx=10, pady=5, sticky='w')
        self.loop_count_entry.config(state='disabled')  # Initially disabled

        # Scheduler Options
        self.schedule_var = tk.BooleanVar(value=False)
        self.schedule_check = ttk.Checkbutton(self, text="Enable Scheduler", variable=self.schedule_var,
                                              command=self.toggle_schedule_entries)
        self.schedule_check.grid(row=7, column=0, columnspan=3, padx=10, pady=5, sticky='w')

        ttk.Label(self, text="Schedule Delay (e.g., 2m5s):").grid(row=8, column=0, padx=10, pady=5, sticky='e')
        self.schedule_entry = ttk.Entry(self, width=20)
        self.schedule_entry.grid(row=8, column=1, padx=10, pady=5, sticky='w')
        self.schedule_entry.config(state='disabled')  # Initially disabled

        ttk.Label(self, text="Repeat Interval (e.g., 1h30m):").grid(row=9, column=0, padx=10, pady=5, sticky='e')
        self.repeat_interval_entry = ttk.Entry(self, width=20)
        self.repeat_interval_entry.grid(row=9, column=1, padx=10, pady=5, sticky='w')
        self.repeat_interval_entry.config(state='disabled')  # Initially disabled

        # Actions List
        ttk.Label(self, text="Actions:").grid(row=10, column=0, padx=10, pady=5, sticky='ne')
        self.actions_listbox = tk.Listbox(self, height=15, width=50)
        self.actions_listbox.grid(row=10, column=1, padx=10, pady=5, sticky='w')

        # Bind double-click event
        self.actions_listbox.bind('<Double-1>', self.on_action_double_click)

        # Buttons for actions
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=10, column=2, padx=10, pady=5, sticky='n')

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

        # Save Button
        save_btn = ttk.Button(self, text="Save Macro", command=self.save_macro)
        save_btn.grid(row=11, column=0, columnspan=3, pady=20)

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

    def toggle_schedule_entries(self):
        if self.schedule_var.get():
            self.schedule_entry.config(state='normal')
            self.repeat_interval_entry.config(state='normal')
            self.schedule_entry.focus()
        else:
            self.schedule_entry.delete(0, tk.END)
            self.repeat_interval_entry.delete(0, tk.END)
            self.schedule_entry.config(state='disabled')
            self.repeat_interval_entry.config(state='disabled')

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
        elif action_type == 'run_macro':
            return f"Run Macro '{action.get('macro_name')}' {f'({annotation})' if annotation else ''}"
        else:
            return "Unknown Action"

    def load_macro_data(self):
        self.name_entry.insert(0, self.macro_config['name'])
        self.hotkey_entry.insert(0, self.macro_config['hotkey'])
        if self.macro_config.get('is_dose_macro', False):
            self.is_dose_macro_var.set(True)
            self.dose_count_entry.config(state='normal')
            self.dose_count_entry.insert(0, str(self.macro_config.get('dose_count', 4)))
        if self.macro_config.get('is_loop_macro', False):
            self.is_loop_macro_var.set(True)
            self.loop_count_entry.config(state='normal')
            self.loop_count_entry.insert(0, str(self.macro_config.get('loop_count', 1)))
        if self.macro_config.get('schedule', None):
            self.schedule_var.set(True)
            self.schedule_entry.config(state='normal')
            self.schedule_entry.insert(0, self.macro_config.get('schedule', ''))
            self.repeat_interval_entry.config(state='normal')
            self.repeat_interval_entry.insert(0, self.macro_config.get('repeat_interval', ''))
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

        schedule = None
        repeat_interval = None

        if is_dose_macro:
            dose_count_str = self.dose_count_entry.get().strip()
            if not dose_count_str.isdigit() or int(dose_count_str) <= 0:
                messagebox.showerror("Invalid Input", "Number of Doses must be a positive integer.")
                return
            dose_count = int(dose_count_str)

        if is_loop_macro:
            loop_count_str = self.loop_count_entry.get().strip()
            try:
                loop_count = int(loop_count_str)
                if loop_count == -1:
                    pass  # Infinite loop
                elif loop_count <= 0:
                    messagebox.showerror("Invalid Input",
                                         "Number of Loops must be a positive integer or -1 for infinite looping.")
                    return
            except ValueError:
                messagebox.showerror("Invalid Input",
                                     "Number of Loops must be a positive integer or -1 for infinite looping.")
                return

        if self.schedule_var.get():
            schedule = self.schedule_entry.get().strip()
            if not schedule:
                messagebox.showerror("Invalid Input", "Please enter a valid schedule delay.")
                return
            parsed_schedule = parse_time(schedule)
            if parsed_schedule is None:
                messagebox.showerror("Invalid Format", "Schedule delay format is invalid.")
                return
            repeat_interval = self.repeat_interval_entry.get().strip()
            if repeat_interval:
                parsed_repeat = parse_time(repeat_interval)
                if parsed_repeat is None:
                    messagebox.showerror("Invalid Format", "Repeat interval format is invalid.")
                    return

        if not name or not hotkey:
            messagebox.showerror("Missing Information", "Please fill in all the required fields.")
            return

        # Check for unique macro name
        existing_names = [m['name'] for m in self.parent.config['macros']]
        if self.macro_config and not self.is_copy:
            # If editing, remove the current macro's name from the list to allow renaming to itself
            existing_names.remove(self.macro_config['name'])
        if name in existing_names:
            messagebox.showerror("Duplicate Name",
                                 "A macro with this name already exists. Please choose a different name.")
            return

        new_macro = {
            "name": name,
            "hotkey": hotkey,
            "actions": self.actions_list,
            "is_dose_macro": is_dose_macro,
            "is_loop_macro": is_loop_macro,
            "schedule": schedule,
            "repeat_interval": repeat_interval
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

        if self.macro_config and not self.is_copy:
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
            self.parent.macro_list.insert('', 'end',
                                          values=(macro['name'], macro['hotkey'], doses, call_count, reset_text))
        self.parent.register_hotkeys()
        self.parent.log(f"Macro '{name}' has been saved.")
        self.destroy()


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
        self.action_types = ["Press Panel Key", "Press Specific Panel Key", "Click", "Return Mouse", "Wait",
                             "Run Macro"]
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

            self.wait_time_menu = ttk.OptionMenu(self.params_frame, self.selected_wait_time,
                                                 self.selected_wait_time.get(),
                                                 *self.wait_time_options)
            self.wait_time_menu.grid(row=1, column=1, padx=5, pady=5, sticky='w')
            self.wait_time_menu.grid_remove()

            ttk.Label(self.params_frame, text="Duration (s):").grid(row=1, column=0, padx=5, pady=5)
            self.duration_entry = ttk.Entry(self.params_frame)
            self.duration_entry.grid(row=1, column=1, padx=5, pady=5)

            self.toggle_wait_duration_entry()
        elif action_type == "Run Macro":
            ttk.Label(self.params_frame, text="Select Macro:").grid(row=0, column=0, padx=5, pady=5)
            self.macro_names = [macro['name'] for macro in self.parent.parent.config['macros'] if
                                macro['name'] != self.parent.name_entry.get()]
            self.selected_macro_name = tk.StringVar()
            self.selected_macro_name.set(self.macro_names[0] if self.macro_names else "")
            self.macro_menu = ttk.OptionMenu(self.params_frame, self.selected_macro_name,
                                             self.selected_macro_name.get(),
                                             *self.macro_names)
            self.macro_menu.grid(row=0, column=1, padx=5, pady=5)
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
        elif action_type == 'run_macro':
            macro_name = self.action.get('macro_name', '')
            self.selected_macro_name.set(macro_name)
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
        elif action_type == "Run Macro":
            macro_name = self.selected_macro_name.get()
            if not macro_name:
                messagebox.showerror("Invalid Input", "Please select a macro to run.")
                return
            action = {
                'type': 'run_macro',
                'macro_name': macro_name
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
