import logging
import random
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext
import functools

import keyboard
import mouse
from colorama import init, Fore
from pyHM import mouse as hm_mouse

# Initialize colorama
init(autoreset=True)

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

pyHM_mult = 0.5  # Multiplier for mouse movement speed


class KillScriptException(Exception):
    """Custom exception to handle script termination."""
    pass


class ScriptLogger:
    """Class to handle logging within the GUI."""

    def __init__(self, text_widget, log_file):
        self.text_widget = text_widget
        self.log_file = log_file
        self.log_lock = threading.Lock()

        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(message)s',
            datefmt='%H:%M:%S',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger()

    def write(self, message):
        with self.log_lock:
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, message)
            self.text_widget.configure(state='disabled')
            self.text_widget.see(tk.END)
            self.logger.info(message.strip())

    def flush(self):
        pass  # For compatibility with file-like object


def INTERACTION_WAIT(min_wait, max_wait):
    """Returns a random interaction wait time between min_wait and max_wait."""
    return random.uniform(min_wait, max_wait)


def check_events():
    """Checks for kill and pause events."""
    if kill_event.is_set():
        raise KillScriptException()
    while pause_event.is_set():
        time.sleep(0.1)


def BankingProcedure(run_number, positions, interaction_wait, logger):
    """Performs the banking procedure."""
    print(Fore.CYAN + f"Starting Banking Procedure (Run {run_number})...")
    wait_time = INTERACTION_WAIT(*interaction_wait)
    check_events()
    print(Fore.YELLOW + "Moving to bank position.")
    hm_mouse.move(*positions['bank_pos'], multiplier=pyHM_mult)
    time.sleep(wait_time)
    hm_mouse.click()

    wait_time = INTERACTION_WAIT(*interaction_wait)
    check_events()
    print(Fore.YELLOW + "Moving to deposit all position.")
    hm_mouse.move(*positions['deposit_all_pos'], multiplier=pyHM_mult)
    time.sleep(wait_time)
    hm_mouse.click()

    wait_time = INTERACTION_WAIT(*interaction_wait)
    check_events()
    print(Fore.YELLOW + "Moving to bank item position.")
    hm_mouse.move(*positions['bank_item_pos'], multiplier=pyHM_mult)
    time.sleep(wait_time)
    print(Fore.YELLOW + "Performing shift double-click on bank item.")
    keyboard.press('shift')
    hm_mouse.double_click()
    keyboard.release('shift')

    time.sleep(wait_time)
    print(Fore.YELLOW + "Pressing ESC to close bank interface.")
    keyboard.press_and_release('esc')
    keyboard.press_and_release('esc')

    print(Fore.CYAN + f"Completed Banking Procedure (Run {run_number}).")


def CookingProcedure(run_number, cooking_repeat, tick_time, positions, interaction_wait, logger):
    """Performs the cooking procedure."""
    print(Fore.GREEN + f"Starting Cooking Procedure (Run {run_number})...")
    wait_time = INTERACTION_WAIT(*interaction_wait)
    check_events()
    print(Fore.YELLOW + "Pressing 'q' to open inventory.")
    keyboard.press_and_release('q')
    time.sleep(wait_time)
    print(Fore.YELLOW + "Pressing 'w' to open cooking interface.")
    keyboard.press_and_release('w')
    time.sleep(wait_time * 2)  # Wait for the interface to load

    # Press and hold the confirmation button (key '1')
    print(Fore.YELLOW + "Holding down confirmation button '1'.")
    keyboard.press('1')

    for i in range(1, cooking_repeat + 1):
        check_events()
        start_time = time.time()

        print(Fore.YELLOW + f"Cooking loop iteration {i}/{cooking_repeat}.")

        wait_time = INTERACTION_WAIT(*interaction_wait)
        hm_mouse.move(*positions['inven_food_pos'], multiplier=pyHM_mult)
        time.sleep(wait_time)
        hm_mouse.click()

        wait_time = INTERACTION_WAIT(*interaction_wait)
        hm_mouse.move(*positions['cook_food_pos'], multiplier=pyHM_mult)
        time.sleep(wait_time)
        hm_mouse.click()

        # Sleep for one tick
        time.sleep(tick_time)

        # Ensure the loop takes between 600-700 ms
        elapsed_time = time.time() - start_time
        if elapsed_time < 0.6:
            time.sleep(0.6 - elapsed_time)
        elif elapsed_time > 0.7:
            print(Fore.RED + "Warning: Cooking loop took longer than 700 ms.")

    # Release the confirmation button
    keyboard.release('1')
    print(Fore.GREEN + f"Completed Cooking Procedure (Run {run_number}).")


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

        self.create_widgets()
        self.log_file = "macro_script.log"

        # Redirect stdout to the text widget
        self.logger = ScriptLogger(self.log_output, self.log_file)
        sys.stdout = self.logger

        # Set up hotkeys
        keyboard.add_hotkey('alt+x', self.hotkey_start_script)
        keyboard.add_hotkey('alt+c', self.hotkey_pause_script)
        keyboard.add_hotkey('f1', self.hotkey_stop_script)

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

        # Button to configure positions
        tk.Button(param_frame, text="Configure Positions", command=self.configure_positions).grid(row=5, column=0,
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
        self.log_output = scrolledtext.ScrolledText(self.root, state='disabled', width=80, height=20)
        self.log_output.pack(pady=10)

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
        messagebox.showinfo("Set Position", "Please click to set the position.")
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
                print(Fore.MAGENTA + "Script resumed.")
            else:
                pause_event.set()
                self.pause_button.config(text="Resume Script")
                print(Fore.MAGENTA + "Script paused.")

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
            print(Fore.RED + "Script stopped.")
        else:
            messagebox.showinfo("Script Not Running", "The script is not running.")

    def run_script(self):
        # Retrieve input parameters
        num_runs = self.num_runs.get()
        cooking_repeat = self.cooking_repeat.get()
        tick_time = self.tick_time.get()
        interaction_wait = (self.interaction_wait_min.get(), self.interaction_wait_max.get())
        positions = self.positions.copy()

        # Start the script
        print(Fore.BLUE + "Script started.")
        try:
            run_number = 1
            while run_number <= num_runs and not kill_event.is_set():
                check_events()
                BankingProcedure(run_number, positions, interaction_wait, self.logger)
                check_events()
                CookingProcedure(run_number, cooking_repeat, tick_time, positions, interaction_wait, self.logger)
                run_number += 1
            if run_number > num_runs:
                print(Fore.BLUE + "Completed all runs.")
                self.stop_script()
        except KillScriptException:
            print(Fore.RED + "Script terminated.")
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
