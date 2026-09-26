import csv
import os

from ai.ocr.ocr_engine import extract_text
from ai.ocr.text_cleaner import clean_text
from ai.ocr.text_matcher import match_text
from ai.routing.confidence_router import route_result


images_folder = "data/evaluation/images"
csv_path = "data/evaluation/ocr_evaluation.csv"


expected_texts = {
    "image 1.jpg": "MARCO PIERRE WHITE MR. WHITE'S ENGLISH CHOPHOUSE EST 2023",
    "image 2.jpg": "PANDORA",
    "image 3.jpg": "Dubai English Speaking School",
    "image 4.jpg": "West Suffolk Hospital",
    "image 5.jpg": "Percy Ingle"
}


with open(csv_path, "w", newline="", encoding="utf-8") as file:

    writer = csv.writer(file)

    writer.writerow([
        "image_name",
        "expected_text",
        "ocr_text",
        "ocr_confidence",
        "text_similarity",
        "routing_decision"
    ])

    for image_name, expected_text in expected_texts.items():

        image_path = os.path.join(images_folder, image_name)

        if not os.path.exists(image_path):
            print("Image not found:", image_name)
            continue

        ocr_text, ocr_confidence = extract_text(image_path)

        cleaned_text = clean_text(ocr_text)

        similarity = match_text(
            cleaned_text,
            expected_text
        )

        decision = route_result(
            ocr_confidence,
            similarity
        )

        writer.writerow([
            image_name,
            expected_text,
            cleaned_text,
            ocr_confidence,
            similarity,
            decision
        ])

        print()
        print("Image:", image_name)
        print("Expected:", expected_text)
        print("OCR:", cleaned_text)
        print("OCR Confidence:", ocr_confidence)
        print("Text Similarity:", similarity)
        print("Routing:", decision)


print()
print("Evaluation completed.")
print("Results saved to:", csv_path)
