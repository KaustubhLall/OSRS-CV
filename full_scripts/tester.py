import random
from icecream import ic
from assets import load_assets
from full_scripts.high_alch import make_action
from utils.overlay import OverlayDrawer
from utils.sprite_loader import ImageLoader
from utils.vision_tools import locate_on_screen
from PIL import ImageDraw

# Load assets and initialize necessary classes
assets = load_assets()
loader = ImageLoader()
drawer = OverlayDrawer()

# Load target images
target = loader.load_image(assets['items']['dwarven-rock-cake'])
target = loader.load_image(assets['items']['pray-hp'])
target_jav = loader.load_image(assets['items']['rune-jav-head'])
target_ha = loader.load_image(assets['items']['high-alch'])

# Debugging: Show loaded assets
ic(assets)
conf = 0.3
target = target_jav

# Iterate over all screens in the assets
for screen_name, screen_path in assets['screens'].items():
    # Load the current screen
    screen = loader.load_image(screen_path)

    # Perform action to locate and calculate the random click position
    click_position = make_action(target, screen, offset_range=3, debug=False, confidence=conf)

    # Check if a click position was calculated
    if click_position:
        # Draw a bounding box around the detected target
        location = locate_on_screen(target, screen, confidence=conf)
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

            # Save the modified image with a unique name
            output_filename = f"test_output_{screen_name}.png"
            loader.save_image(screen, output_filename)

            # Display the image (this will depend on your environment, e.g., using PIL's show method)
            screen.show()

    else:
        print(f"Target not found on the screen: {screen_name}.")
