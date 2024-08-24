import time
import pyautogui
from PIL import Image
from pyscreeze import locate, ImageNotFoundException, USE_IMAGE_NOT_FOUND_EXCEPTION
from utils.custom_logger import setup_logging

logger = setup_logging(log_to_file=True)


def locate_on_screen(image, screen, minSearchTime=0, debug=False, iteration=None, confidence=0.5):
    """Locate an image on the screen with enhanced logging for debugging purposes."""
    start = time.time()
    elapsed_time = 0
    logger.info(f"Starting locate_on_screen with minSearchTime={minSearchTime}, debug={debug}, iteration={iteration}")
    logger.debug(f"Image size: {image.size}, Screen size: {screen.size}")

    try:
        while True:
            try:
                retVal = locate(image, screen, confidence=confidence)
                elapsed_time = time.time() - start
                logger.debug(f"Time elapsed: {elapsed_time:.2f} seconds")

                if retVal:
                    logger.info(f"Found image at {retVal} after {elapsed_time:.2f} seconds")
                    if debug:
                        save_debug_info(image, screen, iteration)
                    return retVal
                elif elapsed_time > minSearchTime:
                    logger.info(f"No match found within the minimum search time of {minSearchTime} seconds.")
                    if debug:
                        save_debug_info(image, screen, iteration, "No match found")
                    return None
            except ImageNotFoundException as e:
                logger.warning(f"ImageNotFoundException: {e}")
                break
                if elapsed_time > minSearchTime:
                    if USE_IMAGE_NOT_FOUND_EXCEPTION:
                        logger.error("Raising ImageNotFoundException due to configuration.")
                        if debug:
                            save_debug_info(image, screen, iteration, str(e))
                        raise
                    else:
                        if debug:
                            save_debug_info(image, screen, iteration, str(e))
                        return None

    except Exception as e:
        elapsed_time = time.time() - start
        logger.error(f"An exception occurred after {elapsed_time:.2f} seconds: {e}")
        if debug:
            save_debug_info(image, screen, iteration, str(e))
        raise


def save_debug_info(image, screen, iteration=None, error_message=None):
    """Save debug information including the source image, the screen, and an error message if any."""
    iteration_str = f"_{iteration}" if iteration is not None else ""
    image_path = f"screenshots/debug_source_image{iteration_str}.png"
    screen_path = f"screenshots/debug_screen{iteration_str}.png"

    # image.save(image_path)
    # screen.save(screen_path)

    logger.info(f"Saved source image to {image_path}")
    logger.info(f"Saved screen capture to {screen_path}")

    if error_message:
        error_file = f"debug_error_message{iteration_str}.txt"
        with open(error_file, 'w') as f:
            f.write(error_message)
        logger.info(f"Saved error message to {error_file}")
