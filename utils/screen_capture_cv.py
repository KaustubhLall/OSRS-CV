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
        self.total_capture_time = 0.0
        self.total_decode_time = 0.0
        self.total_frames = 0
        # Separate attributes for FPS measurement
        self.fps_capture_time = 0.0
        self.fps_decode_time = 0.0
        self.fps_frames = 0
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

            start_capture = time.perf_counter()
            screenshot = self.sct.grab(monitor)
            capture_time = (time.perf_counter() - start_capture) * 1000  # ms
            logger.info("Screen captured in %.2f ms.", capture_time)
            self.total_capture_time += capture_time
            self.total_frames += 1

            start_decode = time.perf_counter()
            img = Image.frombytes('RGB', (screenshot.width, screenshot.height), screenshot.rgb)
            decode_time = (time.perf_counter() - start_decode) * 1000  # ms
            logger.info("Image decoded in %.2f ms.", decode_time)
            self.total_decode_time += decode_time

            start_save = time.perf_counter()
            img.save(output_path)
            save_time = (time.perf_counter() - start_save) * 1000  # ms
            logger.info("Screenshot saved to '%s' in %.2f ms.", output_path, save_time)

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

            start_capture = time.perf_counter()
            screenshot = self.sct.grab(monitor)
            capture_time = (time.perf_counter() - start_capture) * 1000  # ms
            logger.info("Screen captured in %.2f ms.", capture_time)
            self.total_capture_time += capture_time
            self.total_frames += 1

            start_decode = time.perf_counter()
            img = Image.frombytes('RGB', (screenshot.width, screenshot.height), screenshot.rgb)
            decode_time = (time.perf_counter() - start_decode) * 1000  # ms
            logger.info("Image decoded in %.2f ms.", decode_time)
            self.total_decode_time += decode_time

            start_save = time.perf_counter()
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            img_size = img_bytes.getbuffer().nbytes
            save_time = (time.perf_counter() - start_save) * 1000  # ms
            logger.debug("Screenshot captured to memory: %d bytes in %.2f ms", img_size, save_time)

            return img_bytes

        except Exception as e:
            logger.exception("Failed to capture screenshot to memory: %s", e)
            raise

    def measure_fps(self, num_frames=100, display_image=False):
        """
        Measures the FPS by capturing a specified number of frames and calculating the average time per frame.

        :param num_frames: Number of frames to capture for measurement.
        :param display_image: Whether to display the last captured image.
        """
        try:
            logger.info("Starting FPS measurement for %d frames.", num_frames)
            capture_times = []
            decode_times = []

            # Retrieve window coordinates and monitor settings once
            bbox = self.get_window_coordinates()
            monitor = {
                "top": bbox["top"],
                "left": bbox["left"],
                "width": bbox["width"],
                "height": bbox["height"]
            }

            for i in range(num_frames):
                # Avoid logging every frame to minimize overhead
                # logger.debug("FPS Capture Frame %d/%d", i+1, num_frames)

                # Capture time
                start_capture = time.perf_counter()
                screenshot = self.sct.grab(monitor)
                end_capture = time.perf_counter()
                capture_time = (end_capture - start_capture) * 1000  # ms
                capture_times.append(capture_time)
                self.fps_capture_time += capture_time

                # Decode time
                start_decode = time.perf_counter()
                img = Image.frombytes('RGB', (screenshot.width, screenshot.height), screenshot.rgb)
                end_decode = time.perf_counter()
                decode_time = (end_decode - start_decode) * 1000  # ms
                decode_times.append(decode_time)
                self.fps_decode_time += decode_time

                self.fps_frames += 1

                # Optionally display the last captured image
                if display_image and i == num_frames - 1:
                    img.show()
                    logger.debug("Image display triggered for FPS measurement.")

            avg_capture_time = sum(capture_times) / num_frames
            avg_decode_time = sum(decode_times) / num_frames
            total_time_ms = avg_capture_time + avg_decode_time
            fps = 1000 / total_time_ms if total_time_ms > 0 else float('inf')

            logger.info("FPS Measurement Completed:")
            logger.info("Average capture time per frame: %.2f ms", avg_capture_time)
            logger.info("Average decode time per frame: %.2f ms", avg_decode_time)
            logger.info("Estimated FPS: %.2f", fps)

            logger.info("FPS Measurement Results: %s", {
                "average_capture_time_ms": avg_capture_time,
                "average_decode_time_ms": avg_decode_time,
                "estimated_fps": fps
            })

            return {
                "average_capture_time_ms": avg_capture_time,
                "average_decode_time_ms": avg_decode_time,
                "estimated_fps": fps
            }

        except Exception as e:
            logger.exception("An error occurred during FPS measurement: %s", e)
            raise

    def get_total_times(self):
        """
        Returns the total capture and decode times along with the number of frames processed.

        :return: Dictionary containing total capture time, total decode time, and total frames.
        """
        return {
            "total_capture_time_ms": self.total_capture_time,
            "total_decode_time_ms": self.total_decode_time,
            "total_frames": self.total_frames,
            "fps_capture_time_ms": self.fps_capture_time,
            "fps_decode_time_ms": self.fps_decode_time,
            "fps_frames": self.fps_frames
        }


if __name__ == "__main__":
    try:
        total_start_time = time.perf_counter()

        screen_capture = ScreenCapture()
        # Uncomment the following line to set application by name
        screen_capture.set_application(app_name="RuneLite")
        # screen_capture.set_application(interactive=True)

        # Capture to disk
        screen_capture.capture_to_disk("selected_window_screenshot.png")

        # Capture to memory
        img_bytes = screen_capture.capture_to_memory()
        start_load = time.perf_counter()
        img = Image.open(img_bytes)
        end_load = time.perf_counter()
        decode_time = (end_load - start_load) * 1000  # ms
        logger.info("Image loaded from memory in %.2f ms.", decode_time)

        start_convert = time.perf_counter()
        img = img.convert("RGB")
        end_convert = time.perf_counter()
        convert_time = (end_convert - start_convert) * 1000  # ms
        logger.info("Image converted to RGB in %.2f ms.", convert_time)

        # Optionally display the image (excluded from latency measurement)
        img.show()
        logger.debug("Image display triggered.")

        # Measure FPS (optional)
        perform_fps_measurement = True  # Set to False to skip FPS measurement
        if perform_fps_measurement:
            fps_results = screen_capture.measure_fps(num_frames=100, display_image=False)
            logger.info("FPS Measurement Results: %s", fps_results)

        # Calculate total latency
        total_end_time = time.perf_counter()
        total_latency_ms = (total_end_time - total_start_time) * 1000
        logger.info("Total latency for capture and load operations: %.2f ms.", total_latency_ms)

        # Retrieve total times from the class
        total_times = screen_capture.get_total_times()
        logger.info("Aggregated Capture Times: %s", total_times)

    except Exception as e:
        logger.exception("An error occurred during screen capture operations: %s", e)
