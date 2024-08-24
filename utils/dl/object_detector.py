import base64
import io

import requests
from PIL import Image, ImageDraw

from utils.custom_logger import setup_logging

logger = setup_logging(log_to_file=False)


def yolos_object_detection(url, image_path, output_path=None, threshold=0.5, display=False, debug_output_path=None):
    """
    Send an image to the YOLOS object detection server and annotate the detected objects.

    Parameters:
    - url (str): URL of the FastAPI server.
    - image_path (str): Path to the input image.
    - output_path (str): Path to save the annotated image. If None, the image is not saved to disk.
    - threshold (float): Confidence threshold for predictions.
    - display (bool): Whether to display the annotated image after saving.
    - debug_output_path (str): Path to save the annotated original model output without scaling. If None, it is not saved.

    Returns:
    - bool: True if the request was successful and the image was processed, False otherwise.
    - PIL.Image: The annotated image as a PIL Image object (in memory), or None if an error occurred.
    """

    # Send the image to the server for prediction
    with open(image_path, "rb") as f:
        files = {"file": f}
        params = {"threshold": threshold}
        response = requests.post(url, files=files, params=params)

    # Check if the request was successful
    if response.status_code == 200:
        response_data = response.json()
        results = response_data["results"]
        latency = response_data.get("latency", None)

        # Decode the processed image (original resolution as per the model)
        processed_image_data = base64.b64decode(response_data["processed_image"])
        processed_image = Image.open(io.BytesIO(processed_image_data))

        # Get the original input image size
        image = Image.open(image_path).convert("RGB")  # Ensure the image is in RGB mode
        image_width, image_height = image.size
        draw = ImageDraw.Draw(image)

        # Draw bounding boxes on the original image
        for result in results:
            box = result["box"]
            label = result["label"]
            probability = result["probability"]

            # Convert normalized coordinates to pixel values for the original image
            x0 = int(box[0] * image_width)
            y0 = int(box[1] * image_height)
            x1 = int(box[2] * image_width)
            y1 = int(box[3] * image_height)

            # Ensure x0 <= x1 and y0 <= y1
            if x1 < x0:
                x0, x1 = x1, x0
            if y1 < y0:
                y0, y1 = y1, y0

            # Draw the bounding box on the original image
            draw.rectangle(((x0, y0), (x1, y1)), outline="red", width=3)
            draw.text((x0, y0), f"{label}: {probability:.2f}", fill="white")

        # Save the annotated original input image if an output path is provided
        if output_path:
            image.save(output_path)
            logger.info(f"Annotated image saved to {output_path}")
        # Draw bounding boxes on the processed image (original resolution of the model)
        debug_draw = ImageDraw.Draw(processed_image)
        processed_width, processed_height = processed_image.size

        # Ensure that the processed image matches the model's output resolution
        processed_image = processed_image.resize((processed_width, processed_height))

        for result in results:
            box = result["box"]
            label = result["label"]
            probability = result["probability"]

            # Convert normalized coordinates to pixel values for the processed image
            x0_dbg = int(box[0] * processed_width)
            y0_dbg = int(box[1] * processed_height)
            x1_dbg = int(box[2] * processed_width)
            y1_dbg = int(box[3] * processed_height)

            if x1_dbg < x0_dbg:
                x0_dbg, x1_dbg = x1_dbg, x0_dbg
            if y1_dbg < y0_dbg:
                y0_dbg, y1_dbg = y1_dbg, y0_dbg

            # Draw the bounding box on the processed image
            debug_draw.rectangle(((x0_dbg, y0_dbg), (x1_dbg, y1_dbg)), outline="blue", width=2)
            debug_draw.text((x0_dbg, y0_dbg), f"{label}: {probability:.2f}", fill="white")

        # Save the annotated debug image if a debug output path is provided
        if debug_output_path:
            processed_image.save(debug_output_path)
            logger.info(f"Debug image saved to {debug_output_path}")

        # Optionally display the original image
        if display:
            image.show()

        # Print latency information
        if latency is not None:
            logger.debug(f"Processing latency: {latency:.4f} seconds")

        # Return the annotated image (in memory)
        return True, image
    else:
        logger.error(f"Error: {response.status_code}, {response.text}")
        return False, None


# Example usage without CLI arguments
if __name__ == "__main__":
    # Hardcoded parameters
    server_url = "http://localhost:8000/predict/"
    image_path = "C:/Users/kaust/PycharmProjects/RSBot/assets/screens/img_7.png"  # Update with your image path
    output_folder = "C:/Users/kaust/PycharmProjects/RSBot/utils/dl/outputs"
    output_path = f"{output_folder}/annotated_image.jpg"  # Update if you want to save the output image
    debug_output_path = f"{output_folder}/debug_original_output.jpg"  # Save the original model output
    threshold = 0.5
    display = True

    # Call the function
    success, annotated_image = yolos_object_detection(
        url=server_url,
        image_path=image_path,
        output_path=output_path,
        threshold=threshold,
        display=display,
        debug_output_path=debug_output_path
    )

    if success and annotated_image:
        # Further processing can be done with `annotated_image` in memory if needed
        pass
