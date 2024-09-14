from io import BytesIO
from pathlib import Path
from typing import Tuple, Dict

from PIL import Image, ImageOps, ImageGrab, UnidentifiedImageError

from utils.assets_path_loader import load_assets
from utils.custom_logger import setup_logging

logger_manager = setup_logging(log_to_file=True, log_to_stdout=True)
logger = logger_manager.get_logger(__name__)


class ImageLoader:
    """
    A utility class for loading, preprocessing, saving, and viewing images,
    with options for resizing and color mode conversion suitable for ML models.

    Parameters:
    - target_size (Tuple[int, int]): Desired image size as (width, height). Default is (1280, 720).
    - color_mode (str): Color mode to convert images to. Options are 'RGB' or 'L' (grayscale). Default is 'RGB'.
    """

    def __init__(self, target_size: Tuple[int, int] = (1280, 720), color_mode: str = 'RGB'):
        self.target_size = target_size
        self.color_mode = color_mode

    def _preprocess_image(self, img: Image.Image) -> Tuple[Image.Image, Tuple[float, float]]:
        """
        Preprocess the image by handling orientation, converting color mode, and resizing while maintaining aspect ratio.
        Returns the preprocessed image and scaling factors (scale_x, scale_y).
        """
        try:
            # Get original size
            original_width, original_height = img.size

            # Ensure consistent orientation
            img = ImageOps.exif_transpose(img)

            # Convert color mode if necessary
            if self.color_mode and img.mode != self.color_mode:
                img = img.convert(self.color_mode)

            # Resize while maintaining aspect ratio and pad to target size
            if self.target_size:
                target_width, target_height = self.target_size

                # Compute scaling factor to maintain aspect ratio
                scale = min(target_width / original_width, target_height / original_height)
                new_width = int(original_width * scale)
                new_height = int(original_height * scale)
                img = img.resize((new_width, new_height), Image.LANCZOS)

                # Create new image with target size and paste the resized image onto it, centering the image
                new_img = Image.new(self.color_mode, self.target_size, (0, 0, 0))
                left = (target_width - new_width) // 2
                top = (target_height - new_height) // 2
                new_img.paste(img, (left, top))

                # Update img
                img = new_img

                # Calculate scaling factors
                scale_x = scale
                scale_y = scale
            else:
                # No resizing was done
                scale_x = 1.0
                scale_y = 1.0

            return img, (scale_x, scale_y)
        except Exception as e:
            logger.error(f"Error in preprocessing image: {e}")
            raise

    def load_image(self, filepath: str) -> Tuple[Image.Image, Tuple[float, float]]:
        """
        Load and preprocess an image from a file path.
        Returns the image and scaling factors.
        """
        try:
            with Image.open(filepath) as img:
                return self._preprocess_image(img)
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            raise
        except UnidentifiedImageError:
            logger.error(f"Cannot identify image file: {filepath}")
            raise

    def load_image_from_memory(self, image_data: bytes) -> Tuple[Image.Image, Tuple[float, float]]:
        """
        Load and preprocess an image from bytes data.
        Returns the image and scaling factors.
        """
        try:
            with Image.open(BytesIO(image_data)) as img:
                return self._preprocess_image(img)
        except UnidentifiedImageError:
            logger.error("Cannot identify image from provided bytes data.")
            raise

    def save_image(self, img: Image.Image, save_path: str) -> None:
        """Save an image to the specified path."""
        try:
            img.save(save_path)
            logger.debug(f"Image saved to {save_path}")
        except Exception as e:
            logger.error(f"Failed to save image to {save_path}: {e}")
            raise

    def view_image(self, img: Image.Image, window_name: str = 'Image') -> None:
        """Display an image using the default image viewer."""
        try:
            img.show(title=window_name)
        except Exception as e:
            logger.error(f"Failed to display image: {e}")


def process_images(loader: ImageLoader, assets: Dict[str, Dict[str, str]]) -> None:
    """Process images in the 'screens' category."""
    screens_assets = assets.get('screens', {})

    if not screens_assets:
        logger.warning("No images found in assets under 'screens' category.")
        return

    for image_name, path_in in screens_assets.items():
        processed_dir = Path(path_in).parent / 'processed'
        processed_dir.mkdir(parents=True, exist_ok=True)

        path_out = str(processed_dir / f'{image_name}_preprocessed.png')

        try:
            image, (scale_x, scale_y) = loader.load_image(path_in)
            loader.save_image(image, path_out)
            logger.debug(f'Image {image_name} processed with scaling factors: scale_x={scale_x}, scale_y={scale_y}')
        except Exception as e:
            logger.error(f"Failed to process image {image_name}: {e}")


def capture_and_process_screen(loader: ImageLoader) -> None:
    """Capture the screen, process the image, and display it."""
    try:
        img = ImageGrab.grab()
        with BytesIO() as output:
            img.save(output, format='PNG')
            image_data = output.getvalue()
        image_from_memory, (scale_x, scale_y) = loader.load_image_from_memory(image_data)
        loader.view_image(image_from_memory, 'Image from Memory')
        logger.debug(f'Image from memory processed with scaling factors: scale_x={scale_x}, scale_y={scale_y}')
    except Exception as e:
        logger.error(f"Failed to capture and process screen image: {e}")


def main():
    # Initialize the ImageLoader with desired target size and color mode
    loader = ImageLoader(target_size=(1280, 720), color_mode='RGB')

    # Load assets using utils.load_assets
    try:
        assets = load_assets()  # This will load all assets under the ASSETS_ROOT
    except Exception as e:
        logger.error(f"Failed to load assets: {e}")
        return

    # Process images in 'screens' category
    process_images(loader, assets)

    # Capture and process screen image
    capture_and_process_screen(loader)


if __name__ == '__main__':
    main()
