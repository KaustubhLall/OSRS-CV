from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse
import uvicorn
from PIL import Image
import io
import torch
from transformers import YolosFeatureExtractor, YolosForObjectDetection

app = FastAPI()

# Load the YOLOS model and feature extractor
feature_extractor = YolosFeatureExtractor.from_pretrained('hustvl/yolos-small')
model = YolosForObjectDetection.from_pretrained('hustvl/yolos-small')


@app.post("/predict/")
async def predict(file: UploadFile = File(...), threshold: float = Query(0.5)):
    try:
        # Read image file
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))

        # Preprocess the image and prepare it for model inference
        inputs = feature_extractor(images=image, return_tensors="pt")

        # Perform inference
        outputs = model(**inputs)
        logits = outputs.logits
        bboxes = outputs.pred_boxes

        # Extract bounding boxes and classes with a configurable threshold
        probas = logits.softmax(-1)[0, :, :-1].max(-1)
        boxes = bboxes[0]

        results = []
        for i in range(len(probas[0])):
            if probas[0][i].item() > threshold:  # filter by a configurable threshold
                box = boxes[i].tolist()
                label = probas[1][i].item()
                results.append({"box": box, "label": label, "probability": probas[0][i].item()})

        return JSONResponse(content={"results": results})

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
