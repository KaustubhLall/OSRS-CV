import requests
import argparse
from PIL import Image, ImageDraw
import io
import os

# Argument parser for configurability
parser = argparse.ArgumentParser(description="Client for YOLOS object detection")
parser.add_argument("--url", type=str, default="http://localhost:8000/predict/", help="URL of the FastAPI server")
parser.add_argument("--image", type=str, required=True, help="Path to the input image")
parser.add_argument("--output", type=str, default="output.jpg", help="Path to save the annotated image")
parser.add_argument("--threshold", type=float, default=0.5, help="Confidence threshold for predictions")
parser.add_argument("--display", action="store_true", help="Display the annotated image after saving")

args = parser.parse_args()

# Send the image to the server for prediction
with open(args.image, "rb") as f:
    files = {"file": f}
    params = {"threshold": args.threshold}
    response = requests.post(args.url, files=files, params=params)

# Check if the request was successful
if response.status_code == 200:
    results = response.json()["results"]

    # Open the image
    image = Image.open(args.image)
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

    # Save the annotated image
    image.save(args.output)
    print(f"Annotated image saved to {args.output}")

    # Optionally display the image
    if args.display:
        image.show()

else:
    print(f"Error: {response.status_code}, {response.text}")
