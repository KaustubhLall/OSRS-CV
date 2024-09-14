import time
from io import BytesIO

import mss
import pygetwindow as gw
from PIL import Image

from utils.custom_logger import setup_logging

logger_manager = setup_logging(log_to_file=True, log_to_stdout=True)
logger = logger_manager.get_logger(__name__)


class ScreenCapture:
    def __init__(self, app_name=None):
        self.app_name = app_name
        self.window = None
        self.sct = mss.mss()
        logger.debug("Initialized ScreenCapture with app_name: %s", app_name)
        if app_name:
            self.set_application(app_name)

    def __del__(self):
        self.sct.close()
        logger.debug("Closed mss instance")

    def set_application(self, app_name=None, interactive=False):
        if interactive:
            app_name = self._choose_window_interactively()
        if app_name:
            self.app_name = app_name
            self.window = self._find_window()
            logger.info("Application set to: '%s'", app_name)

    def _choose_window_interactively(self):
        windows = gw.getAllTitles()
        if not windows:
            logger.error("No available windows found for selection.")
            raise ValueError("No available windows found.")

        logger.info("Available windows for selection:")
        for index, title in enumerate(windows):
            logger.info("[%d] %s", index, title)
        try:
            selected_index = int(input("Select the window index: "))
            if 0 <= selected_index < len(windows):
                selected_window = windows[selected_index]
                logger.info("User selected window: '%s'", selected_window)
                return selected_window
            else:
                logger.error("Selected index %d is out of range.", selected_index)
                raise ValueError("Invalid selection.")
        except ValueError as e:
            logger.exception("Invalid input during window selection")
            raise

    def _find_window(self):
        windows = gw.getWindowsWithTitle(self.app_name)
        if windows:
            found_window = windows[0]
            logger.debug("Found window: '%s'", found_window.title)
            return found_window
        else:
            logger.error("No window found with title containing '%s'", self.app_name)
            raise ValueError(f"No window found with title containing '{self.app_name}'")

    def get_window_coordinates(self):
        if not self.window:
            logger.error("Attempted to get coordinates without setting a window.")
            raise ValueError("No window set. Please set the application first.")

        coordinates = {
            "left": self.window.left,
            "top": self.window.top,
            "right": self.window.right,
            "bottom": self.window.bottom,
            "width": self.window.width,
            "height": self.window.height
        }
        logger.debug("Retrieved window coordinates: %s", coordinates)
        return coordinates

    def capture_to_disk(self, output_path="screenshot.png"):
        try:
            bbox = self.get_window_coordinates()
            monitor = {
                "top": bbox["top"],
                "left": bbox["left"],
                "width": bbox["width"],
                "height": bbox["height"]
            }

            start_time = time.time()
            screenshot = self.sct.grab(monitor)
            capture_time = (time.time() - start_time) * 1000  # Convert to ms
            logger.info("Screen captured in %.2f ms.", capture_time)

            start_time = time.time()
            img = Image.frombytes('RGB', (screenshot.width, screenshot.height), screenshot.rgb)
            decode_time = (time.time() - start_time) * 1000  # Convert to ms
            logger.info("Image decoded in %.2f ms.", decode_time)

            img.save(output_path)
            logger.info("Screenshot saved to '%s'", output_path)
        except Exception as e:
            logger.exception("Failed to capture and save screenshot: %s", e)
            raise

    def capture_to_memory(self):
        if not self.window:
            logger.error("Attempted to capture to memory without setting a window.")
            raise ValueError("No window set. Please set the application first.")

        try:
            bbox = self.get_window_coordinates()
            monitor = {
                "top": bbox["top"],
                "left": bbox["left"],
                "width": bbox["width"],
                "height": bbox["height"]
            }

            start_time = time.time()
            screenshot = self.sct.grab(monitor)
            capture_time = (time.time() - start_time) * 1000  # Convert to ms
            logger.info("Screen captured in %.2f ms.", capture_time)

            start_time = time.time()
            img = Image.frombytes('RGB', (screenshot.width, screenshot.height), screenshot.rgb)
            decode_time = (time.time() - start_time) * 1000  # Convert to ms
            logger.info("Image decoded in %.2f ms.", decode_time)

            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            img_size = img_bytes.getbuffer().nbytes
            logger.debug("Screenshot captured to memory: %d bytes", img_size)

            return img_bytes
        except Exception as e:
            logger.exception("Failed to capture screenshot to memory: %s", e)
            raise


if __name__ == "__main__":
    try:
        total_start_time = time.time()

        screen_capture = ScreenCapture()
        # Uncomment the following line to set application by name
        screen_capture.set_application(app_name="RuneLite")
        # screen_capture.set_application(interactive=True)
        screen_capture.capture_to_disk("selected_window_screenshot.png")

        img_bytes = screen_capture.capture_to_memory()
        start_time = time.time()
        img = Image.open(img_bytes)
        decode_time = (time.time() - start_time) * 1000
        logger.info("Image loaded from memory in %.2f ms.", decode_time)

        start_time = time.time()
        img = img.convert("RGB")
        convert_time = (time.time() - start_time) * 1000
        logger.info("Image converted to RGB in %.2f ms.", convert_time)

        img.show()
        logger.debug("Image display triggered.")

        total_end_time = time.time()
        total_latency_ms = (total_end_time - total_start_time) * 1000
        logger.info("Total latency for capture and load operations: %.2f ms.", total_latency_ms)

    except Exception as e:
        logger.exception("An error occurred during screen capture operations: %s", e)
