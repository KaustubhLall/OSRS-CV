from io import BytesIO

from PIL import Image

from utils.custom_logger import setup_logging

logger = setup_logging(log_to_file=False)


class ImageLoader:
    def __init__(self, target_size=None, color_mode='RGB'):
        """
        Initializes the image loader with optional size and color mode.

        :param target_size: tuple (width, height) to resize images, or None to keep original size.
        :param color_mode: 'L' for grayscale, 'RGB' for RGB color mode.
        """
        self.target_size = target_size
        self.color_mode = color_mode

    def _preprocess_image(self, img):
        """
        Resize and preprocess the image according to the specified size and color mode.

        :param img: PIL.Image, image to be processed.
        :return: PIL.Image, the preprocessed image.
        """
        if self.color_mode and img.mode != self.color_mode:
            img = img.convert(self.color_mode)
        if self.target_size:
            img = img.resize(self.target_size, Image.ANTIALIAS)
        return img

    def load_image(self, filepath):
        """
        Load an image from the given filepath and preprocess it according to the specified size and color mode.

        :param filepath: str, path to the image file.
        :return: PIL.Image, the preprocessed image.
        """
        img = Image.open(filepath)
        return self._preprocess_image(img)

    def load_image_from_memory(self, image_data):
        """
        Load an image from an in-memory variable (such as bytes).

        :param image_data: bytes, image data.
        :return: PIL.Image, the preprocessed image.
        """
        img = Image.open(BytesIO(image_data))
        return self._preprocess_image(img)

    def save_image(self, img, save_path):
        """
        Save an image to the specified path.

        :param img: PIL.Image, image to be saved.
        :param save_path: str, path where the image will be saved.
        """
        img.save(save_path)

    def view_image(self, img, window_name='Image'):
        """
        Display an image using the default image viewer.

        :param img: PIL.Image, image to be displayed.
        :param window_name: str, name of the window in which the image will be displayed.
        """
        img.show(title=window_name)


def main():
    loader = ImageLoader(target_size=(1920, 1080), color_mode='RGB')
    path_in = '/assets/screens/selected_window_screenshot.png'
    path_out = 'C:/Users/kaust/PycharmProjects/RSBot/utils/processed_selected_window_screenshot.png'

    # Load an image from file
    image = loader.load_image(path_in)
    loader.save_image(image, path_out)
    loader.view_image(image, 'Processed Image')

    # Load an image from memory (simulated here as loading from file first)
    with open(path_in, 'rb') as file:
        image_data = file.read()
    image_from_memory = loader.load_image_from_memory(image_data)
    loader.view_image(image_from_memory, 'Image from Memory')


if __name__ == '__main__':
    main()
