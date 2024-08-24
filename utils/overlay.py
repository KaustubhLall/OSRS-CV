import re
import tkinter as tk
from tkinter import TOP

from utils.screen_capture import ScreenCapture


class OverlayDrawer:
    def __init__(self, title="Overlay", window_dimensions=None, relaxed_mode=False):
        self.root = tk.Tk()
        self.root.title(title)
        self.root.overrideredirect(True)  # Remove window decorations
        self.root.attributes('-topmost', True)  # Always on top
        self.root.attributes('-alpha', 0.8)  # Transparency level
        self.text_frame = tk.Frame(self.root, bg="black")
        self.text_frame.pack(side=TOP, padx=5, pady=5)
        self.window_dimensions = window_dimensions  # (left, top, width, height)
        self.relaxed_mode = relaxed_mode
        if window_dimensions:
            self.set_position(window_dimensions[0], window_dimensions[1])  # Initial position
        self._timeout_id = None  # Store the after() ID

    def display_text(self, text, timeout=None, font_size=16):
        self._clear_text()  # Clear previous text
        self._parse_and_display_text(text, font_size)
        self.root.update_idletasks()
        self.root.deiconify()  # Ensure the window is visible

        if timeout:
            # Cancel any existing timeout
            if self._timeout_id:
                self.root.after_cancel(self._timeout_id)
            # Set new timeout
            self._timeout_id = self.root.after(timeout * 1000, self.remove_text)

    def _clear_text(self):
        for widget in self.text_frame.winfo_children():
            widget.destroy()

    def _parse_and_display_text(self, text, default_font_size):
        # Parsing logic remains the same...
        pattern = re.compile(r"<color=(?P<color>[^>]+)>(.*?)</color>|<size=(?P<size>\d+)>(.*?)</size>")
        segments = []
        last_end = 0

        for match in pattern.finditer(text):
            if match.start() > last_end:
                segments.append({"content": text[last_end:match.start()], "size": default_font_size})

            color = match.group("color")
            size = match.group("size")
            if color:
                segments.append({"color": color, "content": match.group(2), "size": default_font_size})
            elif size:
                segments.append({"size": int(size), "content": match.group(4)})
            last_end = match.end()

        if last_end < len(text):
            segments.append({"content": text[last_end:], "size": default_font_size})

        # Display segments
        row = 0
        col = 0
        for segment in segments:
            color = segment.get("color", "white")
            font_size = segment.get("size", default_font_size)
            content = segment.get("content", "")
            label = tk.Label(self.text_frame, text=content, fg=color, bg="black", font=("Helvetica", font_size))
            label.grid(row=row, column=col, sticky="w")
            col += 1
            if "\n" in content:
                row += 1
                col = 0

    def remove_text(self):
        self.root.withdraw()  # Hide the window without closing it

    def set_position(self, x, y):
        self.root.geometry(f"+{x}+{y}")

    def move_by_percentage(self, x_percent=0, y_percent=0):
        """Move the overlay by a percentage of the window's width and height."""
        if not self.window_dimensions:
            return
        delta_x = int(self.window_dimensions[2] * (x_percent / 100))
        delta_y = int(self.window_dimensions[3] * (y_percent / 100))
        self.move_by_pixels(delta_x, delta_y)

    def move_by_pixels(self, delta_x=0, delta_y=0):
        """Move the overlay by a specific number of pixels."""
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        self.set_position(current_x + delta_x, current_y + delta_y)

    def start(self):
        self.root.mainloop()

    def stop(self):
        if self._timeout_id:
            self.root.after_cancel(self._timeout_id)
        self.root.quit()


def main():
    def format_number(number):
        """Formats the number with 'k' for thousands and 'm' for millions."""
        if number >= 1_000_000:
            return f"{number / 1_000_000:.2f}m"
        elif number >= 1_000:
            return f"{number / 1_000:.2f}k"
        else:
            return f"{number:.0f}"

    def format_time(seconds_left):
        hours, remainder = divmod(int(seconds_left), 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        elif minutes > 0:
            return f"{minutes:02}:{seconds:02}"
        else:
            return f"{seconds:02}"

    try:
        # Initialize the screen capture tool
        screen_capture = ScreenCapture()
        screen_capture.set_application(app_name='RuneLite')  # Select an application interactively

        # Get window coordinates and dimensions
        window_coords = screen_capture.get_window_coordinates()
        window_dimensions = (
            window_coords['left'],
            window_coords['top'],
            window_coords['width'],
            window_coords['height']
        )
        window_info = f"Captured: <color=yellow>{screen_capture.app_name}</color>\n" \
                      f"Coordinates: <color=lightblue>{window_coords}</color>"

        # Define dummy values
        alchs_per_second = 1.23
        alchs_per_minute = 74.5
        alchs_per_hour = 4470.0
        exp_per_hour = 180_000
        formatted_exp = format_number(1_200_000)
        ALCH_EXP = 65  # Dummy value
        num_iterations = 1000
        iterations = 500
        OUTPUT_VALUE = 1000
        INPUT_COST = 700
        formatted_profit = format_number(OUTPUT_VALUE * iterations - INPUT_COST * iterations)
        formatted_value = format_number(OUTPUT_VALUE * iterations)
        profit_per_hour = formatted_profit
        time_left = format_time((num_iterations - iterations) / alchs_per_second)

        # Construct the overlay text with the dummy values
        overlay_text = (
            f"<color=lightgreen>Track</color> <color=lightgreen>Live Rate</color> <color=lightgreen>Total</color> <color=lightgreen>Goal  ({time_left})</color>\n"
            f"<color=lightgreen>Alchs:</color> <color=lightblue>{alchs_per_second:>6.2f}/s</color> <color=lightblue>{alchs_per_minute:>7.2f}/min</color> <color=lightblue>{alchs_per_hour:>7.2f}/hr</color>\n"
            f"<color=lightgreen>XP Rate:</color> <color=yellow>{format_number(exp_per_hour):>8} xp/hr</color> <color=yellow>{formatted_exp:>8} xp</color> <color=orange>{format_number(ALCH_EXP * num_iterations):>8} xp</color>\n"
            f"<color=lightgreen>Profit:</color> <color=lightblue>{OUTPUT_VALUE - INPUT_COST:>6} gp/alch</color> <color=yellow>{formatted_profit:>8} gp</color> <color=lightblue>{profit_per_hour:>8} gp/hr</color>\n"
            f"<color=lightgreen>Total Alchs:</color> <color=lightblue>{iterations:>4}/{num_iterations:<4}</color> <color=lightyellow>{formatted_value:>8} gp</color> <color=orange>{num_iterations - iterations:<4} alchs</color>\n"
        )

        # Initialize the first overlay drawer with window dimensions
        overlay1 = OverlayDrawer("Info Overlay 1", window_dimensions=window_dimensions, relaxed_mode=False)
        overlay1.display_text(overlay_text, timeout=10, font_size=18)  # Display for 10 seconds with font size 18

        # Initialize the second overlay drawer with window dimensions
        overlay2 = OverlayDrawer("Info Overlay 2", window_dimensions=window_dimensions, relaxed_mode=False)
        overlay2.display_text(overlay_text, timeout=10, font_size=18)  # Display for 10 seconds with font size 18

        def move_overlays():
            # Move overlay1 by 10% of the window's width to the right and 10% of the height down
            overlay1.move_by_percentage(10, 10)

            # Move overlay2 by 50 pixels to the right and 30 pixels down
            overlay2.move_by_pixels(50, 30)

        # Schedule the move_overlays function to run after 2 seconds
        overlay1.root.after(2000, move_overlays)

        # Start the overlay GUI loop
        overlay1.start()
        overlay2.start()

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()


