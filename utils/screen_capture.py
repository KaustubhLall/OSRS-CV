import logging
import time
from contextlib import contextmanager
from io import BytesIO

import mss
import pygetwindow as gw
from PIL import Image

from utils.custom_logger import setup_logging

# Initialize logging with adjustable verbosity
logger_manager = setup_logging(log_to_file=True, log_to_stdout=True)
logger = logger_manager.get_logger(__name__)


@contextmanager
def Timer(name: str):
    """
    Context manager for timing code blocks.
    Logs the elapsed time upon exiting the context.
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        logger.debug(f"{name} completed in {elapsed_ms:.2f} ms.")


class ScreenCapture:
    def __init__(self, app_name: str = None, verbose: bool = False):
        """
        Initializes the ScreenCapture instance.

        :param app_name: Name of the application/window to capture.
        :param verbose: If True, sets logging level to DEBUG.
        """
        self.app_name = app_name
        self.window = None
        self.sct = mss.mss()
        self.total_capture_time = 0.0
        self.total_decode_time = 0.0
        self.total_frames = 0

        # Adjust logging level based on verbosity
        if verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        logger.debug("Initialized ScreenCapture with app_name: %s", app_name)
        if app_name:
            self.set_application(app_name)

    def __del__(self):
        self.sct.close()
        logger.debug("Closed mss instance.")

    def set_application(self, app_name: str = None, interactive: bool = False):
        """
        Sets the application/window to capture by name or interactively.

        :param app_name: Name of the application/window to capture.
        :param interactive: If True, allows user to select a window interactively.
        """
        if interactive:
            app_name = self._choose_window_interactively()
        if app_name:
            self.app_name = app_name
            self.window = self._find_window()
            logger.info("Application set to: '%s'", app_name)

    def _choose_window_interactively(self) -> str:
        """
        Allows the user to select a window interactively.

        :return: The title of the selected window.
        """
        windows = gw.getAllTitles()
        windows = [w for w in windows if w.strip()]  # Filter out empty titles
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
        except ValueError:
            logger.exception("Invalid input during window selection.")
            raise

    def _find_window(self):
        """
        Finds the window object based on the application name.

        :return: The window object.
        """
        windows = gw.getWindowsWithTitle(self.app_name)
        if windows:
            found_window = windows[0]
            logger.debug("Found window: '%s'", found_window.title)
            return found_window
        else:
            logger.error("No window found with title containing '%s'", self.app_name)
            raise ValueError(f"No window found with title containing '{self.app_name}'")

    def get_window_coordinates(self) -> dict:
        """
        Retrieves the coordinates of the selected window.

        :return: Dictionary containing window coordinates.
        """
        if not self.window:
            logger.error("Attempted to get coordinates without setting a window.")
            raise ValueError("No window set. Please set the application first.")

        coordinates = {
            "left": self.window.left,
            "top": self.window.top,
            "width": self.window.width,
            "height": self.window.height
        }
        logger.debug("Retrieved window coordinates: %s", coordinates)
        return coordinates

    def capture_to_disk(self, output_path: str = "screenshot.png"):
        """
        Captures the screenshot of the window and saves it to disk.

        :param output_path: Path to save the screenshot.
        """
        try:
            bbox = self.get_window_coordinates()
            monitor = {
                "top": bbox["top"],
                "left": bbox["left"],
                "width": bbox["width"],
                "height": bbox["height"]
            }

            with Timer("Screen capture"):
                screenshot = self.sct.grab(monitor)
                capture_start = time.perf_counter()

            with Timer("Image decoding"):
                img = Image.frombytes('RGB', (screenshot.width, screenshot.height), screenshot.rgb)
                decode_start = time.perf_counter()

            with Timer("Saving image to disk"):
                img.save(output_path)
                logger.info("Screenshot saved to '%s'.", output_path)
                save_end = time.perf_counter()

            # Calculate elapsed times
            capture_time = (decode_start - capture_start) * 1000  # ms
            decode_time = (save_end - decode_start) * 1000  # ms

            # Update total times
            self.total_capture_time += capture_time
            self.total_decode_time += decode_time
            self.total_frames += 1

        except Exception as e:
            logger.exception("Failed to capture and save screenshot: %s", e)
            raise

    def capture_to_memory(self) -> BytesIO:
        """
        Captures the screenshot of the window and saves it to memory.

        :return: BytesIO object containing the screenshot image.
        """
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

            with Timer("Screen capture"):
                screenshot = self.sct.grab(monitor)
                capture_start = time.perf_counter()

            with Timer("Image decoding"):
                img = Image.frombytes('RGB', (screenshot.width, screenshot.height), screenshot.rgb)
                decode_start = time.perf_counter()

            with Timer("Saving image to memory"):
                img_bytes = BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                img_size = img_bytes.getbuffer().nbytes
                logger.debug("Screenshot captured to memory: %d bytes.", img_size)
                save_end = time.perf_counter()

            # Calculate elapsed times
            capture_time = (decode_start - capture_start) * 1000  # ms
            decode_time = (save_end - decode_start) * 1000  # ms

            # Update total times
            self.total_capture_time += capture_time
            self.total_decode_time += decode_time
            self.total_frames += 1

            return img_bytes

        except Exception as e:
            logger.exception("Failed to capture screenshot to memory: %s", e)
            raise

    def get_total_times(self) -> dict:
        """
        Returns the total capture and decode times along with the number of frames processed.

        :return: Dictionary containing total capture time, total decode time, and total frames.
        """
        return {
            "total_capture_time_ms": self.total_capture_time,
            "total_decode_time_ms": self.total_decode_time,
            "total_frames": self.total_frames
        }


def measure_fps(screen_capture: ScreenCapture, num_frames: int = 100, display_image: bool = False) -> dict:
    """
    Measures the FPS by capturing a specified number of frames and calculating the average time per frame.

    :param screen_capture: An instance of ScreenCapture.
    :param num_frames: Number of frames to capture for measurement.
    :param display_image: Whether to display the last captured image.
    :return: Dictionary containing average capture time, average decode time, and estimated FPS.
    """
    try:
        logger.info("Starting FPS measurement for %d frames.", num_frames)
        capture_times = []
        decode_times = []
        last_image = None

        bbox = screen_capture.get_window_coordinates()
        monitor = {
            "top": bbox["top"],
            "left": bbox["left"],
            "width": bbox["width"],
            "height": bbox["height"]
        }

        for i in range(num_frames):
            # Capture time
            start_capture = time.perf_counter()
            screenshot = screen_capture.sct.grab(monitor)
            end_capture = time.perf_counter()
            capture_time = (end_capture - start_capture) * 1000  # ms
            capture_times.append(capture_time)

            # Decode time
            start_decode = time.perf_counter()
            img = Image.frombytes('RGB', (screenshot.width, screenshot.height), screenshot.rgb)
            end_decode = time.perf_counter()
            decode_time = (end_decode - start_decode) * 1000  # ms
            decode_times.append(decode_time)

            last_image = img  # Keep reference for optional display

        avg_capture_time = sum(capture_times) / num_frames
        avg_decode_time = sum(decode_times) / num_frames
        total_time_ms = avg_capture_time + avg_decode_time
        fps = 1000 / total_time_ms if total_time_ms > 0 else float('inf')

        logger.info("FPS Measurement Completed:")
        logger.info("Average capture time per frame: %.2f ms", avg_capture_time)
        logger.info("Average decode time per frame: %.2f ms", avg_decode_time)
        logger.info("Estimated FPS: %.2f", fps)

        if display_image and last_image:
            last_image.show()
            logger.debug("Image display triggered for FPS measurement.")

        return {
            "average_capture_time_ms": avg_capture_time,
            "average_decode_time_ms": avg_decode_time,
            "estimated_fps": fps
        }

    except Exception as e:
        logger.exception("An error occurred during FPS measurement: %s", e)
        raise


if __name__ == "__main__":
    try:
        total_start_time = time.perf_counter()

        # Initialize ScreenCapture with desired verbosity
        screen_capture = ScreenCapture(verbose=False)
        # Uncomment the following line to set application by name
        screen_capture.set_application(app_name="RuneLite")
        # Alternatively, enable interactive window selection
        # screen_capture.set_application(interactive=True)

        # Capture to disk
        screen_capture.capture_to_disk("selected_window_screenshot.png")

        # Capture to memory
        img_bytes = screen_capture.capture_to_memory()
        with Timer("Loading image from memory"):
            img = Image.open(img_bytes)

        with Timer("Converting image to RGB"):
            img = img.convert("RGB")

        # Optionally display the image (excluded from latency measurement)
        img.show()
        logger.debug("Image display triggered.")

        # Calculate total latency excluding FPS measurement
        capture_end_time = time.perf_counter()
        capture_latency_ms = (capture_end_time - total_start_time) * 1000
        logger.info("Total latency for capture and load operations: %.2f ms.", capture_latency_ms)

        # Measure FPS (optional and separate from total latency)
        perform_fps_measurement = True  # Set to False to skip FPS measurement
        if perform_fps_measurement:
            fps_results = measure_fps(screen_capture, num_frames=100, display_image=False)
            logger.info("FPS Measurement Results: %s", fps_results)

        # Retrieve total times from the class
        total_times = screen_capture.get_total_times()
        logger.info("Aggregated Capture Times: %s", total_times)

    except Exception as e:
        logger.exception("An error occurred during screen capture operations: %s", e)
