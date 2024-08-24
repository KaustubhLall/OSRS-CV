import requests
from PIL import Image, ImageDraw
import io


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
        results = response.json()["results"]

        # Open the image
        image = Image.open(image_path)
        draw = ImageDraw.Draw(image)

        # Annotate the image with bounding boxes and labels
        for result in results:
            box = result["box"]
            label = result["label"]
            probability = result["probability"]

            # Draw the bounding box
            draw.rectangle(((box[0], box[1]), (box[2], box[3])), outline="red", width=3)
            # Add the label and probability
            draw.text((box[0], box[1]), f"{label}: {probability:.2f}", fill="white")

        # Save the annotated image if an output path is provided
        if output_path:
            image.save(output_path)
            print(f"Annotated image saved to {output_path}")

        # Optionally display the image
        if display:
            image.show()

        # Return the annotated image (in memory)
        return True, image
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return False, None


# Example usage
if __name__ == "__main__":
    import argparse

    # Argument parser for configurability
    parser = argparse.ArgumentParser(description="Client for YOLOS object detection")
    parser.add_argument("--url", type=str, default="http://localhost:8000/predict/", help="URL of the FastAPI server")
    parser.add_argument("--image", type=str, required=True, help="Path to the input image")
    parser.add_argument("--output", type=str, help="Path to save the annotated image (optional)")
    parser.add_argument("--threshold", type=float, default=0.5, help="Confidence threshold for predictions")
    parser.add_argument("--display", action="store_true", help="Display the annotated image after processing")

    args = parser.parse_args()

    # Call the function
    success, annotated_image = yolos_object_detection(
        url=args.url,
        image_path=args.image,
        output_path=args.output,
        threshold=args.threshold,
        display=args.display
    )

    if success and annotated_image:
        # Further processing can be done with `annotated_image` in memory if needed
        pass
