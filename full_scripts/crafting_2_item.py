import functools
import json
import logging
import os
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
    # Main macro positions
    "bank_pos": (902, 810),
    "deposit_all_pos": (313, 954),
    "bank_item1_pos": (610, 723),
    "bank_item2_pos": (650, 723),
    "item_pos1": (1200, 800),
    "item_pos2": (1250, 800),
}

# Default positions for herb cleaner
default_herb_positions = {
    "herb_bank_pos": (902, 810),
    "herb_deposit_all_pos": (313, 954),
    "herb_bank_item_pos": (610, 723),
    "top_left_pos": (0, 0),
    "bottom_right_pos": (0, 0),
}

# Event flags to control script execution
start_event = threading.Event()
pause_event = threading.Event()
kill_event = threading.Event()

CONFIG_FILE = 'macro_config.json'


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


special_keys = {
    'space': Key.space,
    'esc': Key.esc,
    'enter': Key.enter,
    'shift': Key.shift,
    'ctrl': Key.ctrl,
    'alt': Key.alt,
    'tab': Key.tab,
    'caps_lock': Key.caps_lock,
    'backspace': Key.backspace,
    'delete': Key.delete,
    'up': Key.up,
    'down': Key.down,
    'left': Key.left,
    'right': Key.right,
    'home': Key.home,
    'end': Key.end,
    'page_up': Key.page_up,
    'page_down': Key.page_down,
    'f1': Key.f1,
    'f2': Key.f2,
    'f3': Key.f3,
    'f4': Key.f4,
    'f5': Key.f5,
    'f6': Key.f6,
    'f7': Key.f7,
    'f8': Key.f8,
    'f9': Key.f9,
    'f10': Key.f10,
    'f11': Key.f11,
    'f12': Key.f12,
    # Add more as needed
}


def get_key_code(key_str):
    key_str = key_str.lower()
    return special_keys.get(key_str, key_str)


class MacroGUI:
    """Graphical User Interface for the Game Macro Script."""

    def __init__(self, root):
        self.root = root
        self.root.title("Game Macro Script")
        self.running = False

        # Initialize configuration
        self.config = {
            'main': {},
            'herb_cleaner': {},
            'positions': default_positions.copy(),
            'herb_positions': default_herb_positions.copy()
        }
        self.load_config()

        # Create Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')

        # Frames for each tab
        self.main_frame = tk.Frame(self.notebook)
        self.herb_frame = tk.Frame(self.notebook)
        self.notebook.add(self.main_frame, text='Main Macro')
        self.notebook.add(self.herb_frame, text='Herb Cleaner')

        # Input parameters with default values
        self.num_runs = tk.IntVar(value=self.config['main'].get('num_runs', 10))
        self.number_craft = tk.IntVar(value=self.config['main'].get('number_craft', 14))
        self.num_ticks_per_craft = tk.IntVar(value=self.config['main'].get('num_ticks_per_craft', 1))
        self.tick_time = tk.DoubleVar(value=self.config['main'].get('tick_time', 0.6))
        self.interaction_wait_min = tk.DoubleVar(value=self.config['main'].get('interaction_wait_min', 0.02))
        self.interaction_wait_max = tk.DoubleVar(value=self.config['main'].get('interaction_wait_max', 0.05))
        self.mouse_method = tk.StringVar(value=self.config['main'].get('mouse_method', 'standard'))
        self.interface_wait = tk.DoubleVar(value=self.config['main'].get('interface_wait', 0.5))
        self.font_size = tk.IntVar(value=self.config['main'].get('font_size', 10))
        self.dark_mode = tk.BooleanVar(value=self.config['main'].get('dark_mode', False))

        # Configurable keys
        self.open_tab_key = tk.StringVar(value=self.config['main'].get('open_tab_key', 'q'))
        self.open_inventory_key = tk.StringVar(value=self.config['main'].get('open_inventory_key', 'w'))
        self.confirm_key = tk.StringVar(value=self.config['main'].get('confirm_key', 'space'))
        self.close_interface_key = tk.StringVar(value=self.config['main'].get('close_interface_key', 'esc'))
        self.confirm_key_duration = tk.DoubleVar(value=self.config['main'].get('confirm_key_duration', 1.0))

        # Herb Cleaner specific variables
        self.herb_num_runs = tk.IntVar(value=self.config['herb_cleaner'].get('num_runs', 10))
        self.herb_interaction_wait_min = tk.DoubleVar(
            value=self.config['herb_cleaner'].get('interaction_wait_min', 0.02))
        self.herb_interaction_wait_max = tk.DoubleVar(
            value=self.config['herb_cleaner'].get('interaction_wait_max', 0.05))
        self.herb_interface_wait = tk.DoubleVar(value=self.config['herb_cleaner'].get('interface_wait', 0.5))
        self.herb_font_size = tk.IntVar(value=self.config['herb_cleaner'].get('font_size', 10))

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
        self.herb_font_size.trace("w", self.update_font_size)

    def create_widgets(self):
        """Creates and arranges all GUI widgets."""

        # === Main Macro Tab ===
        param_frame = tk.Frame(self.main_frame)
        param_frame.pack(pady=10)

        row = 0
        # Number of Runs
        tk.Label(param_frame, text="Number of Runs:").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(param_frame, textvariable=self.num_runs).grid(row=row, column=1)
        row += 1

        # Number of Crafts
        tk.Label(param_frame, text="Number of Crafts:").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(param_frame, textvariable=self.number_craft).grid(row=row, column=1)
        row += 1

        # Ticks per Craft
        tk.Label(param_frame, text="Ticks per Craft:").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(param_frame, textvariable=self.num_ticks_per_craft).grid(
            row=row, column=1
        )
        row += 1

        # Tick Time
        tk.Label(param_frame, text="Tick Time (s):").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(param_frame, textvariable=self.tick_time).grid(row=row, column=1)
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
        row += 1  # Increment row to prevent overlapping

        # Configurable Keys Frame
        keys_frame = tk.LabelFrame(self.main_frame, text="Configurable Keys")
        keys_frame.pack(pady=10)

        row = 0
        # Open Tab Key
        tk.Label(keys_frame, text="Open Tab Key:").grid(row=row, column=0, sticky="e")
        tk.Entry(keys_frame, textvariable=self.open_tab_key).grid(row=row, column=1)
        row += 1

        # Open Inventory Key
        tk.Label(keys_frame, text="Open Inventory Key:").grid(row=row, column=0, sticky="e")
        tk.Entry(keys_frame, textvariable=self.open_inventory_key).grid(row=row, column=1)
        row += 1

        # Confirm Key
        tk.Label(keys_frame, text="Confirm Key:").grid(row=row, column=0, sticky="e")
        tk.Entry(keys_frame, textvariable=self.confirm_key).grid(row=row, column=1)
        row += 1

        # Confirm Key Duration
        tk.Label(keys_frame, text="Confirm Key Spam Duration (s):").grid(row=row, column=0, sticky="e")
        tk.Entry(keys_frame, textvariable=self.confirm_key_duration).grid(row=row, column=1)
        row += 1

        # Close Interface Key
        tk.Label(keys_frame, text="Close Interface Key:").grid(row=row, column=0, sticky="e")
        tk.Entry(keys_frame, textvariable=self.close_interface_key).grid(row=row, column=1)
        row += 1

        # Frame for control buttons
        control_frame = tk.Frame(self.main_frame)
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
        progress_frame = tk.Frame(self.main_frame)
        progress_frame.pack(pady=10, fill="x")

        # Current Procedure Progress
        tk.Label(progress_frame, text="Current Procedure Progress:").grid(
            row=0, column=0, sticky="w"
        )
        self.current_progress = ttk.Progressbar(
            progress_frame, length=400, mode="determinate"
        )
        self.current_progress.grid(row=1, column=0, padx=5, pady=5)
        self.current_progress_label = tk.Label(progress_frame, text="0/0 Steps (0.00%)")
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
            self.main_frame,
            state="disabled",
            width=80,
            height=10,
            font=("TkDefaultFont", font_size),
        )
        self.log_output.pack(pady=10)

        # Info Box for Main Macro
        info_text = (
            "Main Macro Procedure:\n"
            "- The script automates a crafting procedure involving two items.\n"
            "- It performs banking operations, withdraws items, and crafts them.\n"
            "\nConfiguration Variables:\n"
            "- Number of Runs: Total iterations the script will perform.\n"
            "- Number of Crafts: Number of times to craft per run.\n"
            "- Ticks per Craft: Game ticks required per craft.\n"
            "- Tick Time: Duration of a game tick in seconds.\n"
            "- Total Crafting Time = Number of Crafts * Ticks per Craft * Tick Time.\n"
            "- Interaction Wait Min/Max: Random wait time range between interactions.\n"
            "- Mouse Method: Method used for mouse movements (e.g., standard).\n"
            "- Interface Wait: Time to wait after an interface action.\n"
            "- Configurable Keys: Keys used to interact with the game.\n"
        )
        info_box = tk.Message(self.main_frame, text=info_text, width=600)
        info_box.pack(pady=10)

        # === Herb Cleaner Tab ===
        herb_param_frame = tk.Frame(self.herb_frame)
        herb_param_frame.pack(pady=10)

        row = 0
        # Number of Runs
        tk.Label(herb_param_frame, text="Number of Runs:").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(herb_param_frame, textvariable=self.herb_num_runs).grid(row=row, column=1)
        row += 1

        # Interaction Wait Min
        tk.Label(herb_param_frame, text="Interaction Wait Min (s):").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(herb_param_frame, textvariable=self.herb_interaction_wait_min).grid(
            row=row, column=1
        )
        row += 1

        # Interaction Wait Max
        tk.Label(herb_param_frame, text="Interaction Wait Max (s):").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(herb_param_frame, textvariable=self.herb_interaction_wait_max).grid(
            row=row, column=1
        )
        row += 1

        # Interface Wait
        tk.Label(herb_param_frame, text="Interface Wait (s):").grid(
            row=row, column=0, sticky="e"
        )
        tk.Entry(herb_param_frame, textvariable=self.herb_interface_wait).grid(row=row, column=1)
        row += 1

        # Font Size
        tk.Label(herb_param_frame, text="Font Size:").grid(row=row, column=0, sticky="e")
        tk.Entry(herb_param_frame, textvariable=self.herb_font_size).grid(row=row, column=1)
        row += 1

        # Configure Inventory Positions Button
        tk.Button(
            herb_param_frame, text="Configure Herb Positions", command=self.configure_herb_positions
        ).grid(row=row, column=0, columnspan=2, pady=5)
        row += 1  # Increment row to prevent overlapping

        # Herb Control Frame
        herb_control_frame = tk.Frame(self.herb_frame)
        herb_control_frame.pack(pady=10)

        # Start Herb Cleaner Button
        self.herb_start_button = tk.Button(
            herb_control_frame, text="Start Herb Cleaner", command=self.start_herb_script
        )
        self.herb_start_button.grid(row=0, column=0, padx=5)

        # Pause Herb Cleaner Button
        self.herb_pause_button = tk.Button(
            herb_control_frame,
            text="Pause Script",
            command=self.pause_script,
            state="disabled",
        )
        self.herb_pause_button.grid(row=0, column=1, padx=5)

        # Stop Herb Cleaner Button
        self.herb_stop_button = tk.Button(
            herb_control_frame,
            text="Stop Script",
            command=self.stop_script,
            state="disabled",
        )
        self.herb_stop_button.grid(row=0, column=2, padx=5)

        # Herb Log Output
        herb_font_size = self.herb_font_size.get()
        self.herb_log_output = scrolledtext.ScrolledText(
            self.herb_frame,
            state="disabled",
            width=80,
            height=10,
            font=("TkDefaultFont", herb_font_size),
        )
        self.herb_log_output.pack(pady=10)

        # Info Box for Herb Cleaner
        herb_info_text = (
            "Herb Cleaner Procedure:\n"
            "- Automates cleaning herbs in your inventory.\n"
            "- Performs banking to withdraw unclean herbs and then cleans them.\n"
            "- Uses a 4x7 grid based on the top-left and bottom-right inventory positions.\n"
            "\nConfiguration Variables:\n"
            "- Number of Runs: Total iterations the script will perform.\n"
            "- Interaction Wait Min/Max: Random wait time range between interactions.\n"
            "- Interface Wait: Time to wait after an interface action.\n"
            "- Configure Herb Positions: Set banking positions and inventory grid positions.\n"
        )
        herb_info_box = tk.Message(self.herb_frame, text=herb_info_text, width=600)
        herb_info_box.pack(pady=10)

    def update_font_size(self, *args):
        """Updates the font size of the log output."""
        font_size = self.font_size.get()
        self.log_output.configure(font=("TkDefaultFont", font_size))
        herb_font_size = self.herb_font_size.get()
        self.herb_log_output.configure(font=("TkDefaultFont", herb_font_size))

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
        for key, value in self.config['positions'].items():
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
                self.config['positions'][key] = (x_var.get(), y_var.get())
            self.save_config()
            pos_window.destroy()

        tk.Button(pos_window, text="Save", command=save_positions).grid(
            row=row, column=0, columnspan=4, pady=5
        )

    def configure_herb_positions(self):
        """Configure positions for the herb cleaner."""
        pos_window = tk.Toplevel(self.root)
        pos_window.title("Configure Herb Cleaner Positions")

        pos_vars = {}
        row = 0
        for key in ['herb_bank_pos', 'herb_deposit_all_pos', 'herb_bank_item_pos', 'top_left_pos', 'bottom_right_pos']:
            value = self.config['herb_positions'].get(key, (0, 0))
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
                command=functools.partial(self.set_herb_position, key, x_var, y_var),
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
                self.config['herb_positions'][key] = (x_var.get(), y_var.get())
            self.save_config()
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
            self.root.after(0, self.update_position, key, x_var, y_var, x, y)

        threading.Thread(target=wait_for_click).start()

    def update_position(self, key, x_var, y_var, x, y):
        """Updates the position variables and re-enables the GUI."""
        x_var.set(x)
        y_var.set(y)
        self.config['positions'][key] = (x, y)
        self.save_config()
        self.root.attributes("-disabled", False)

    def set_herb_position(self, key, x_var, y_var):
        """Sets a specific herb position based on the next left-click."""
        # Disable GUI interactions
        self.root.attributes("-disabled", True)

        def wait_for_click():
            # Wait for left mouse button down event
            mouse.wait(button="left", target_types=("down",))
            x, y = mouse.get_position()
            # Update position in the GUI thread
            self.root.after(0, self.update_herb_position, key, x_var, y_var, x, y)

        threading.Thread(target=wait_for_click).start()

    def update_herb_position(self, key, x_var, y_var, x, y):
        """Updates the herb position variables and re-enables the GUI."""
        x_var.set(x)
        y_var.set(y)
        self.config['herb_positions'][key] = (x, y)
        self.save_config()
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
            self.root.after(0, lambda: messagebox.showinfo("Script Running", "The script is already running."))

    def start_herb_script(self):
        """Starts the herb cleaner script if not already running."""
        if not self.running:
            self.running = True
            self.herb_start_button.config(state="disabled")
            self.herb_pause_button.config(state="normal")
            self.herb_stop_button.config(state="normal")
            self.script_thread = threading.Thread(target=self.run_herb_script)
            self.script_thread.start()
        else:
            self.root.after(0, lambda: messagebox.showinfo("Script Running", "The script is already running."))

    def pause_script(self):
        """Pauses or resumes the macro script."""
        if self.running:
            if pause_event.is_set():
                pause_event.clear()
                self.pause_button.config(text="Pause Script")
                self.herb_pause_button.config(text="Pause Script")
                self.logger.info(Fore.MAGENTA + "Script resumed.")
            else:
                pause_event.set()
                self.pause_button.config(text="Resume Script")
                self.herb_pause_button.config(text="Resume Script")
                self.logger.info(Fore.MAGENTA + "Script paused.")

    def stop_script(self):
        """Stops the macro script and resets the UI."""
        if self.running:
            kill_event.set()
            pause_event.clear()  # Ensure the script isn't paused
            if threading.current_thread() != self.script_thread:
                self.script_thread.join()
                self.root.after(0, self.reset_ui_elements)
            else:
                self.root.after(0, self.reset_ui_elements)
            self.running = False
        else:
            self.root.after(0, lambda: messagebox.showinfo("Script Not Running", "The script is not running."))

    def reset_ui_elements(self):
        """Resets the UI elements after the script stops."""
        self.start_button.config(state="normal")
        self.pause_button.config(state="disabled", text="Pause Script")
        self.stop_button.config(state="disabled")
        self.herb_start_button.config(state="normal")
        self.herb_pause_button.config(state="disabled", text="Pause Script")
        self.herb_stop_button.config(state="disabled")
        # Reset events
        start_event.clear()
        kill_event.clear()
        self.logger.info(Fore.RED + "Script stopped.")
        # Reset progress bars
        self.reset_progress_bars()

    def reset_progress_bars(self):
        """Resets all progress bars and their labels."""
        # Reset Current Procedure Progress
        self.current_progress["value"] = 0
        self.current_progress_label.config(text="0/0 Steps (0.00%)")
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
        # Start logging
        self.logger.info(Fore.BLUE + "Script started.")
        self.overall_start_time = time.time()
        self.running = True  # Ensure running is set to True

        try:
            self.reload_config()  # Reload configuration

            # Estimate total time per run
            banking_time = self.estimate_banking_time()
            crafting_time = self.estimate_crafting_time()
            self.estimated_time_per_run = banking_time + crafting_time
            self.total_estimated_time = self.num_runs_value * self.estimated_time_per_run

            # Start the ETA update loop
            self.root.after(0, self.update_eta_loop)

            for run_number in range(1, self.num_runs.get() + 1):
                check_events()
                self.update_overall_progress(run_number - 1, self.num_runs.get())
                self.current_progress["maximum"] = 5  # total steps in banking_procedure
                self.current_procedure_start_time = time.time()
                self.current_procedure_total_time = banking_time
                self.banking_procedure(run_number)
                check_events()
                self.current_progress["maximum"] = 6  # total steps in crafting_procedure
                self.current_procedure_start_time = time.time()
                self.current_procedure_total_time = crafting_time
                self.crafting_procedure(run_number)
                self.update_overall_progress(run_number, self.num_runs.get())
            self.logger.info(Fore.BLUE + "Completed all runs.")
            self.stop_script()
        except KillScriptException:
            self.logger.info(Fore.RED + "Script terminated.")
            self.stop_script()
        except Exception as e:
            self.logger.error(Fore.RED + f"An error occurred: {e}")
            self.stop_script()

    def run_herb_script(self):
        """Runs the herb cleaner script."""
        # Start logging
        self.logger.info(Fore.BLUE + "Herb Cleaner Script started.")
        self.overall_start_time = time.time()
        self.running = True  # Ensure running is set to True

        try:
            self.reload_config()  # Reload configuration

            # Estimate total time per run
            herb_banking_time = self.estimate_herb_banking_time()
            cleaning_time = self.estimate_cleaning_time()
            self.estimated_time_per_run = herb_banking_time + cleaning_time
            self.total_estimated_time = self.herb_num_runs_value * self.estimated_time_per_run

            # Start the ETA update loop
            self.root.after(0, self.update_eta_loop)

            for run_number in range(1, self.herb_num_runs.get() + 1):
                check_events()
                self.update_overall_progress(run_number - 1, self.herb_num_runs.get())
                self.current_progress["maximum"] = 4  # total steps in herb banking_procedure
                self.current_procedure_start_time = time.time()
                self.current_procedure_total_time = herb_banking_time
                self.herb_banking_procedure(run_number)
                check_events()
                self.current_progress["maximum"] = 28  # total steps in cleaning procedure
                self.current_procedure_start_time = time.time()
                self.current_procedure_total_time = cleaning_time
                self.cleaning_procedure(run_number)
                self.update_overall_progress(run_number, self.herb_num_runs.get())
            self.logger.info(Fore.BLUE + "Completed all runs.")
            self.stop_script()
        except KillScriptException:
            self.logger.info(Fore.RED + "Script terminated.")
            self.stop_script()
        except Exception as e:
            self.logger.error(Fore.RED + f"An error occurred: {e}")
            self.stop_script()

    def reload_config(self):
        """Reloads the configuration from GUI variables."""
        # Retrieve input parameters
        self.num_runs_value = self.num_runs.get()
        self.number_craft_value = self.number_craft.get()
        self.num_ticks_per_craft_value = self.num_ticks_per_craft.get()
        self.tick_time_value = self.tick_time.get()
        self.interaction_wait = (self.interaction_wait_min.get(), self.interaction_wait_max.get())
        self.positions_value = self.config['positions'].copy()
        self.interface_wait_value = self.interface_wait.get()
        self.mouse_method_value = self.mouse_method.get()
        self.open_tab_key_value = get_key_code(self.open_tab_key.get())
        self.open_inventory_key_value = get_key_code(self.open_inventory_key.get())
        self.confirm_key_value = get_key_code(self.confirm_key.get())
        self.confirm_key_duration_value = self.confirm_key_duration.get()
        self.close_interface_key_value = get_key_code(self.close_interface_key.get())

        # Herb Cleaner Config
        self.herb_num_runs_value = self.herb_num_runs.get()
        self.herb_interaction_wait = (self.herb_interaction_wait_min.get(), self.herb_interaction_wait_max.get())
        self.herb_interface_wait_value = self.herb_interface_wait.get()
        self.herb_positions_value = self.config['herb_positions'].copy()
        self.top_left_pos_value = self.herb_positions_value.get('top_left_pos', (0, 0))
        self.bottom_right_pos_value = self.herb_positions_value.get('bottom_right_pos', (0, 0))

        # Initialize MouseController
        self.mouse_controller = MouseController(
            method=self.mouse_method_value, interface_wait=self.interface_wait_value
        )

        # Save config
        self.save_config()

    def update_overall_progress(self, run_number, total_runs):
        """Updates the overall progress bar."""
        percent = (run_number / total_runs) * 100
        self.root.after(0, self._update_overall_progress_ui, run_number, total_runs, percent)

    def _update_overall_progress_ui(self, run_number, total_runs, percent):
        self.overall_progress["value"] = run_number
        self.overall_progress_label.config(
            text=f"{run_number}/{total_runs} Runs ({percent:.2f}%)"
        )
        self.overall_progress_percent_label.config(text=f"{percent:.2f}%")
        # ETA will be updated in the update_eta_loop method

    def update_current_progress(self, steps_completed, total_steps):
        """Updates the current procedure's progress bar."""
        self.root.after(0, self._update_current_progress_ui, steps_completed, total_steps)

    def _update_current_progress_ui(self, steps_completed, total_steps):
        """Updates the current procedure's progress bar and ETA."""
        percent = (steps_completed / total_steps) * 100
        self.current_progress["value"] = steps_completed
        self.current_progress_label.config(
            text=f"{steps_completed}/{total_steps} Steps ({percent:.2f}%)"
        )
        self.current_progress_percent_label.config(text=f"{percent:.2f}%")

        # Calculate ETA
        elapsed = time.time() - self.current_procedure_start_time
        eta = self.current_procedure_total_time - elapsed
        if eta < 0:
            eta = 0
        eta_str = time.strftime("%H:%M:%S", time.gmtime(eta))
        self.current_progress_eta_label.config(text=f"ETA: {eta_str}")

    def update_eta_loop(self):
        """Periodically updates the ETA labels."""
        if self.running:
            # Update overall ETA
            elapsed = time.time() - self.overall_start_time
            eta = self.total_estimated_time - elapsed
            if eta < 0:
                eta = 0
            eta_str = time.strftime("%H:%M:%S", time.gmtime(eta))
            self.overall_progress_eta_label.config(text=f"ETA: {eta_str}")

            # Schedule next update
            self.root.after(1000, self.update_eta_loop)

    def estimate_banking_time(self):
        """Estimates the time required for the banking procedure."""
        steps = 5
        avg_interaction_wait = sum(self.interaction_wait) / 2
        total_time = (
            steps * avg_interaction_wait +
            steps * self.interface_wait_value
        )
        return total_time

    def estimate_crafting_time(self):
        """Estimates the time required for the crafting procedure."""
        steps = 6
        avg_interaction_wait = sum(self.interaction_wait) / 2
        total_time = (
            steps * avg_interaction_wait +
            steps * self.interface_wait_value +
            self.confirm_key_duration_value +
            self.number_craft_value * self.num_ticks_per_craft_value * self.tick_time_value
        )
        return total_time

    def estimate_herb_banking_time(self):
        """Estimates the time required for the herb banking procedure."""
        steps = 4
        avg_interaction_wait = sum(self.herb_interaction_wait) / 2
        total_time = (
            steps * avg_interaction_wait +
            steps * self.herb_interface_wait_value
        )
        return total_time

    def estimate_cleaning_time(self):
        """Estimates the time required for the cleaning procedure."""
        steps = 28
        avg_interaction_wait = sum(self.herb_interaction_wait) / 2
        total_time = (
            steps * avg_interaction_wait +
            steps * self.herb_interface_wait_value
        )
        return total_time

    def banking_procedure(self, run_number):
        """Executes the banking steps for the main macro."""
        self.logger.info(
            Fore.CYAN + f"Starting Banking Procedure (Run {run_number})..."
        )
        steps_completed = 0
        total_steps = 5  # Total steps in banking procedure

        # Step 1: Move to bank position and click
        self.logger.info(Fore.BLACK + "Moving to bank position.")
        wait_time = INTERACTION_WAIT(*self.interaction_wait)
        self.mouse_controller.move(*self.positions_value["bank_pos"], duration=wait_time)
        time.sleep(wait_time)
        self.mouse_controller.click()
        time.sleep(self.interface_wait_value)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)

        # Step 2: Move to deposit all position and click
        self.logger.info(Fore.BLACK + "Moving to deposit all position.")
        wait_time = INTERACTION_WAIT(*self.interaction_wait)
        self.mouse_controller.move(*self.positions_value["deposit_all_pos"], duration=wait_time)
        time.sleep(wait_time)
        self.mouse_controller.click()
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)

        # Step 3: Move to bank item 1 position and shift-click
        self.logger.info(Fore.BLACK + "Moving to bank item 1 position.")
        wait_time = INTERACTION_WAIT(*self.interaction_wait)
        self.mouse_controller.move(*self.positions_value["bank_item1_pos"], duration=wait_time)
        time.sleep(wait_time)
        self.logger.info(Fore.BLACK + "Performing shift-click on bank item 1.")
        keyboard_controller.press(Key.shift)
        self.mouse_controller.click()
        keyboard_controller.release(Key.shift)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)

        # Step 4: Move to bank item 2 position and shift-click
        self.logger.info(Fore.BLACK + "Moving to bank item 2 position.")
        wait_time = INTERACTION_WAIT(*self.interaction_wait)
        self.mouse_controller.move(*self.positions_value["bank_item2_pos"], duration=wait_time)
        time.sleep(wait_time)
        self.logger.info(Fore.BLACK + "Performing shift-click on bank item 2.")
        keyboard_controller.press(Key.shift)
        self.mouse_controller.click()
        keyboard_controller.release(Key.shift)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)

        # Step 5: Close bank interface using configurable key
        self.logger.info(Fore.BLACK + f"Closing bank interface using '{self.close_interface_key.get()}' key.")
        key_code = self.close_interface_key_value
        keyboard_controller.press(key_code)
        keyboard_controller.release(key_code)
        time.sleep(self.interface_wait_value)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)

        self.logger.info(Fore.CYAN + f"Completed Banking Procedure (Run {run_number}).")
        self.update_current_progress(
            total_steps, total_steps
        )  # No ETA needed

    def herb_banking_procedure(self, run_number):
        """Executes the banking steps for the herb cleaner."""
        self.logger.info(
            Fore.CYAN + f"Starting Banking Procedure (Run {run_number})..."
        )
        steps_completed = 0
        total_steps = 4  # Total steps in banking procedure for herb cleaner

        # Step 1: Move to herb bank position and click
        self.logger.info(Fore.BLACK + "Moving to herb bank position.")
        wait_time = INTERACTION_WAIT(*self.herb_interaction_wait)
        self.mouse_controller.move(*self.herb_positions_value["herb_bank_pos"], duration=wait_time)
        time.sleep(wait_time)
        self.mouse_controller.click()
        time.sleep(self.herb_interface_wait_value)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)

        # Step 2: Move to herb deposit all position and click
        self.logger.info(Fore.BLACK + "Moving to herb deposit all position.")
        wait_time = INTERACTION_WAIT(*self.herb_interaction_wait)
        self.mouse_controller.move(*self.herb_positions_value["herb_deposit_all_pos"], duration=wait_time)
        time.sleep(wait_time)
        self.mouse_controller.click()
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)

        # Step 3: Move to herb bank item position and shift-click
        self.logger.info(Fore.BLACK + "Moving to herb bank item position.")
        wait_time = INTERACTION_WAIT(*self.herb_interaction_wait)
        self.mouse_controller.move(*self.herb_positions_value["herb_bank_item_pos"], duration=wait_time)
        time.sleep(wait_time)
        self.logger.info(Fore.BLACK + "Performing shift-click on herb bank item.")
        keyboard_controller.press(Key.shift)
        self.mouse_controller.click()
        keyboard_controller.release(Key.shift)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)

        # Step 4: Close bank interface using configurable key
        self.logger.info(Fore.BLACK + f"Closing bank interface using '{self.close_interface_key.get()}' key.")
        key_code = self.close_interface_key_value
        keyboard_controller.press(key_code)
        keyboard_controller.release(key_code)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)

        self.logger.info(Fore.CYAN + f"Completed Banking Procedure (Run {run_number}).")
        self.update_current_progress(
            total_steps, total_steps
        )  # No ETA needed

    def crafting_procedure(self, run_number):
        """Executes the crafting steps."""
        self.logger.info(
            Fore.GREEN + f"Starting Crafting Procedure (Run {run_number})..."
        )
        steps_completed = 0
        total_steps = 6  # Total steps in crafting procedure

        # Step 1: Press open_tab_key to open tab
        self.logger.info(Fore.BLACK + f"Pressing '{self.open_tab_key.get()}' to open tab.")
        key_code = self.open_tab_key_value
        keyboard_controller.press(key_code)
        keyboard_controller.release(key_code)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)
        check_events()

        # Step 2: Press open_inventory_key to open inventory
        self.logger.info(Fore.BLACK + f"Pressing '{self.open_inventory_key.get()}' to open inventory.")
        key_code = self.open_inventory_key_value
        keyboard_controller.press(key_code)
        keyboard_controller.release(key_code)
        time.sleep(self.interface_wait_value)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)
        check_events()

        # Step 3: Move to item_pos1 and click
        self.logger.info(Fore.BLACK + "Moving to item position 1.")
        wait_time = INTERACTION_WAIT(*self.interaction_wait)
        self.mouse_controller.move(*self.positions_value["item_pos1"], duration=wait_time)
        time.sleep(wait_time)
        self.mouse_controller.click()
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)
        check_events()

        # Step 4: Move to item_pos2 and click
        self.logger.info(Fore.BLACK + "Moving to item position 2.")
        wait_time = INTERACTION_WAIT(*self.interaction_wait)
        self.mouse_controller.move(*self.positions_value["item_pos2"], duration=wait_time)
        time.sleep(wait_time)
        self.mouse_controller.click()
        time.sleep(self.interface_wait_value)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)
        check_events()

        # Step 5: Spam confirm key for specified duration
        self.logger.info(
            Fore.BLACK + f"Spamming confirm key ('{self.confirm_key.get()}') for {self.confirm_key_duration_value} seconds.")
        key_code = self.confirm_key_value
        start_time = time.time()
        while time.time() - start_time < self.confirm_key_duration_value:
            keyboard_controller.press(key_code)
            keyboard_controller.release(key_code)
            time.sleep(0.05)  # Small delay to prevent overloading
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)
        check_events()

        # Step 6: Wait for crafting to finish
        crafting_wait = self.number_craft_value * self.num_ticks_per_craft_value * self.tick_time_value
        self.logger.info(Fore.BLACK + f"Waiting for crafting to finish ({crafting_wait:.2f} seconds).")
        time.sleep(crafting_wait)
        steps_completed += 1
        self.update_current_progress(steps_completed, total_steps)
        check_events()

        self.logger.info(Fore.GREEN + f"Completed Crafting Procedure (Run {run_number}).")
        self.update_current_progress(
            total_steps, total_steps
        )

    def cleaning_procedure(self, run_number):
        """Executes the herb cleaning steps."""
        self.logger.info(
            Fore.GREEN + f"Starting Cleaning Procedure (Run {run_number})..."
        )
        steps_completed = 0
        total_steps = 28  # Total steps in cleaning procedure

        # Number of columns and rows in the grid
        number_of_columns = 4
        number_of_rows = 7

        # Calculate positions in the 7x4 grid
        x_start, y_start = self.top_left_pos_value
        x_end, y_end = self.bottom_right_pos_value

        # Calculate the slot width and height
        slot_width = (x_end - x_start) / (number_of_columns - 1)
        slot_height = (y_end - y_start) / (number_of_rows - 1)

        # Generate positions for the 7x4 grid
        x_positions = [x_start + i * slot_width for i in range(number_of_columns)]
        y_positions = [y_start + i * slot_height for i in range(number_of_rows)]

        # Print grid positions for better visualization
        self.print_grid_positions(x_positions, y_positions)

        positions = [(x, y) for y in y_positions for x in x_positions]

        for idx, pos in enumerate(positions):
            check_events()
            self.logger.info(Fore.BLACK + f"Clicking position {idx + 1}/{len(positions)} at {pos}")
            wait_time = INTERACTION_WAIT(*self.herb_interaction_wait)
            self.mouse_controller.move(*pos, duration=wait_time)
            time.sleep(wait_time)
            self.mouse_controller.click()
            steps_completed += 1
            self.update_current_progress(steps_completed, total_steps)

        self.logger.info(Fore.GREEN + f"Completed Cleaning Procedure (Run {run_number}).")
        self.update_current_progress(
            total_steps, total_steps
        )

    def print_grid_positions(self, x_positions, y_positions):
        """Prints the calculated grid positions in a formatted way."""
        grid_output = "\nHerb Cleaner Grid Positions (4x7):\n"
        grid_output += "--------------------------\n"
        for y in y_positions:
            row = []
            for x in x_positions:
                row.append(f"({int(x)}, {int(y)})")
            grid_output += " | ".join(row) + "\n"
        grid_output += "--------------------------\n"
        self.logger.info(Fore.CYAN + grid_output)

    def save_config(self):
        """Saves the configuration to disk."""
        # Main Macro Config
        self.config['main'] = {
            'num_runs': self.num_runs.get(),
            'number_craft': self.number_craft.get(),
            'num_ticks_per_craft': self.num_ticks_per_craft.get(),
            'tick_time': self.tick_time.get(),
            'interaction_wait_min': self.interaction_wait_min.get(),
            'interaction_wait_max': self.interaction_wait_max.get(),
            'mouse_method': self.mouse_method.get(),
            'interface_wait': self.interface_wait.get(),
            'font_size': self.font_size.get(),
            'dark_mode': self.dark_mode.get(),
            'open_tab_key': self.open_tab_key.get(),
            'open_inventory_key': self.open_inventory_key.get(),
            'confirm_key': self.confirm_key.get(),
            'close_interface_key': self.close_interface_key.get(),
            'confirm_key_duration': self.confirm_key_duration.get()
        }
        # Herb Cleaner Config
        self.config['herb_cleaner'] = {
            'num_runs': self.herb_num_runs.get(),
            'interaction_wait_min': self.herb_interaction_wait_min.get(),
            'interaction_wait_max': self.herb_interaction_wait_max.get(),
            'interface_wait': self.herb_interface_wait.get(),
            'font_size': self.herb_font_size.get()
        }
        # Positions already updated in set_position and set_herb_position
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def load_config(self):
        """Loads the configuration from disk."""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                self.config = json.load(f)

            # Ensure all keys are present
            self.config.setdefault('main', {})
            self.config.setdefault('herb_cleaner', {})
            self.config.setdefault('positions', default_positions.copy())
            self.config.setdefault('herb_positions', default_herb_positions.copy())
        else:
            self.config = {
                'main': {},
                'herb_cleaner': {},
                'positions': default_positions.copy(),
                'herb_positions': default_herb_positions.copy()
            }

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
