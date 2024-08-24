import requests
from PIL import Image, ImageDraw
from utils.custom_logger import setup_logging

logger = setup_logging(log_to_file=False)

def yolos_object_detection(url, image_path, output_path=None, threshold=0.5, display=False):
    """
    Send an image to the YOLOS object detection server and annotate the detected objects.

    Parameters:
    - url (str): URL of the FastAPI server.
    - image_path (str): Path to the input image.
    - output_path (str): Path to save the annotated image. If None, the image is not saved to disk.
    - threshold (float): Confidence threshold for predictions.
    - display (bool): Whether to display the annotated image after saving.

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

        # Open the image
        image = Image.open(image_path).convert("RGB")  # Ensure the image is in RGB mode
        draw = ImageDraw.Draw(image)
        image_width, image_height = image.size

        # Annotate the image with bounding boxes and labels
        for result in results:
            box = result["box"]
            label = result["label"]
            probability = result["probability"]

            # Convert normalized coordinates to pixel values
            x0 = int(box[0] * image_width)
            y0 = int(box[1] * image_height)
            x1 = int(box[2] * image_width)
            y1 = int(box[3] * image_height)

            # Ensure x0 <= x1 and y0 <= y1
            if x1 < x0:
                x0, x1 = x1, x0
            if y1 < y0:
                y0, y1 = y1, y0

            # Print the bounding box coordinates for debugging
            logger.debug(f"Box coordinates: {(x0, y0, x1, y1)}, label: {label}, probability: {probability}")

            # Draw the bounding box
            draw.rectangle(((x0, y0), (x1, y1)), outline="red", width=3)
            # Add the label and probability
            draw.text((x0, y0), f"{label}: {probability:.2f}", fill="white")

        # Save the annotated image if an output path is provided
        if output_path:
            image.save(output_path)
            logger.info(f"Annotated image saved to {output_path}")

        # Optionally display the image
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
    output_path = "outputs/annotated_image.jpg"  # Update if you want to save the output image
    threshold = 0.5
    display = True

    # Call the function
    success, annotated_image = yolos_object_detection(
        url=server_url,
        image_path=image_path,
        output_path=output_path,
        threshold=threshold,
        display=display
    )

    if success and annotated_image:
        # Further processing can be done with `annotated_image` in memory if needed
        pass
