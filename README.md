# Project Title: Old School Runescape AI Automation Tool

## Overview

This project is a comprehensive automation tool designed to use computer vision (CV) and AI to play Old School
Runescape (OSRS). Initially configured to automate the high alchemy task, the tool is designed to be extensible,
allowing for a wide range of in-game activities to be automated through AI-driven strategies. The project will continue
to evolve, adding more scripts and functionalities to cover various aspects of gameplay.

## Table of Contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Setup Instructions](#setup-instructions)
5. [Usage](#usage)
    - [Main Script (`high_alch.py`)](#main-script-high_alchpy)
    - [Screen Capture (`screen_capture.py`)](#screen-capture-screen_capturepy)
    - [Image Loader (`sprite_loader.py`)](#image-loader-sprite_loaderpy)
    - [Vision Tools (`vision_tools.py`)](#vision-tools-vision_toolspy)
    - [Overlay (`overlay.py`)](#overlay-overlaypy)
    - [Object Detector (`object_detector.py`)](#object-detector-object_detectorpy)
    - [Custom Logger (`custom_logger.py`)](#custom-logger-custom_loggerpy)
6. [Future Activities and Use Cases](#future-activities-and-use-cases)
7. [Contributing](#contributing)
8. [License](#license)

## Features

- **Automated Gameplay**: AI-driven automation for various in-game activities in OSRS, starting with high alchemy.
- **Computer Vision**: Leverages advanced image recognition to interact with the game environment.
- **Real-time Overlays**: Display live statistics and in-game data on the screen using customizable overlays.
- **Custom Logging**: Detailed, color-coded logging for easy debugging and monitoring.
- **Modular Design**: The codebase is designed to be easily extensible for new activities and use cases.
- **Scalable Architecture**: Prepared for the inclusion of multiple scripts to handle various in-game activities.

## Requirements

Before you begin, ensure you have met the following requirements:

- Python 3.8 or higher
- pip (Python package installer)

## Installation

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/KaustubhLall/OSRS-CV.git
   cd OSRS-CV
   ```

2. **Install the Required Python Packages**:

   You can install the required packages using the `requirements.txt` file:

   ```bash
   pip install -r requirements.txt
   ```

   This will install all the dependencies necessary for the project to run smoothly.

## Setup Instructions

1. **Assets**:

    - Ensure that the required assets (e.g., images for spells and items) are placed in the appropriate directory. The
      default location for assets is `/assets/`.
    - You may need to create this directory if it does not exist:

   ```bash
   mkdir -p assets/screenshots
   ```

2. **Logging Setup**:

    - By default, logs will be saved to `logs/application.log`. Ensure that the `logs/` directory exists:

   ```bash
   mkdir -p logs
   ```

3. **Run the Main Script**:

    - Once the setup is complete, you can run the main script to start the automation:

   ```bash
   python high_alch.py
   ```

   This will begin the high alchemy process, automatically casting spells and tracking progress.

## Usage

### Main Script (`high_alch.py`)

The `high_alch.py` script is the initial use case in the project. It orchestrates the automation process, utilizing
other modules for screen capture, image recognition, and overlay management.

- **Run the Script**:

  ```bash
  python high_alch.py
  ```

- **Customizable Parameters**:

    - `spell_name`: The name of the spell to cast (default: `high-alch`).
    - `item_name`: The name of the item to alch (default: `rune-jav-head`).
    - `num_iterations`: The number of alchs to perform.
    - `max_iterations`: The maximum number of iterations before stopping.
    - `max_time_minutes`: The maximum time to run the script.
    - `spell_confidence`: The confidence level for detecting the spell on screen.
    - `item_confidence`: The confidence level for detecting the item on screen.

### Screen Capture (`screen_capture.py`)

This module is responsible for capturing screenshots of the targeted application window.

- **Key Functions**:
    - `set_application(app_name)`: Set the application window to capture.
    - `capture_to_disk(output_path)`: Capture the screenshot and save it to the specified path.
    - `capture_to_memory()`: Capture the screenshot and keep it in memory.

- **Usage**:

  ```bash
  python screen_capture.py
  ```

  This script can be used standalone to capture screenshots of the selected window. You can modify the script to change
  the target application and output paths.

### Image Loader (`sprite_loader.py`)

The `sprite_loader.py` module handles loading, preprocessing, and saving images used for automation.

- **Key Functions**:
    - `load_image(filepath)`: Load an image from the specified path.
    - `load_image_from_memory(image_data)`: Load an image from a byte stream.
    - `save_image(img, save_path)`: Save the image to disk.

- **Usage**:

  ```bash
  python sprite_loader.py
  ```

  This script demonstrates loading an image, processing it, and saving the processed image. Modify the paths to load
  your specific assets.

### Vision Tools (`vision_tools.py`)

This module provides image recognition tools to locate elements on the screen.

- **Key Functions**:
    - `locate_on_screen(image, screen, confidence)`: Locate an image on the screen with the specified confidence level.

- **Usage**:

  ```bash
  python vision_tools.py
  ```

  Use this script to test image recognition and debug image matching on the screen.

### Overlay (`overlay.py`)

The `overlay.py` module creates and manages overlays that display real-time information on the screen.

- **Key Functions**:
    - `display_text(text, timeout, font_size)`: Display text on the overlay with optional timeout and font size.

- **Usage**:

  ```bash
  python overlay.py
  ```

  This script will display an overlay with sample statistics. Customize the text and appearance as needed.

### Object Detector (`object_detector.py`)

This module uses pre-trained models to detect objects in images.

- **Key Functions**:
    - Uses `YolosFeatureExtractor` and `YolosForObjectDetection` to perform object detection.

- **Usage**:

  ```bash
  python object_detector.py
  ```

  This script demonstrates object detection using the YOLOS model. The script downloads an example image and applies the
  object detection model to identify objects.

### Custom Logger (`custom_logger.py`)

The `custom_logger.py` module provides a custom logging setup with color-coded log levels for better readability.

- **Key Functions**:
    - `setup_logging(level, log_to_file, filename)`: Sets up logging with the specified level and output options.

- **Usage**:

  This module is used internally by other scripts. To customize logging behavior, modify the `setup_logging` function
  in `custom_logger.py`.

## Future Activities and Use Cases

This project is designed to be scalable, with plans to include many more scripts in the future. These will cover a wide
range of in-game activities, such as:

- **Automated Combat**: Using CV to identify enemies and perform combat actions.
- **Resource Gathering**: Automating tasks like woodcutting, mining, and fishing.
- **Quest Automation**: Completing simple quests or repetitive tasks using AI.
- **Trading and Merchanting**: Automating in-game trading processes.

Each new script will be documented with detailed instructions on how to use it and integrate it into the broader
automation framework.

## Contributing

Contributions are welcome! Please fork this repository and submit a pull request with your changes. Ensure that your
code is well-documented and adheres to the project's coding standards.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

