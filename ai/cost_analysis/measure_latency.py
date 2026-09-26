import csv
import os
import time

from ai.ocr.ocr_engine import extract_text


images_folder = "data/evaluation/images"

print("OCR Latency Evaluation")
print("----------------------")

times = []

for image_name in os.listdir(images_folder):

    image_path = os.path.join(images_folder, image_name)

    if not image_name.lower().endswith((".jpg", ".jpeg", ".png")):
        continue

    start_time = time.perf_counter()

    text, confidence = extract_text(image_path)

    end_time = time.perf_counter()

    latency = (end_time - start_time) * 1000

    times.append(latency)

    print()
    print("Image:", image_name)
    print("OCR Confidence:", confidence)
    print("Processing Time:", round(latency, 2), "ms")


if times:
    average_latency = sum(times) / len(times)

    print()
    print("Average OCR Processing Time:",
          round(average_latency, 2), "ms")
