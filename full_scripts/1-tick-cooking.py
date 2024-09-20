import logging
import random
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext
from tkinter import ttk
import functools
import re

import mouse  # For capturing mouse clicks
import pyautogui  # For mouse movements and clicks
from colorama import init, Fore
from pynput.keyboard import Key, Controller  # For keyboard control
from pynput import keyboard as pynput_keyboard  # For global hotkeys

# Initialize colorama
init(autoreset=True)

# Initialize pynput keyboard controller
keyboard_controller = Controller()

# Configurable positions (default values)
default_positions = {
    'bank_pos': (902, 810),
    'deposit_all_pos': (313, 954),
    'bank_item_pos': (610, 723),
    'inven_food_pos': (2188, 1244),
    'cook_food_pos': (1710, 1110)
}

# Event flags for controlling the script
start_event = threading.Event()
pause_event = threading.Event()
kill_event = threading.Event()

class KillScriptException(Exception):
    """Custom exception to handle script termination."""
    pass

class MouseController:
    def __init__(self, method='standard', interface_wait=0.5):
        self.method = method
        self.interface_wait = interface_wait  # Wait time after interactions

    def move(self, x, y, duration=0):
        if self.method == 'standard':
            pyautogui.moveTo(x, y, duration=duration)
        elif self.method == 'pyhm':
            pass  # Placeholder for pyHM implementation

    def click(self):
        if self.method == 'standard':
            pyautogui.click()
        elif self.method == 'pyhm':
            pass  # Placeholder for pyHM implementation

    def double_click(self):
        if self.method == 'standard':
            pyautogui.doubleClick()
        elif self.method == 'pyhm':
            pass  # Placeholder for pyHM implementation

class TextHandler(logging.Handler):
    """Logging handler that outputs log messages to a Tkinter Text widget."""

    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget
        # Configure text tags for colors
        self.text_widget.tag_config('RED', foreground='red')
        self.text_widget.tag_config('GREEN', foreground='green')
        self.text_widget.tag_config('YELLOW', foreground='yellow')
        self.text_widget.tag_config('BLUE', foreground='blue')
        self.text_widget.tag_config('MAGENTA', foreground='magenta')
        self.text_widget.tag_config('CYAN', foreground='cyan')
        self.text_widget.tag_config('RESET', foreground='black')
        # Regular expression to match ANSI escape sequences
        self.ANSI_ESCAPE_RE = re.compile(r'\x1b\[(\d+)(;\d+)*m')
        self.COLOR_MAP = {
            '30': 'BLACK',
            '31': 'RED',
            '32': 'GREEN',
            '33': 'YELLOW',
            '34': 'BLUE',
            '35': 'MAGENTA',
            '36': 'CYAN',
            '37': 'WHITE',
        }

    def emit(self, record):
        msg = self.format(record)
        # Remove ANSI color codes and apply tags
        pos = 0
        last_tag = 'RESET'
        for match in self.ANSI_ESCAPE_RE.finditer(msg):
            start, end = match.span()
            text = msg[pos:start]
            if text:
                self.text_widget.configure(state='normal')
                self.text_widget.insert(tk.END, text, last_tag)
                self.text_widget.configure(state='disabled')
            color_codes = match.group().strip('\x1b[').strip('m').split(';')
            last_tag = self.COLOR_MAP.get(color_codes[0], 'RESET')
            pos = end
        # Insert the remaining text
        text = msg[pos:] + '\n'
        if text:
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, text, last_tag)
            self.text_widget.configure(state='disabled')
        # Scroll to the end
        self.text_widget.see(tk.END)

def INTERACTION_WAIT(min_wait, max_wait):
    """Returns a random interaction wait time between min_wait and max_wait."""
    return random.uniform(min_wait, max_wait)

def check_events():
    """Checks for kill and pause events."""
    if kill_event.is_set():
        raise KillScriptException()
    while pause_event.is_set():
        time.sleep(0.1)

def press_key_continuously(key, stop_event, interval=0.05):
    """Presses a key continuously at specified intervals until stopped."""
    while not stop_event.is_set():
        keyboard_controller.press(key)
        keyboard_controller.release(key)
        time.sleep(interval)

def BankingProcedure(run_number, positions, interaction_wait, logger, interface_wait, mouse_controller):
    """Performs the banking procedure."""
    logger.info(Fore.CYAN + f"Starting Banking Procedure (Run {run_number})...")
    wait_time = INTERACTION_WAIT(*interaction_wait)
    check_events()
    logger.info(Fore.YELLOW + "Moving to bank position.")
    mouse_controller.move(*positions['bank_pos'], duration=wait_time)
    time.sleep(wait_time)
    mouse_controller.click()
    time.sleep(interface_wait)  # Interface wait

    wait_time = INTERACTION_WAIT(*interaction_wait)
    check_events()
    logger.info(Fore.YELLOW + "Moving to deposit all position.")
    mouse_controller.move(*positions['deposit_all_pos'], duration=wait_time)
    time.sleep(wait_time)
    mouse_controller.click()
    time.sleep(interface_wait)  # Interface wait

    wait_time = INTERACTION_WAIT(*interaction_wait)
    check_events()
    logger.info(Fore.YELLOW + "Moving to bank item position.")
    mouse_controller.move(*positions['bank_item_pos'], duration=wait_time)
    time.sleep(wait_time)
    logger.info(Fore.YELLOW + "Performing shift double-click on bank item.")
    keyboard_controller.press(Key.shift)
    mouse_controller.double_click()
    keyboard_controller.release(Key.shift)
    time.sleep(interface_wait)  # Interface wait

    logger.info(Fore.YELLOW + "Pressing ESC to close bank interface.")
    keyboard_controller.press(Key.esc)
    keyboard_controller.release(Key.esc)
    keyboard_controller.press(Key.esc)
    keyboard_controller.release(Key.esc)
    time.sleep(interface_wait)  # Interface wait

    logger.info(Fore.CYAN + f"Completed Banking Procedure (Run {run_number}).")

def CookingProcedure(run_number, cooking_repeat, tick_time, positions, interaction_wait, logger, interface_wait, mouse_controller):
    """Performs the cooking procedure."""
    logger.info(Fore.GREEN + f"Starting Cooking Procedure (Run {run_number})...")
    wait_time = INTERACTION_WAIT(*interaction_wait)
    check_events()
    logger.info(Fore.YELLOW + "Pressing 'q' to open inventory.")
    keyboard_controller.press('q')
    keyboard_controller.release('q')
    time.sleep(wait_time)
    logger.info(Fore.YELLOW + "Pressing 'w' to open cooking interface.")
    keyboard_controller.press('w')
    keyboard_controller.release('w')
    time.sleep(wait_time * 2)  # Wait for the interface to load/ todo change to interface time

    # Start pressing '1' continuously
    stop_event = threading.Event()
    key_thread = threading.Thread(target=press_key_continuously, args=('1', stop_event)) # todo fix this code running even when script is paused
    key_thread.start()

    try:
        for i in range(1, cooking_repeat + 1):
            check_events()
            start_time = time.time()

            logger.info(Fore.YELLOW + f"Cooking loop iteration {i}/{cooking_repeat}.")

            wait_time = INTERACTION_WAIT(*interaction_wait)
            mouse_controller.move(*positions['inven_food_pos'], duration=wait_time)
            time.sleep(wait_time)
            mouse_controller.click()

            wait_time = INTERACTION_WAIT(*interaction_wait)
            mouse_controller.move(*positions['cook_food_pos'], duration=wait_time)
            time.sleep(wait_time)
            mouse_controller.click()

            # Sleep for one tick/ # todo configurable to dynamically calculate this based on time elapsed since start time
            time.sleep(tick_time)

            # Ensure the loop takes between 600-700 ms
            elapsed_time = time.time() - start_time
            if elapsed_time < 0.6:
                time.sleep(0.6 - elapsed_time)
            elif elapsed_time > 0.7:
                logger.warning(Fore.RED + "Warning: Cooking loop took longer than 700 ms.")
    finally:
        # Stop the key pressing thread
        stop_event.set()
        key_thread.join()
        logger.info(Fore.GREEN + f"Completed Cooking Procedure (Run {run_number}).")

class MacroGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Macro Script")
        self.running = False

        # Input parameters with default values
        self.num_runs = tk.IntVar(value=10)
        self.cooking_repeat = tk.IntVar(value=28)
        self.tick_time = tk.DoubleVar(value=0.6)
        self.interaction_wait_min = tk.DoubleVar(value=0.02)
        self.interaction_wait_max = tk.DoubleVar(value=0.05)
        self.positions = default_positions.copy()
        self.mouse_method = tk.StringVar(value='standard')
        self.interface_wait = tk.DoubleVar(value=0.5)
        self.font_size = tk.IntVar(value=10)
        self.dark_mode = tk.BooleanVar(value=False)

        self.create_widgets()
        self.log_file = "macro_script.log"

        # Set up logging
        self.logger = logging.getLogger('MacroLogger')
        self.logger.setLevel(logging.INFO)

        # Create file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S')
        file_handler.setFormatter(file_formatter)

        # Create GUI handler
        gui_handler = TextHandler(self.log_output)
        gui_handler.setLevel(logging.INFO)
        gui_formatter = logging.Formatter('%(message)s')
        gui_handler.setFormatter(gui_formatter)

        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(gui_handler)

        # Set up global hotkeys using pynput
        self.hotkey_listener = pynput_keyboard.GlobalHotKeys({
            '<alt>+x': self.hotkey_start_script,
            '<alt>+c': self.hotkey_pause_script,
            '<f1>': self.hotkey_stop_script
        })
        self.hotkey_listener.start()

        # Bind font size change
        self.font_size.trace('w', self.update_font_size)

    def create_widgets(self):
        # Frame for input parameters
        param_frame = tk.Frame(self.root)
        param_frame.pack(pady=10)

        tk.Label(param_frame, text="Number of Runs:").grid(row=0, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.num_runs).grid(row=0, column=1)

        tk.Label(param_frame, text="Cooking Repeat:").grid(row=1, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.cooking_repeat).grid(row=1, column=1)

        tk.Label(param_frame, text="Tick Time (s):").grid(row=2, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.tick_time).grid(row=2, column=1)

        tk.Label(param_frame, text="Interaction Wait Min (s):").grid(row=3, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.interaction_wait_min).grid(row=3, column=1)

        tk.Label(param_frame, text="Interaction Wait Max (s):").grid(row=4, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.interaction_wait_max).grid(row=4, column=1)

        tk.Label(param_frame, text="Mouse Method:").grid(row=5, column=0, sticky='e')
        mouse_method_option = tk.OptionMenu(param_frame, self.mouse_method, 'standard', 'pyhm')
        mouse_method_option.grid(row=5, column=1)

        tk.Label(param_frame, text="Interface Wait (s):").grid(row=6, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.interface_wait).grid(row=6, column=1)

        tk.Label(param_frame, text="Font Size:").grid(row=7, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.font_size).grid(row=7, column=1)

        dark_mode_check = tk.Checkbutton(param_frame, text="Dark Mode", variable=self.dark_mode, command=self.toggle_dark_mode)
        dark_mode_check.grid(row=8, column=0, columnspan=2)

        # Button to configure positions
        tk.Button(param_frame, text="Configure Positions", command=self.configure_positions).grid(row=9, column=0,
                                                                                                  columnspan=2, pady=5)

        # Frame for control buttons
        control_frame = tk.Frame(self.root)
        control_frame.pack(pady=10)

        self.start_button = tk.Button(control_frame, text="Start Script", command=self.start_script)
        self.start_button.grid(row=0, column=0, padx=5)

        self.pause_button = tk.Button(control_frame, text="Pause Script", command=self.pause_script, state='disabled')
        self.pause_button.grid(row=0, column=1, padx=5)

        self.stop_button = tk.Button(control_frame, text="Stop Script", command=self.stop_script, state='disabled')
        self.stop_button.grid(row=0, column=2, padx=5)

        # Log output
        font_size = self.font_size.get()
        self.log_output = scrolledtext.ScrolledText(self.root, state='disabled', width=80, height=20, font=('TkDefaultFont', font_size))
        self.log_output.pack(pady=10)

    def update_font_size(self, *args):
        font_size = self.font_size.get()
        self.log_output.configure(font=('TkDefaultFont', font_size))

    def toggle_dark_mode(self):
        if self.dark_mode.get():
            # Set dark mode colors
            bg_color = '#2e2e2e'  # Dark gray
            fg_color = '#ffffff'  # White
            self.root.configure(bg=bg_color)
            for widget in self.root.winfo_children():
                self.set_widget_colors(widget, bg_color, fg_color)
        else:
            # Set light mode colors
            bg_color = '#f0f0f0'  # Default light gray
            fg_color = '#000000'  # Black
            self.root.configure(bg=bg_color)
            for widget in self.root.winfo_children():
                self.set_widget_colors(widget, bg_color, fg_color)

    def set_widget_colors(self, widget, bg_color, fg_color):
        try:
            widget.configure(bg=bg_color, fg=fg_color)
        except:
            pass
        if isinstance(widget, (tk.Frame, tk.LabelFrame)):
            for child in widget.winfo_children():
                self.set_widget_colors(child, bg_color, fg_color)

    def configure_positions(self):
        # Simple dialog to show positions and allow editing
        pos_window = tk.Toplevel(self.root)
        pos_window.title("Configure Positions")

        pos_vars = {}
        row = 0
        for key, value in self.positions.items():
            tk.Label(pos_window, text=f"{key}:").grid(row=row, column=0, sticky='e')
            x_var = tk.IntVar(value=value[0])
            y_var = tk.IntVar(value=value[1])
            pos_vars[key] = (x_var, y_var)
            x_entry = tk.Entry(pos_window, textvariable=x_var, width=10)
            x_entry.grid(row=row, column=1)
            y_entry = tk.Entry(pos_window, textvariable=y_var, width=10)
            y_entry.grid(row=row, column=2)
            # Add Set button
            set_button = tk.Button(pos_window, text="Set", command=functools.partial(self.set_position, key, x_var, y_var))
            set_button.grid(row=row, column=3)
            row += 1

        # Add current mouse position label
        current_pos_label = tk.Label(pos_window, text="Current Mouse Position: (0, 0)")
        current_pos_label.grid(row=row, column=0, columnspan=4)
        row += 1

        # Function to update the mouse position
        def update_mouse_position():
            x, y = mouse.get_position()
            current_pos_label.config(text=f"Current Mouse Position: ({x}, {y})")
            pos_window.after(100, update_mouse_position)

        update_mouse_position()

        def save_positions():
            for key, (x_var, y_var) in pos_vars.items():
                self.positions[key] = (x_var.get(), y_var.get())
            pos_window.destroy()

        tk.Button(pos_window, text="Save", command=save_positions).grid(row=row, column=0, columnspan=4, pady=5)

    def set_position(self, key, x_var, y_var):
        # Remove the confirmation messagebox
        # Disable the GUI to prevent interactions
        self.root.attributes("-disabled", True)

        def wait_for_click():
            # Wait for the next left button down event
            mouse.wait(button='left', target_types=('down',))
            # Get the current mouse position
            x, y = mouse.get_position()
            # Schedule the update to the GUI thread
            self.root.after(0, self.update_position, x_var, y_var, x, y)

        threading.Thread(target=wait_for_click).start()

    def update_position(self, x_var, y_var, x, y):
        x_var.set(x)
        y_var.set(y)
        # Re-enable the GUI
        self.root.attributes("-disabled", False)

    def start_script(self):
        if not self.running:
            self.running = True
            self.start_button.config(state='disabled')
            self.pause_button.config(state='normal')
            self.stop_button.config(state='normal')
            self.script_thread = threading.Thread(target=self.run_script)
            self.script_thread.start()
        else:
            messagebox.showinfo("Script Running", "The script is already running.")

    def pause_script(self):
        if self.running:
            if pause_event.is_set():
                pause_event.clear()
                self.pause_button.config(text="Pause Script")
                self.logger.info(Fore.MAGENTA + "Script resumed.")
            else:
                pause_event.set()
                self.pause_button.config(text="Resume Script")
                self.logger.info(Fore.MAGENTA + "Script paused.")

    def stop_script(self):
        if self.running:
            kill_event.set()
            self.script_thread.join()
            self.running = False
            self.start_button.config(state='normal')
            self.pause_button.config(state='disabled', text="Pause Script")
            self.stop_button.config(state='disabled')
            # Reset events
            start_event.clear()
            pause_event.clear()
            kill_event.clear()
            self.logger.info(Fore.RED + "Script stopped.")
        else:
            messagebox.showinfo("Script Not Running", "The script is not running.")

    def run_script(self):
        # Retrieve input parameters
        num_runs = self.num_runs.get()
        cooking_repeat = self.cooking_repeat.get()
        tick_time = self.tick_time.get()
        interaction_wait = (self.interaction_wait_min.get(), self.interaction_wait_max.get())
        positions = self.positions.copy()
        interface_wait = self.interface_wait.get()
        mouse_method = self.mouse_method.get()

        # Create mouse controller
        mouse_controller = MouseController(method=mouse_method, interface_wait=interface_wait)

        # Start the script
        self.logger.info(Fore.BLUE + "Script started.")
        try:
            run_number = 1
            while run_number <= num_runs and not kill_event.is_set():
                check_events()
                BankingProcedure(run_number, positions, interaction_wait, self.logger, interface_wait, mouse_controller)
                check_events()
                CookingProcedure(run_number, cooking_repeat, tick_time, positions, interaction_wait, self.logger, interface_wait, mouse_controller)
                run_number += 1
            if run_number > num_runs:
                self.logger.info(Fore.BLUE + "Completed all runs.")
                self.stop_script()
        except KillScriptException:
            self.logger.info(Fore.RED + "Script terminated.")
            self.stop_script()

    # Hotkey methods
    def hotkey_start_script(self):
        self.root.after(0, self.start_script)

    def hotkey_pause_script(self):
        self.root.after(0, self.pause_script)

    def hotkey_stop_script(self):
        self.root.after(0, self.stop_script)

if __name__ == "__main__":
    # Create the main window
    root = tk.Tk()
    app = MacroGUI(root)
    root.mainloop()
