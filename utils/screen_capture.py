from io import BytesIO

import mss
import mss.tools
import pygetwindow as gw
from PIL import Image

from utils.custom_logger import setup_logging

logger = setup_logging(log_to_file=False)


class ScreenCapture:
    def __init__(self, app_name=None):
        self.app_name = app_name
        self.window = None
        self.sct = mss.mss()
        logger.debug("ScreenCapture instance created with app_name: %s", app_name)
        if app_name:
            self.set_application(app_name)

    def __del__(self):
        self.sct.close()
        logger.debug("mss instance closed")

    def set_application(self, app_name=None, interactive=False):
        if interactive:
            app_name = self._choose_window_interactively()
        if app_name:
            self.app_name = app_name
            self.window = self._find_window()
            logger.debug("Application set to: %s", app_name)

    def _choose_window_interactively(self):
        windows = gw.getAllTitles()
        if not windows:
            logger.error("No available windows found.")
            raise ValueError("No available windows found.")

        for index, title in enumerate(windows):
            print(f"[{index}] {title}")
        try:
            selected_index = int(input("Select the window index: "))
            if 0 <= selected_index < len(windows):
                return windows[selected_index]
            else:
                raise ValueError("Invalid selection.")
        except ValueError as e:
            logger.exception("Exception occurred during window selection")
            raise

    def _find_window(self):
        windows = gw.getWindowsWithTitle(self.app_name)
        if windows:
            return windows[0]
        else:
            logger.error("No window found with title containing '%s'", self.app_name)
            raise ValueError(f"No window found with title containing '{self.app_name}'")

    def get_window_coordinates(self):
        if not self.window:
            logger.error("No window set. Attempt to get coordinates failed.")
            raise ValueError("No window set. Please set the application first.")
        coordinates = {
            "left": self.window.left,
            "top": self.window.top,
            "right": self.window.right,
            "bottom": self.window.bottom,
            "width": self.window.width,
            "height": self.window.height
        }
        logger.debug("Window coordinates: %s", coordinates)
        return coordinates

    def capture_to_disk(self, output_path="screenshot.png"):
        bbox = self.get_window_coordinates()
        monitor = {
            "top": bbox["top"],
            "left": bbox["left"],
            "width": bbox["width"],
            "height": bbox["height"]
        }

        screenshot = self.sct.grab(monitor)
        img = Image.frombytes('RGB', (screenshot.width, screenshot.height), screenshot.rgb)
        img.save(output_path)
        logger.info("Screenshot saved to %s", output_path)

    def capture_to_memory(self):
        if not self.window:
            logger.error("No window set. Attempt to capture screen failed.")
            raise ValueError("No window set. Please set the application first.")

        bbox = self.get_window_coordinates()
        monitor = {
            "top": bbox["top"],
            "left": bbox["left"],
            "width": bbox["width"],
            "height": bbox["height"]
        }

        screenshot = self.sct.grab(monitor)
        img = Image.frombytes('RGB', (screenshot.width, screenshot.height), screenshot.rgb)
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        logger.debug(f"Screenshot captured to memory: {img_bytes.tell()} bytes")

        return img_bytes


if __name__ == "__main__":
    # Example usage
    try:
        screen_capture = ScreenCapture()
        # screen_capture.set_application(app_name="RuneLite")
        screen_capture.set_application(interactive=True)
        screen_capture.capture_to_disk("selected_window_screenshot.png")

        img_bytes = screen_capture.capture_to_memory()  # Capture image to memory
        img = Image.open(img_bytes)  # Load the image from the BytesIO stream

        # Adjust color channels for display only
        img = img.convert("RGB")  # This ensures the display uses the correct RGB format
        img.show()  # Display the image

    except Exception as e:
        logger.exception("An error occurred: %s", e)