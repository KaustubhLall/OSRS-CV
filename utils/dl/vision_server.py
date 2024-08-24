import time
import logging
from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse
import uvicorn
from PIL import Image
import io
import torch
from transformers import YolosImageProcessor, YolosForObjectDetection

from utils.custom_logger import setup_logging

app = FastAPI()

logger = setup_logging(log_to_file=False)

# Load the YOLOS model and image processor
image_processor = YolosImageProcessor.from_pretrained('hustvl/yolos-small')
model = YolosForObjectDetection.from_pretrained('hustvl/yolos-small')


@app.post("/predict/")
async def predict(file: UploadFile = File(...), threshold: float = Query(0.5)):
    try:
        # Start overall timer
        overall_start_time = time.time()

        # Step 1: Read and convert image
        start_time = time.time()
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")  # Ensure RGB format
        step_time = (time.time() - start_time) * 1000
        logger.info(f"Step 1 (Image Read & Convert): {step_time:.2f} ms")

        # Step 2: Preprocess the image
        start_time = time.time()
        inputs = image_processor(images=image, return_tensors="pt")
        step_time = (time.time() - start_time) * 1000
        logger.info(f"Step 2 (Image Preprocessing): {step_time:.2f} ms")

        # Step 3: Perform inference
        start_time = time.time()
        with torch.no_grad():  # Disabling gradient calculation for inference
            outputs = model(**inputs)
        step_time = (time.time() - start_time) * 1000
        logger.info(f"Step 3 (Model Inference): {step_time:.2f} ms")

        # Step 4: Post-process results
        start_time = time.time()
        logits = outputs.logits
        bboxes = outputs.pred_boxes
        probas = logits.softmax(-1)[0, :, :-1].max(-1)
        boxes = bboxes[0]
        results = []
        for i in range(len(probas[0])):
            if probas[0][i].item() > threshold:  # filter by a configurable threshold
                box = boxes[i].tolist()
                label = probas[1][i].item()
                results.append({"box": box, "label": label, "probability": probas[0][i].item()})
        step_time = (time.time() - start_time) * 1000
        logger.info(f"Step 4 (Post-Processing): {step_time:.2f} ms")

        # Calculate total latency
        total_latency = (time.time() - overall_start_time) * 1000
        logger.info(f"Total Processing time: {total_latency:.2f} ms")

        return JSONResponse(content={"results": results, "latency": total_latency / 1000})

    except Exception as e:
        logger.error(f"Error processing the image: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
