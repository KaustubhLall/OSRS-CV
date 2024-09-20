import functools
import logging
import random
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import mouse
import pyautogui
from colorama import init, Fore
from pynput import keyboard as pynput_keyboard
from pynput.keyboard import Key, Controller

# Initialize Colorama for colored terminal output
init(autoreset=True)

# Initialize pynput keyboard controller
keyboard_controller = Controller()

# Default positions for various UI elements
default_positions = {
    "bank_pos": (902, 810),
    "deposit_all_pos": (313, 954),
    "bank_item_pos": (610, 723),
    "inven_food_pos": (2188, 1244),
    "cook_food_pos": (1710, 1110),
}

# Event flags to control script execution
start_event = threading.Event()
pause_event = threading.Event()
kill_event = threading.Event()


class KillScriptException(Exception):
    """Exception to signal script termination."""

    pass


class MouseController:
    """Handles mouse movements and clicks using specified methods."""

    def __init__(self, method="standard", interface_wait=0.5):
        self.method = method
        self.interface_wait = interface_wait  # Time to wait after interactions

    def move(self, x, y, duration=0):
        if self.method == "standard":
            pyautogui.moveTo(x, y, duration=duration)
        elif self.method == "pyhm":
            pass  # TODO: Implement pyHM method

    def click(self):
        if self.method == "standard":
            pyautogui.click()
        elif self.method == "pyhm":
            pass  # TODO: Implement pyHM method

    def double_click(self):
        if self.method == "standard":
            pyautogui.doubleClick()
        elif self.method == "pyhm":
            pass  # TODO: Implement pyHM method


class TextHandler(logging.Handler):
    """Logging handler that directs log messages to a Tkinter Text widget."""

    def __init__(self, text_widget, dark_mode=False):
        super().__init__()
        self.text_widget = text_widget
        self.dark_mode = dark_mode
        self.configure_tags()
        self.ANSI_ESCAPE_RE = re.compile(r"\x1b\[(\d+)(;\d+)*m")
        self.COLOR_MAP = {
            "30": "BLACK",
            "31": "RED",
            "32": "GREEN",
            "33": "BLACK",  # Changed from YELLOW to BLACK for better visibility
            "34": "BLUE",
            "35": "MAGENTA",
            "36": "CYAN",
            "37": "WHITE",
        }

    def configure_tags(self):
        """Sets up text tags for color formatting based on theme."""
        if self.dark_mode:
            colors = {
                "BLACK": "#A9B7C6",
                "RED": "#FF5555",
                "GREEN": "#50FA7B",
                "YELLOW": "#FFB86C",
                "BLUE": "#BD93F9",
                "MAGENTA": "#FF79C6",
                "CYAN": "#8BE9FD",
                "WHITE": "#FFFFFF",
                "RESET": "#FFFFFF",
            }
        else:
            colors = {
                "BLACK": "black",
                "RED": "red",
                "GREEN": "green",
                "YELLOW": "black",  # Changed for consistency
                "BLUE": "blue",
                "MAGENTA": "magenta",
                "CYAN": "cyan",
                "WHITE": "white",
                "RESET": "black",
            }

        for tag, color in colors.items():
            self.text_widget.tag_config(tag, foreground=color)

        # Bold fonts for specific log levels
        bold_tags = {
            "ERROR": ("red", ("TkDefaultFont", 10, "bold")),
            "WARNING": ("BLACK", ("TkDefaultFont", 10, "bold")),
            "INFO": ("green", ("TkDefaultFont", 10, "bold")),
            "DEBUG": ("blue", ("TkDefaultFont", 10, "bold")),
        }

        for tag, (color, font) in bold_tags.items():
            self.text_widget.tag_config(tag, foreground=color, font=font)

    def emit(self, record):
        """Formats and inserts log records into the Text widget."""
        msg = self.format(record)
        pos = 0
        last_tag = "RESET"
        for match in self.ANSI_ESCAPE_RE.finditer(msg):
            start, end = match.span()
            text = msg[pos:start]
            if text:
                self.text_widget.configure(state="normal")
                self.text_widget.insert(tk.END, text, last_tag)
                self.text_widget.configure(state="disabled")
            color_codes = match.group().strip("\x1b[").strip("m").split(";")
            last_tag = self.COLOR_MAP.get(color_codes[0], "RESET")
            pos = end
        # Insert remaining text
        text = msg[pos:] + "\n"
        if text:
            self.text_widget.configure(state="normal")
            self.text_widget.insert(tk.END, text, last_tag)
            self.text_widget.configure(state="disabled")
        # Auto-scroll to the end
        self.text_widget.see(tk.END)


def INTERACTION_WAIT(min_wait, max_wait):
    """Generates a random wait time between min_wait and max_wait seconds."""
    return random.uniform(min_wait, max_wait)


def check_events():
    """Monitors kill and pause events, raising an exception if termination is requested."""
    while True:
        if kill_event.is_set():
            raise KillScriptException()
        if not pause_event.is_set():
            break
        time.sleep(0.1)


def press_key_continuously(key, stop_event, interval=0.05):
    """Continuously presses and releases a key at specified intervals until stopped."""
    while not stop_event.is_set():
        if kill_event.is_set():
            break
        if pause_event.is_set():
            time.sleep(0.1)
            continue
        keyboard_controller.press(key)
        keyboard_controller.release(key)
        time.sleep(interval)


class MacroGUI:
    """Graphical User Interface for the Game Macro Script."""

    def __init__(self, root):
        self.root = root
        self.root.title("Game Macro Script")
        self.running = False

        # Input parameters with default values
        self.num_runs = tk.IntVar(value=10)
        self.cooking_repeat = tk.IntVar(value=28)
        self.tick_time = tk.DoubleVar(value=0.7)
        self.speculative_mode = tk.BooleanVar(value=False)
        self.cooking_loop_target = tk.DoubleVar(value=0.55)
        self.interaction_wait_min = tk.DoubleVar(value=0.02)
        self.interaction_wait_max = tk.DoubleVar(value=0.05)
        self.positions = default_positions.copy()
        self.mouse_method = tk.StringVar(value="standard")
        self.interface_wait = tk.DoubleVar(value=0.5)
        self.font_size = tk.IntVar(value=10)
        self.dark_mode = tk.BooleanVar(value=False)

        self.create_widgets()
        self.log_file = "macro_script.log"

        # Set up logging
        self.logger = logging.getLogger("MacroLogger")
        self.logger.setLevel(logging.INFO)

        # File handler for logging
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)

        # GUI handler for logging
        gui_handler = TextHandler(self.log_output, dark_mode=self.dark_mode.get())
        gui_handler.setLevel(logging.INFO)
        gui_formatter = logging.Formatter("%(message)s")
        gui_handler.setFormatter(gui_formatter)

        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(gui_handler)

        # Set up global hotkeys
        self.hotkey_listener = pynput_keyboard.GlobalHotKeys(
            {
                "<alt>+x": self.hotkey_start_script,
                "<alt>+c": self.hotkey_pause_script,
                "<f1>": self.hotkey_stop_script,
            }
        )
        self.hotkey_listener.start()

        # Bind font size changes
        self.font_size.trace("w", self.update_font_size)

    def create_widgets(self):
        """Creates and arranges all GUI widgets."""
        # Frame for input parameters
        param_frame = tk.Frame(self.root)
        param_frame.pack(pady=10)

        row = 0
        # Number of Runs
        tk.Label(param_frame, text="Number of Runs:").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(param_frame, textvariable=self.num_runs).grid(row=row, column=1)
        row += 1

        # Cooking Repeat
        tk.Label(param_frame, text="Cooking Repeat:").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(param_frame, textvariable=self.cooking_repeat).grid(row=row, column=1)
        row += 1

        # Tick Time
        tk.Label(param_frame, text="Tick Time (s):").grid(row=row, column=0, sticky="e")
        tk.Entry(param_frame, textvariable=self.tick_time).grid(row=row, column=1)
        row += 1

        # Speculative Mode
        tk.Checkbutton(
            param_frame, text="Speculative Mode", variable=self.speculative_mode
        ).grid(row=row, column=0, columnspan=2)
        row += 1

        # Cooking Loop Target
        tk.Label(param_frame, text="Cooking Loop Target (s):").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(param_frame, textvariable=self.cooking_loop_target).grid(
            row=row, column=1
        )
        row += 1

        # Interaction Wait Min
        tk.Label(param_frame, text="Interaction Wait Min (s):").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(param_frame, textvariable=self.interaction_wait_min).grid(
            row=row, column=1
        )
        row += 1

        # Interaction Wait Max
        tk.Label(param_frame, text="Interaction Wait Max (s):").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(param_frame, textvariable=self.interaction_wait_max).grid(
            row=row, column=1
        )
        row += 1

        # Mouse Method
        tk.Label(param_frame, text="Mouse Method:").grid(row=row, column=0, sticky="e")
        tk.OptionMenu(param_frame, self.mouse_method, "standard", "pyhm").grid(
            row=row, column=1
        )
        row += 1

        # Interface Wait
        tk.Label(param_frame, text="Interface Wait (s):").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(param_frame, textvariable=self.interface_wait).grid(row=row, column=1)
        row += 1

        # Font Size
        tk.Label(param_frame, text="Font Size:").grid(row=row, column=0, sticky="e")
        tk.Entry(param_frame, textvariable=self.font_size).grid(row=row, column=1)
        row += 1

        # Dark Mode
        tk.Checkbutton(
            param_frame,
            text="Dark Mode",
            variable=self.dark_mode,
            command=self.toggle_dark_mode,
        ).grid(row=row, column=0, columnspan=2)
        row += 1

        # Configure Positions Button
        tk.Button(
            param_frame, text="Configure Positions", command=self.configure_positions
        ).grid(row=row, column=0, columnspan=2, pady=5)

        # Frame for control buttons
        control_frame = tk.Frame(self.root)
        control_frame.pack(pady=10)

        # Start Button
        self.start_button = tk.Button(
            control_frame, text="Start Script", command=self.start_script
        )
        self.start_button.grid(row=0, column=0, padx=5)

        # Pause Button
        self.pause_button = tk.Button(
            control_frame,
            text="Pause Script",
            command=self.pause_script,
            state="disabled",
        )
        self.pause_button.grid(row=0, column=1, padx=5)

        # Stop Button
        self.stop_button = tk.Button(
            control_frame,
            text="Stop Script",
            command=self.stop_script,
            state="disabled",
        )
        self.stop_button.grid(row=0, column=2, padx=5)

        # Frame for progress bars
        progress_frame = tk.Frame(self.root)
        progress_frame.pack(pady=10, fill="x")

        # Current Procedure Progress
        tk.Label(progress_frame, text="Current Procedure Progress:").grid(
            row=0, column=0, sticky="w"
        )
        self.current_progress = ttk.Progressbar(
            progress_frame, length=400, mode="determinate"
        )
        self.current_progress.grid(row=1, column=0, padx=5, pady=5)
        self.current_progress_label = tk.Label(progress_frame, text="0/2 Steps (0.00%)")
        self.current_progress_label.grid(row=1, column=1, padx=5)
        self.current_progress_eta_label = tk.Label(
            progress_frame, text="ETA: Calculating..."
        )
        self.current_progress_eta_label.grid(row=1, column=2, padx=5)
        self.current_progress_percent_label = tk.Label(progress_frame, text="0.00%")
        self.current_progress_percent_label.grid(row=1, column=3, padx=5)

        # Overall Progress
        tk.Label(progress_frame, text="Overall Progress:").grid(
            row=2, column=0, sticky="w"
        )
        self.overall_progress = ttk.Progressbar(
            progress_frame, length=400, mode="determinate"
        )
        self.overall_progress.grid(row=3, column=0, padx=5, pady=5)
        num_runs = self.num_runs.get()
        self.overall_progress_label = tk.Label(
            progress_frame, text=f"0/{num_runs} Runs (0.00%)"
        )
        self.overall_progress_label.grid(row=3, column=1, padx=5)
        self.overall_progress_eta_label = tk.Label(
            progress_frame, text="ETA: Calculating..."
        )
        self.overall_progress_eta_label.grid(row=3, column=2, padx=5)
        self.overall_progress_percent_label = tk.Label(progress_frame, text="0.00%")
        self.overall_progress_percent_label.grid(row=3, column=3, padx=5)

        # Log Output
        font_size = self.font_size.get()
        self.log_output = scrolledtext.ScrolledText(
            self.root,
            state="disabled",
            width=80,
            height=20,
            font=("TkDefaultFont", font_size),
        )
        self.log_output.pack(pady=10)

    def update_font_size(self, *args):
        """Updates the font size of the log output."""
        font_size = self.font_size.get()
        self.log_output.configure(font=("TkDefaultFont", font_size))

    def toggle_dark_mode(self):
        """Toggles between dark and light themes."""
        if self.dark_mode.get():
            bg_color = "#2e2e2e"  # Dark gray
            fg_color = "#ffffff"  # White
        else:
            bg_color = "#f0f0f0"  # Light gray
            fg_color = "#000000"  # Black

        self.root.configure(bg=bg_color)
        for widget in self.root.winfo_children():
            self.set_widget_colors(widget, bg_color, fg_color)

        # Update log handler colors
        for handler in self.logger.handlers:
            if isinstance(handler, TextHandler):
                handler.dark_mode = self.dark_mode.get()
                handler.configure_tags()

    def set_widget_colors(self, widget, bg_color, fg_color):
        """Recursively sets background and foreground colors for widgets."""
        try:
            widget.configure(bg=bg_color, fg=fg_color)
        except:
            pass
        if isinstance(widget, (tk.Frame, tk.LabelFrame)):
            for child in widget.winfo_children():
                self.set_widget_colors(child, bg_color, fg_color)

    def configure_positions(self):
        """Opens a dialog to view and edit mouse positions."""
        pos_window = tk.Toplevel(self.root)
        pos_window.title("Configure Positions")

        pos_vars = {}
        row = 0
        for key, value in self.positions.items():
            tk.Label(pos_window, text=f"{key}:").grid(row=row, column=0, sticky="e")
            x_var = tk.IntVar(value=value[0])
            y_var = tk.IntVar(value=value[1])
            pos_vars[key] = (x_var, y_var)
            tk.Entry(pos_window, textvariable=x_var, width=10).grid(row=row, column=1)
            tk.Entry(pos_window, textvariable=y_var, width=10).grid(row=row, column=2)
            # Set Button
            tk.Button(
                pos_window,
                text="Set",
                command=functools.partial(self.set_position, key, x_var, y_var),
            ).grid(row=row, column=3)
            row += 1

        # Display current mouse position
        current_pos_label = tk.Label(pos_window, text="Current Mouse Position: (0, 0)")
        current_pos_label.grid(row=row, column=0, columnspan=4)
        row += 1

        def update_mouse_position():
            x, y = mouse.get_position()
            current_pos_label.config(text=f"Current Mouse Position: ({x}, {y})")
            pos_window.after(100, update_mouse_position)

        update_mouse_position()

        def save_positions():
            for key, (x_var, y_var) in pos_vars.items():
                self.positions[key] = (x_var.get(), y_var.get())
            pos_window.destroy()

        tk.Button(pos_window, text="Save", command=save_positions).grid(
            row=row, column=0, columnspan=4, pady=5
        )

    def set_position(self, key, x_var, y_var):
        """Sets a specific mouse position based on the next left-click."""
        # Disable GUI interactions
        self.root.attributes("-disabled", True)

        def wait_for_click():
            # Wait for left mouse button down event
            mouse.wait(button="left", target_types=("down",))
            x, y = mouse.get_position()
            # Update position in the GUI thread
            self.root.after(0, self.update_position, x_var, y_var, x, y)

        threading.Thread(target=wait_for_click).start()

    def update_position(self, x_var, y_var, x, y):
        """Updates the position variables and re-enables the GUI."""
        x_var.set(x)
        y_var.set(y)
        self.root.attributes("-disabled", False)

    def start_script(self):
        """Starts the macro script if not already running."""
        if not self.running:
            self.running = True
            self.start_button.config(state="disabled")
            self.pause_button.config(state="normal")
            self.stop_button.config(state="normal")
            self.script_thread = threading.Thread(target=self.run_script)
            self.script_thread.start()
        else:
            messagebox.showinfo("Script Running", "The script is already running.")

    def pause_script(self):
        """Pauses or resumes the macro script."""
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
        """Stops the macro script and resets the UI."""
        if self.running:
            kill_event.set()
            pause_event.clear()  # Ensure the script isn't paused
            self.script_thread.join()
            self.running = False
            self.start_button.config(state="normal")
            self.pause_button.config(state="disabled", text="Pause Script")
            self.stop_button.config(state="disabled")
            # Reset events
            start_event.clear()
            kill_event.clear()
            self.logger.info(Fore.RED + "Script stopped.")
            # Reset progress bars
            self.reset_progress_bars()
        else:
            messagebox.showinfo("Script Not Running", "The script is not running.")

    def reset_progress_bars(self):
        """Resets all progress bars and their labels."""
        # Reset Current Procedure Progress
        self.current_progress["value"] = 0
        self.current_progress_label.config(text="0/2 Steps (0.00%)")
        self.current_progress_eta_label.config(text="ETA: Calculating...")
        self.current_progress_percent_label.config(text="0.00%")

        # Reset Overall Progress
        num_runs = self.num_runs.get()
        self.overall_progress["value"] = 0
        self.overall_progress_label.config(text=f"0/{num_runs} Runs (0.00%)")
        self.overall_progress_eta_label.config(text="ETA: Calculating...")
        self.overall_progress_percent_label.config(text="0.00%")

    def run_script(self):
        """Main method to execute the macro script."""
        # Retrieve input parameters
        num_runs = self.num_runs.get()
        cooking_repeat = self.cooking_repeat.get()
        tick_time = self.tick_time.get()
        speculative_mode = self.speculative_mode.get()
        cooking_loop_target = self.cooking_loop_target.get()
        interaction_wait = (
            self.interaction_wait_min.get(),
            self.interaction_wait_max.get(),
        )
        positions = self.positions.copy()
        interface_wait = self.interface_wait.get()
        mouse_method = self.mouse_method.get()

        # Initialize MouseController
        mouse_controller = MouseController(
            method=mouse_method, interface_wait=interface_wait
        )

        # Initialize progress bars
        self.current_progress["maximum"] = 2 * cooking_repeat  # 2 steps per iteration
        self.overall_progress["maximum"] = num_runs
        self.overall_progress_label.config(text=f"0/{num_runs} Runs (0.00%)")
        self.overall_progress_eta_label.config(text="ETA: Calculating...")
        self.overall_progress_percent_label.config(text="0.00%")

        # Start logging
        self.logger.info(Fore.BLUE + "Script started.")
        overall_run_start_time = time.time()
        try:
            for run_number in range(1, num_runs + 1):
                check_events()
                self.update_overall_progress(
                    run_number, num_runs, overall_run_start_time
                )
                self.banking_procedure(
                    run_number,
                    positions,
                    interaction_wait,
                    interface_wait,
                    mouse_controller,
                )
                check_events()
                self.cooking_procedure(
                    run_number,
                    cooking_repeat,
                    tick_time,
                    speculative_mode,
                    cooking_loop_target,
                    positions,
                    interaction_wait,
                    interface_wait,
                    mouse_controller,
                )
            self.logger.info(Fore.BLUE + "Completed all runs.")
            self.stop_script()
        except KillScriptException:
            self.logger.info(Fore.RED + "Script terminated.")
            self.stop_script()
        except Exception as e:
            self.logger.error(Fore.RED + f"An error occurred: {e}")
            self.stop_script()

    def update_overall_progress(self, run_number, total_runs, start_time):
        """Updates the overall progress bar and estimated time remaining."""
        percent = (run_number / total_runs) * 100
        self.overall_progress["value"] = run_number
        self.overall_progress_label.config(
            text=f"{run_number}/{total_runs} Runs ({percent:.2f}%)"
        )

        # Calculate ETA
        elapsed = time.time() - start_time
        if run_number > 0:
            average_time = elapsed / run_number
            remaining_runs = total_runs - run_number
            eta = average_time * remaining_runs
            eta_str = time.strftime("%H:%M:%S", time.gmtime(eta))
        else:
            eta_str = "Calculating..."
        self.overall_progress_eta_label.config(text=f"ETA: {eta_str}")
        self.overall_progress_percent_label.config(text=f"{percent:.2f}%")

    def update_current_progress(self, steps_completed, total_steps, eta):
        """Updates the current procedure's progress bar and ETA."""
        percent = (steps_completed / total_steps) * 100
        self.current_progress["value"] = steps_completed
        self.current_progress_label.config(
            text=f"{steps_completed}/{total_steps} Steps ({percent:.2f}%)"
        )
        self.current_progress_percent_label.config(text=f"{percent:.2f}%")

        if eta:
            eta_str = eta
        else:
            eta_str = "Calculating..."
        self.current_progress_eta_label.config(text=f"ETA: {eta_str}")

    def banking_procedure(
        self, run_number, positions, interaction_wait, interface_wait, mouse_controller
    ):
        """Executes the banking steps."""
        self.logger.info(
            Fore.CYAN + f"Starting Banking Procedure (Run {run_number})..."
        )
        steps_completed = 0
        total_steps = 4  # Total steps in banking procedure

        # Step 1: Move to bank position and click
        self.logger.info(Fore.BLACK + "Moving to bank position.")
        wait_time = INTERACTION_WAIT(*interaction_wait)
        mouse_controller.move(*positions["bank_pos"], duration=wait_time)
        time.sleep(wait_time)
        mouse_controller.click()
        time.sleep(interface_wait)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps, None)

        # Step 2: Move to deposit all position and click
        self.logger.info(Fore.BLACK + "Moving to deposit all position.")
        wait_time = INTERACTION_WAIT(*interaction_wait)
        mouse_controller.move(*positions["deposit_all_pos"], duration=wait_time)
        time.sleep(wait_time)
        mouse_controller.click()
        time.sleep(interface_wait)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps, None)

        # Step 3: Move to bank item position and shift double-click
        self.logger.info(Fore.BLACK + "Moving to bank item position.")
        wait_time = INTERACTION_WAIT(*interaction_wait)
        mouse_controller.move(*positions["bank_item_pos"], duration=wait_time)
        time.sleep(wait_time)
        self.logger.info(Fore.BLACK + "Performing shift double-click on bank item.")
        keyboard_controller.press(Key.shift)
        mouse_controller.double_click()
        keyboard_controller.release(Key.shift)
        time.sleep(interface_wait)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps, None)

        # Step 4: Press ESC twice to close bank interface
        self.logger.info(Fore.BLACK + "Pressing ESC to close bank interface.")
        for _ in range(2):
            keyboard_controller.press(Key.esc)
            keyboard_controller.release(Key.esc)
            time.sleep(interface_wait)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps, None)

        self.logger.info(Fore.CYAN + f"Completed Banking Procedure (Run {run_number}).")
        self.update_current_progress(
            total_steps, total_steps, "0:00:00"
        )  # No ETA needed

    def cooking_procedure(
        self,
        run_number,
        cooking_repeat,
        tick_time,
        speculative_mode,
        cooking_loop_target,
        positions,
        interaction_wait,
        interface_wait,
        mouse_controller,
    ):
        """Executes the cooking steps."""
        self.logger.info(
            Fore.GREEN + f"Starting Cooking Procedure (Run {run_number})..."
        )
        wait_time = INTERACTION_WAIT(*interaction_wait)

        # Open inventory
        self.logger.info(Fore.BLACK + "Pressing 'q' to open inventory.")
        keyboard_controller.press("q")
        keyboard_controller.release("q")
        time.sleep(wait_time)

        # Open cooking interface
        self.logger.info(Fore.BLACK + "Pressing 'w' to open cooking interface.")
        keyboard_controller.press("w")
        keyboard_controller.release("w")

        # Start pressing '1' continuously
        stop_event = threading.Event()
        key_thread = threading.Thread(
            target=press_key_continuously, args=("1", stop_event)
        )
        key_thread.start()

        total_start_time = time.time()
        step_times_list = []
        eta_iterations = 1
        recent_iterations = []
        steps_completed = 0
        total_steps = cooking_repeat * 2

        try:
            for i in range(1, cooking_repeat + 1):
                check_events()
                loop_start_time = time.time()

                self.logger.info(
                    Fore.LIGHTCYAN_EX + f"Cooking loop iteration {i}/{cooking_repeat}."
                )

                # Step 1: Move to inventory food position and click
                self.logger.info(Fore.BLACK + "Moving to inventory food position.")
                step_start = time.time()
                wait_time = INTERACTION_WAIT(*interaction_wait)
                mouse_controller.move(*positions["inven_food_pos"], duration=wait_time)
                time.sleep(wait_time)
                mouse_controller.click()
                step_times = {"Step 1": time.time() - step_start}
                steps_completed += 1
                self.update_current_progress(steps_completed, total_steps, None)

                # Step 2: Move to cook food position and click
                self.logger.info(Fore.BLACK + "Moving to cook food position.")
                step_start = time.time()
                wait_time = INTERACTION_WAIT(*interaction_wait)
                mouse_controller.move(*positions["cook_food_pos"], duration=wait_time)
                time.sleep(wait_time)
                mouse_controller.click()
                step_times["Step 2"] = time.time() - step_start
                steps_completed += 1
                self.update_current_progress(steps_completed, total_steps, None)

                # Calculate elapsed time for the loop
                elapsed_time = time.time() - loop_start_time

                if speculative_mode:
                    # Adjust sleep to match cooking loop target
                    sleep_time = cooking_loop_target - elapsed_time
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    else:
                        self.logger.warning(
                            Fore.RED
                            + f"Warning: Cooking loop exceeded target of {cooking_loop_target:.2f} seconds."
                        )
                else:
                    # Sleep based on tick time
                    sleep_time = tick_time - elapsed_time
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    else:
                        self.logger.warning(
                            Fore.RED
                            + f"Warning: Cooking loop exceeded tick time of {tick_time:.2f} seconds."
                        )

                # Record loop execution time
                total_loop_time = time.time() - loop_start_time
                step_times["Total Loop"] = total_loop_time
                step_times_list.append(step_times)

                # Update ETA based on recent iterations
                recent_iterations.append(total_loop_time)
                if len(recent_iterations) > eta_iterations:
                    recent_iterations.pop(0)
                average_time = sum(recent_iterations) / len(recent_iterations)
                remaining_iterations = cooking_repeat - i
                eta = average_time * remaining_iterations
                eta_str = time.strftime("%H:%M:%S", time.gmtime(eta))

                self.logger.info(Fore.BLUE + f"Iteration {i} times: {step_times}")

                # Update current progress with ETA
                self.update_current_progress(steps_completed, total_steps, eta_str)

        finally:
            # Stop pressing '1'
            stop_event.set()
            key_thread.join()
            total_execution_time = time.time() - total_start_time
            self.logger.info(
                Fore.GREEN + f"Completed Cooking Procedure (Run {run_number})."
            )
            self.logger.info(
                Fore.BLUE + f"Total execution time: {total_execution_time:.2f} seconds."
            )

            # Log individual step times
            for idx, times in enumerate(step_times_list, 1):
                self.logger.info(Fore.BLUE + f"Iteration {idx} times: {times}")

    # Hotkey callback methods
    def hotkey_start_script(self):
        """Starts the script via hotkey."""
        self.root.after(0, self.start_script)

    def hotkey_pause_script(self):
        """Pauses or resumes the script via hotkey."""
        self.root.after(0, self.pause_script)

    def hotkey_stop_script(self):
        """Stops the script via hotkey."""
        self.root.after(0, self.stop_script)


if __name__ == "__main__":
    # Initialize and run the GUI
    root = tk.Tk()
    app = MacroGUI(root)
    root.mainloop()
