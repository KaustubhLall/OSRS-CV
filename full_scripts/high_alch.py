import asyncio
import random
from datetime import datetime, timedelta

import pyautogui
from PIL import ImageDraw
from pyHM import mouse

from utils.assets_path_loader import load_assets
from utils.custom_logger import setup_logging
from utils.image_loader import ImageLoader
from utils.overlay import OverlayDrawer
from utils.screen_capture import ScreenCapture
from utils.vision_tools import locate_on_screen

# Set up logging
logger = setup_logging(log_to_file=True)

# Load assets and initialize tools
assets = load_assets()
loader = ImageLoader()
screen_capture = ScreenCapture(app_name="RuneLite")
overlay = OverlayDrawer(title="Alching Statistics")  # Initialize the overlay before the loop

# Constants for calculations
ALCH_EXP = 65  # Experience per alch
RUNE_COST = 108
ITEM_COST = 538
OUTPUT_VALUE = 810  # Coin value per alch
INPUT_COST = RUNE_COST + ITEM_COST


def get_random_offset_position(x, y, offset_range=3):
    """Generate a random offset position around a given x, y coordinate."""
    offset_x = random.randint(-offset_range, offset_range)
    offset_y = random.randint(-offset_range, offset_range)
    return x + offset_x, y + offset_y


def save_debug_image(image, location, file_name, box=None):
    """Save a debug image with optional location marking and bounding box."""
    draw = ImageDraw.Draw(image)
    dot_size = 5
    draw.ellipse(
        [(location[0] - dot_size, location[1] - dot_size), (location[0] + dot_size, location[1] + dot_size)],
        fill="red"
    )
    if box:
        draw.rectangle(box, outline="green", width=2)
    image.save(f"screenshots/{file_name}")


async def make_action(target_image, screen, offset_range=3, debug=False, iteration=0, confidence=0.5):
    """Locate the target image on screen and return the random click location."""
    location = locate_on_screen(target_image, screen, debug=debug, iteration=iteration, confidence=confidence)
    if location:
        center_x = location.left + location.width // 2
        center_y = location.top + location.height // 2
        random_location = get_random_offset_position(center_x, center_y, offset_range)
        bounding_box = (location.left, location.top, location.left + location.width, location.top + location.height)
        if debug:
            save_debug_image(screen, random_location, f"click_{iteration}.png", box=bounding_box)
        return random_location
    return None


def load_target_images():
    """Load target images from assets."""
    return {name: loader.load_image(path) for name, path in assets['items'].items()}


async def retry_until_found(target_image, screen_capture, loader, max_retries=10, confidence=0.5, debug=False,
                            iteration=0):
    """Retry finding and clicking the target image until found or max retries."""
    retries = 0
    while retries < max_retries:
        screen_capture.capture_to_disk('screenshots/temp.png')
        screen = loader.load_image('screenshots/temp.png')
        location = await make_action(target_image, screen, confidence=confidence, debug=debug, iteration=iteration)
        if location:
            return location
        retries += 1
        logger.debug(f"Retrying... ({retries}/{max_retries})")
        await asyncio.sleep(random.uniform(0.25, 1.0))

    logger.warning("Failed to find the target image after maximum retries.")
    raise ValueError("Failed to locate image on screen after maximum retries.")


async def reset_procedure():
    """Perform a reset by pressing 'esc' three times and then pressing '3'."""
    logger.info("Performing reset procedure.")
    for _ in range(3):
        pyautogui.press('esc')
        await asyncio.sleep(0.2)
    pyautogui.press('3')
    logger.info("Reset complete, resuming script.")


async def cast_spell(spell, screen_capture, loader, confidence, debug, iteration):
    """Attempt to cast the spell by locating it on the screen."""
    spell_location = await retry_until_found(spell, screen_capture, loader, max_retries=5, confidence=confidence,
                                             debug=debug, iteration=iteration)
    if spell_location:
        mouse.click(*spell_location)
        logger.info(f"Spell cast at {spell_location}")
        await asyncio.sleep(random.uniform(0.25, 0.5))
        return True
    logger.warning("Spell not found on screen.")
    return False


async def alch_item(item, screen_capture, loader, confidence, debug, iteration):
    """Attempt to alch the item by locating it on the screen."""
    item_location = await retry_until_found(item, screen_capture, loader, max_retries=10, confidence=confidence,
                                            debug=debug, iteration=iteration)
    if item_location:
        mouse.click(*item_location)
        logger.info(f"Item alched at {item_location}")
        return True
    logger.warning("Item not found on screen.")
    return False


def format_number(number):
    """Formats the number with 'k' for thousands and 'm' for millions."""
    if number >= 1_000_000:
        return f"{number / 1_000_000:.2f}m"
    elif number >= 1_000:
        return f"{number / 1_000:.2f}k"
    else:
        return f"{number:.0f}"


def format_time(seconds_left):
    """Formats seconds into a human-readable time format (HH:MM:SS)."""
    hours, remainder = divmod(int(seconds_left), 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    elif minutes > 0:
        return f"{minutes:02}:{seconds:02}"
    else:
        return f"{seconds:02}"


def update_statistics_overlay(overlay, start_time, iterations, num_iterations, total_exp, total_profit, total_value):
    """Updates the overlay with the current statistics."""
    time_elapsed = datetime.now() - start_time

    if time_elapsed.total_seconds() > 0:
        alchs_per_second = iterations / time_elapsed.total_seconds()
    else:
        alchs_per_second = 0

    alchs_per_minute = alchs_per_second * 60
    alchs_per_hour = alchs_per_second * 3600

    if time_elapsed.total_seconds() > 0:
        exp_per_hour = (total_exp / time_elapsed.total_seconds()) * 3600
        profit_per_hour = (total_profit / time_elapsed.total_seconds()) * 3600
    else:
        exp_per_hour = 0
        profit_per_hour = 0

    alchs_remaining = num_iterations - iterations
    if alchs_per_second > 0:
        eta_seconds = alchs_remaining / alchs_per_second
        time_left = timedelta(seconds=int(eta_seconds))
    else:
        time_left = timedelta(seconds=0)

    overlay_text = (
        f"<color=lightgreen>Track</color> <color=lightgreen>Live Rate</color> <color=lightgreen>Total</color> <color=lightgreen>Goal ({str(time_left)})</color>\n"
        f"<color=lightgreen>Alchs:</color> <color=lightblue>{alchs_per_second:>6.2f}/s</color> <color=lightblue>{alchs_per_minute:>7.2f}/min</color> <color=lightblue>{alchs_per_hour:>7.2f}/hr</color>\n"
        f"<color=lightgreen>XP Rate:</color> <color=yellow>{format_number(exp_per_hour):>8} xp/hr</color> <color=yellow>{format_number(total_exp):>8} xp</color> <color=orange>{format_number(ALCH_EXP * num_iterations):>8} xp</color>\n"
        f"<color=lightgreen>Profit:</color> <color=lightblue>{OUTPUT_VALUE - INPUT_COST:>6} gp/alch</color> <color=yellow>{format_number(total_profit):>8} gp</color> <color=lightblue>{format_number(profit_per_hour):>8} gp/hr</color>\n"
        f"<color=lightgreen>Total Alchs:</color> <color=lightblue>{iterations:>4}/{num_iterations:<4}</color> <color=lightyellow>{format_number(total_value):>8} gp</color> <color=orange>{alchs_remaining:<4} alchs</color>\n"
    )

    overlay.display_text(overlay_text, font_size=12)


async def perform_high_alchemy(spell_name, item_name, num_iterations, max_iterations=100, max_time_minutes=10,
                               spell_confidence=0.6, item_confidence=0.3):
    """Main loop to perform high alchemy for a specified number of iterations or time."""
    items = load_target_images()
    spell = items.get(spell_name)
    target_item = items.get(item_name)

    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=max_time_minutes)
    iterations = 0
    total_exp = 0
    total_value = 0
    total_profit = 0

    while iterations < max_iterations and datetime.now() < end_time:
        if iterations >= num_iterations:
            logger.info("Reached the specified number of iterations.")
            break

        try:
            if await cast_spell(spell, screen_capture, loader, spell_confidence, debug=True, iteration=iterations):
                if await alch_item(target_item, screen_capture, loader, item_confidence, debug=True,
                                   iteration=iterations):
                    iterations += 1
                    total_exp += ALCH_EXP
                    total_profit += OUTPUT_VALUE - INPUT_COST
                    total_value += OUTPUT_VALUE

                    update_statistics_overlay(overlay, start_time, iterations, num_iterations, total_exp, total_profit,
                                              total_value)

                    logger.debug(f"Iteration {iterations} complete.")
        except ValueError as e:
            logger.error(f"Error encountered during iteration {iterations}: {str(e)}")
            await reset_procedure()

        await asyncio.sleep(random.uniform(0.05, 0.25))

    logger.info(
        f"Script stopped after {iterations} iterations due to reaching the specified number of iterations or timeout.")


async def main():
    await perform_high_alchemy('high-alch', 'rune-jav-head', num_iterations=5000, max_iterations=5000,
                               max_time_minutes=11 * 30, spell_confidence=0.53, item_confidence=0.35)


if __name__ == "__main__":
    asyncio.run(main())
