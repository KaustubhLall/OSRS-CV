import asyncio
import logging
import os

from PIL import ImageDraw, Image
from icecream import ic

from assets import load_assets
from full_scripts.high_alch import make_action
from utils.overlay import OverlayDrawer
from utils.sprite_loader import ImageLoader
from utils.vision_tools import locate_on_screen

# Set up logging
logging.basicConfig(filename='detection_report.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Define the directory where screenshots will be saved
output_dir = os.path.join(os.path.dirname(__file__), 'test_outputs')
os.makedirs(output_dir, exist_ok=True)

# Load assets and initialize necessary classes
assets = load_assets()
loader = ImageLoader()
drawer = OverlayDrawer()

# Debugging: Show loaded assets
ic(assets)
conf = 0.95


def concatenate_images(target_image, screen):
    """Concatenate target image and screen image vertically."""
    width = max(target_image.width, screen.width)
    height = target_image.height + screen.height
    concatenated_image = Image.new('RGB', (width, height))

    concatenated_image.paste(target_image, (0, 0))
    concatenated_image.paste(screen, (0, target_image.height))

    return concatenated_image


async def test_object_detection(item_name, screen_name, screen_path):
    """Test object detection by locating and drawing a bounding box on the target image."""
    # Load the target image based on the item name
    target_image = loader.load_image(assets['items'][item_name])

    # Load the current screen
    screen = loader.load_image(screen_path)

    # Perform action to locate and calculate the random click position
    click_position = await make_action(target_image, screen, offset_range=3, debug=False, confidence=conf)

    if click_position:
        # Draw a bounding box around the detected target
        location = locate_on_screen(target_image, screen, confidence=conf)
        if location:
            left, top, width, height = location.left, location.top, location.width, location.height
            right = left + width
            bottom = top + height
            bbox = (left, top, right, bottom)

            draw = ImageDraw.Draw(screen)
            draw.rectangle(bbox, outline="red", width=3)

            # Draw a green dot where the "click" would occur
            draw.ellipse(
                (click_position[0] - 2, click_position[1] - 2, click_position[0] + 2, click_position[1] + 2),
                fill="green",
                outline="green"
            )

            # Concatenate the target image and the screen
            output_image = concatenate_images(target_image, screen)

            # Save the modified image with a unique name
            output_filename = os.path.join(output_dir, f"test_output_{item_name}_{screen_name}.png")
            loader.save_image(output_image, output_filename)

            # Log success and save report
            message = f"Item '{item_name}' successfully detected on screen '{screen_name}'."
            logging.info(message)
            print(message)
        else:
            message = f"Target '{item_name}' not found on the screen '{screen_name}'."
            logging.warning(message)
            print(message)

            # Concatenate the target image and the screen even on failure
            output_image = concatenate_images(target_image, screen)
            output_filename = os.path.join(output_dir, f"failure_output_{item_name}_{screen_name}.png")
            loader.save_image(output_image, output_filename)
    else:
        message = f"Click position for item '{item_name}' could not be determined on screen '{screen_name}'."
        logging.error(message)
        print(message)

        # Concatenate the target image and the screen even on failure
        output_image = concatenate_images(target_image, screen)
        output_filename = os.path.join(output_dir, f"failure_output_{item_name}_{screen_name}.png")
        loader.save_image(output_image, output_filename)


async def main():
    item_names = [
        # 'rune-jav-head',
        'run-on',
        # 'spec-off',
        # 'prayer-off',
    ]
    tasks = []

    for item_name in item_names:
        for screen_name, screen_path in assets['screens'].items():
            task = asyncio.create_task(test_object_detection(item_name, screen_name, screen_path))
            tasks.append(task)

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
