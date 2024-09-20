import logging
import random
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter import scrolledtext
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
    def __init__(self, method='standard'):
        self.method = method

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
        self.text_widget.tag_config('RED', foreground='#FF5555')
        self.text_widget.tag_config('GREEN', foreground='#50FA7B')
        self.text_widget.tag_config('YELLOW', foreground='#F1FA8C')
        self.text_widget.tag_config('BLUE', foreground='#BD93F9')
        self.text_widget.tag_config('MAGENTA', foreground='#FF79C6')
        self.text_widget.tag_config('CYAN', foreground='#8BE9FD')
        self.text_widget.tag_config('RESET', foreground='#F8F8F2')
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
    while True:
        if kill_event.is_set():
            raise KillScriptException()
        if not pause_event.is_set():
            break
        time.sleep(0.1)

def press_key_smoothly(key, stop_event):
    """Simulates holding down a key smoothly until stopped or paused."""
    keyboard_controller.press(key)
    try:
        while not stop_event.is_set():
            if kill_event.is_set() or pause_event.is_set():
                break
            time.sleep(0.1)
    finally:
        keyboard_controller.release(key)

def BankingProcedure(run_number, positions, interaction_wait, logger, mouse_controller):
    """Performs the banking procedure."""
    logger.info(Fore.CYAN + f"Starting Banking Procedure (Run {run_number})...")
    wait_time = INTERACTION_WAIT(*interaction_wait)
    check_events()
    logger.debug(Fore.CYAN + "Moving to bank position.")
    mouse_controller.move(*positions['bank_pos'], duration=wait_time)
    time.sleep(wait_time)
    mouse_controller.click()
    time.sleep(wait_time)

    wait_time = INTERACTION_WAIT(*interaction_wait)
    check_events()
    logger.debug(Fore.CYAN + "Moving to deposit all position.")
    mouse_controller.move(*positions['deposit_all_pos'], duration=wait_time)
    time.sleep(wait_time)
    mouse_controller.click()
    time.sleep(wait_time)

    wait_time = INTERACTION_WAIT(*interaction_wait)
    check_events()
    logger.debug(Fore.CYAN + "Moving to bank item position.")
    mouse_controller.move(*positions['bank_item_pos'], duration=wait_time)
    time.sleep(wait_time)
    logger.debug(Fore.CYAN + "Performing shift double-click on bank item.")
    keyboard_controller.press(Key.shift)
    mouse_controller.double_click()
    keyboard_controller.release(Key.shift)
    time.sleep(wait_time)

    logger.debug(Fore.CYAN + "Pressing ESC to close bank interface.")
    keyboard_controller.press(Key.esc)
    keyboard_controller.release(Key.esc)
    time.sleep(wait_time)

    logger.info(Fore.CYAN + f"Completed Banking Procedure (Run {run_number}).")

def CookingProcedure(run_number, cooking_repeat, tick_time, speculative_mode, cooking_loop_target, positions, interaction_wait, logger, mouse_controller, app):
    """Performs the cooking procedure."""
    logger.info(Fore.GREEN + f"Starting Cooking Procedure (Run {run_number})...")
    wait_time = INTERACTION_WAIT(*interaction_wait)
    check_events()
    logger.debug(Fore.GREEN + "Pressing 'q' to open inventory.")
    keyboard_controller.press('q')
    keyboard_controller.release('q')
    time.sleep(wait_time)
    logger.debug(Fore.GREEN + "Pressing 'w' to open cooking interface.")
    keyboard_controller.press('w')
    keyboard_controller.release('w')
    time.sleep(wait_time)  # Wait for the interface to load

    # Start holding '1' key smoothly
    stop_event = threading.Event()
    key_thread = threading.Thread(target=press_key_smoothly, args=('1', stop_event))
    key_thread.start()

    total_start_time = time.time()  # To record total execution time
    iteration_times = []

    try:
        for i in range(1, cooking_repeat + 1):
            check_events()
            loop_start_time = time.time()

            # Update progress
            app.update_progress(i, cooking_repeat)

            # Step 1: Move to inven_food_pos and click
            wait_time = INTERACTION_WAIT(*interaction_wait)
            mouse_controller.move(*positions['inven_food_pos'], duration=wait_time)
            time.sleep(wait_time)
            mouse_controller.click()

            # Step 2: Move to cook_food_pos and click
            wait_time = INTERACTION_WAIT(*interaction_wait)
            mouse_controller.move(*positions['cook_food_pos'], duration=wait_time)
            time.sleep(wait_time)
            mouse_controller.click()

            # Calculate elapsed time
            elapsed_time = time.time() - loop_start_time

            if speculative_mode:
                # Adjust sleep time to match cooking_loop_target
                sleep_time = cooking_loop_target - elapsed_time
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    logger.warning(Fore.RED + f"Warning: Cooking loop took longer than {cooking_loop_target:.4f} seconds.")
            else:
                # Sleep for tick_time
                sleep_time = tick_time - elapsed_time
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    logger.warning(Fore.RED + f"Warning: Cooking loop took longer than tick_time ({tick_time:.4f} seconds).")
                    logger.debug(Fore.BLUE + f"Tick time: {tick_time:.4f}s, Difference: {tick_time - elapsed_time:.4f}s")

            # Record iteration time
            iteration_time = time.time() - loop_start_time
            iteration_times.append(iteration_time)

            # Update estimated time remaining
            app.update_estimated_time(iteration_times, cooking_repeat - i)

    finally:
        # Stop the key pressing thread
        stop_event.set()
        key_thread.join()
        total_execution_time = time.time() - total_start_time
        logger.info(Fore.GREEN + f"Completed Cooking Procedure (Run {run_number}).")
        logger.debug(Fore.BLUE + f"Total execution time: {total_execution_time:.4f} seconds.")
        # Reset current progress
        app.update_progress(0, 1)
        app.update_estimated_time([], 0)

class MacroGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Macro Script")
        self.running = False

        # Input parameters with default values
        self.num_runs = tk.IntVar(value=10)
        self.cooking_repeat = tk.IntVar(value=28)
        self.tick_time = tk.DoubleVar(value=0.7)  # Default to 0.7 seconds
        self.speculative_mode = tk.BooleanVar(value=False)
        self.cooking_loop_target = tk.DoubleVar(value=0.55)
        self.interaction_wait_min = tk.DoubleVar(value=0.02)
        self.interaction_wait_max = tk.DoubleVar(value=0.05)
        self.positions = default_positions.copy()
        self.mouse_method = tk.StringVar(value='standard')
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

        row = 0
        tk.Label(param_frame, text="Number of Runs:").grid(row=row, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.num_runs).grid(row=row, column=1)
        row += 1

        tk.Label(param_frame, text="Cooking Repeat:").grid(row=row, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.cooking_repeat).grid(row=row, column=1)
        row +=1

        tk.Label(param_frame, text="Tick Time (s):").grid(row=row, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.tick_time).grid(row=row, column=1)
        row +=1

        self.speculative_mode_check = tk.Checkbutton(param_frame, text="Speculative Mode", variable=self.speculative_mode)
        self.speculative_mode_check.grid(row=row, column=0, columnspan=2)
        row +=1

        tk.Label(param_frame, text="Cooking Loop Target (s):").grid(row=row, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.cooking_loop_target).grid(row=row, column=1)
        row +=1

        tk.Label(param_frame, text="Interaction Wait Min (s):").grid(row=row, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.interaction_wait_min).grid(row=row, column=1)
        row +=1

        tk.Label(param_frame, text="Interaction Wait Max (s):").grid(row=row, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.interaction_wait_max).grid(row=row, column=1)
        row +=1

        tk.Label(param_frame, text="Mouse Method:").grid(row=row, column=0, sticky='e')
        mouse_method_option = tk.OptionMenu(param_frame, self.mouse_method, 'standard', 'pyhm')
        mouse_method_option.grid(row=row, column=1)
        row +=1

        tk.Label(param_frame, text="Font Size:").grid(row=row, column=0, sticky='e')
        tk.Entry(param_frame, textvariable=self.font_size).grid(row=row, column=1)
        row +=1

        dark_mode_check = tk.Checkbutton(param_frame, text="Dark Mode", variable=self.dark_mode, command=self.toggle_dark_mode)
        dark_mode_check.grid(row=row, column=0, columnspan=2)
        row +=1

        # Button to configure positions
        tk.Button(param_frame, text="Configure Positions", command=self.configure_positions).grid(row=row, column=0, columnspan=2, pady=5)
        row +=1

        # Progress bars and timing labels
        self.current_progress = tk.DoubleVar()
        self.overall_progress = tk.DoubleVar()
        self.current_progress_label = tk.StringVar()
        self.overall_progress_label = tk.StringVar()
        self.estimated_time_label = tk.StringVar(value="Estimated Time Remaining: N/A")

        tk.Label(param_frame, text="Current Procedure Progress:").grid(row=row, column=0, sticky='e')
        self.current_progress_bar = ttk.Progressbar(param_frame, variable=self.current_progress, maximum=100)
        self.current_progress_bar.grid(row=row, column=1, sticky='we')
        row +=1

        self.current_progress_text = tk.Label(param_frame, textvariable=self.current_progress_label)
        self.current_progress_text.grid(row=row, column=0, columnspan=2)
        row +=1

        tk.Label(param_frame, text="Overall Progress:").grid(row=row, column=0, sticky='e')
        self.overall_progress_bar = ttk.Progressbar(param_frame, variable=self.overall_progress, maximum=100)
        self.overall_progress_bar.grid(row=row, column=1, sticky='we')
        row +=1

        self.overall_progress_text = tk.Label(param_frame, textvariable=self.overall_progress_label)
        self.overall_progress_text.grid(row=row, column=0, columnspan=2)
        row +=1

        self.estimated_time_text = tk.Label(param_frame, textvariable=self.estimated_time_label)
        self.estimated_time_text.grid(row=row, column=0, columnspan=2)
        row +=1

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
            bg_color = '#3a3a3a'  # Dark gray
            fg_color = '#F8F8F2'  # Light gray
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

    def update_progress(self, current, total):
        progress = (current / total) * 100
        self.current_progress.set(progress)
        self.current_progress_label.set(f"{current}/{total} ({progress:.2f}%)")
        self.root.update_idletasks()

    def update_overall_progress(self, current, total):
        progress = (current / total) * 100
        self.overall_progress.set(progress)
        self.overall_progress_label.set(f"{current}/{total} ({progress:.2f}%)")
        self.root.update_idletasks()

    def update_estimated_time(self, iteration_times, remaining_iterations):
        if iteration_times:
            average_time = sum(iteration_times[-5:]) / min(len(iteration_times), 5)  # Average of last 5 iterations
            estimated_time = average_time * remaining_iterations
            minutes, seconds = divmod(estimated_time, 60)
            self.estimated_time_label.set(f"Estimated Time Remaining: {int(minutes)}m {int(seconds)}s")
        else:
            self.estimated_time_label.set("Estimated Time Remaining: N/A")
        self.root.update_idletasks()

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
                # Reload configuration when resuming
                self.reload_config()
                pause_event.clear()
                self.pause_button.config(text="Pause Script")
                self.logger.info(Fore.MAGENTA + "Script resumed.")
            else:
                pause_event.set()
                self.pause_button.config(text="Resume Script")
                self.logger.info(Fore.MAGENTA + "Script paused.")

    def reload_config(self):
        # Re-fetch input parameters
        self.logger.info(Fore.CYAN + "Reloading configuration...")
        self.num_runs_value = self.num_runs.get()
        self.cooking_repeat_value = self.cooking_repeat.get()
        self.tick_time_value = self.tick_time.get()
        self.speculative_mode_value = self.speculative_mode.get()
        self.cooking_loop_target_value = self.cooking_loop_target.get()
        self.interaction_wait_value = (self.interaction_wait_min.get(), self.interaction_wait_max.get())
        self.positions_value = self.positions.copy()
        self.mouse_method_value = self.mouse_method.get()
        self.logger.info(Fore.CYAN + "Configuration reloaded.")

    def stop_script(self):
        if self.running:
            kill_event.set()
            pause_event.clear()  # Ensure the script isn't paused
            self.script_thread.join()
            self.running = False
            self.start_button.config(state='normal')
            self.pause_button.config(state='disabled', text="Pause Script")
            self.stop_button.config(state='disabled')
            # Reset events
            start_event.clear()
            kill_event.clear()
            self.logger.info(Fore.RED + "Script stopped.")
            # Reset progress bars and labels
            self.current_progress.set(0)
            self.current_progress_label.set("")
            self.overall_progress.set(0)
            self.overall_progress_label.set("")
            self.estimated_time_label.set("Estimated Time Remaining: N/A")
        else:
            messagebox.showinfo("Script Not Running", "The script is not running.")

    def run_script(self):
        # Retrieve input parameters
        self.reload_config()

        # Create mouse controller
        mouse_controller = MouseController(method=self.mouse_method_value)

        # Start the script
        self.logger.info(Fore.BLUE + "Script started.")
        try:
            run_number = 1
            total_runs = self.num_runs_value
            while run_number <= total_runs and not kill_event.is_set():
                check_events()
                self.update_overall_progress(run_number - 1, total_runs)
                BankingProcedure(run_number, self.positions_value, self.interaction_wait_value, self.logger, mouse_controller)
                check_events()
                CookingProcedure(run_number, self.cooking_repeat_value, self.tick_time_value, self.speculative_mode_value, self.cooking_loop_target_value, self.positions_value, self.interaction_wait_value, self.logger, mouse_controller, self)
                run_number += 1
                self.update_overall_progress(run_number - 1, total_runs)
            if run_number > total_runs:
                self.logger.info(Fore.BLUE + "Completed all runs.")
                self.stop_script()
        except KillScriptException:
            self.logger.info(Fore.RED + "Script terminated.")
            self.stop_script()
        except Exception as e:
            self.logger.error(Fore.RED + f"An error occurred: {e}")
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
