import csv
import os

from ai.ocr.ocr_engine import extract_text
from ai.ocr.text_cleaner import clean_text
from ai.ocr.text_matcher import match_text
from ai.routing.process_result import process_result


images_folder = "data/evaluation/images"
csv_path = "data/evaluation/full_pipeline_results.csv"


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
        "decision",
        "status"
    ])

    for image_name, expected_text in expected_texts.items():

        image_path = os.path.join(
            images_folder,
            image_name
        )

        if not os.path.exists(image_path):
            print("Image not found:", image_name)
            continue

        # OCR
        ocr_text, ocr_confidence = extract_text(image_path)

        # Clean OCR text
        cleaned_text = clean_text(ocr_text)

        # Compare with reference text
        similarity = match_text(
            cleaned_text,
            expected_text
        )

        # Process routing
        result = process_result(
            image_path,
            cleaned_text,
            ocr_confidence,
            similarity
        )

        if result.get("decision") == "ACCEPT_OCR":

            decision = "ACCEPT_OCR"
            status = "OCR_RESULT_ACCEPTED"

        else:

            decision = "ESCALATE_TO_VLM"
            status = result.get(
                "status",
                "VLM_ESCALATION_REQUIRED"
            )

        writer.writerow([
            image_name,
            expected_text,
            cleaned_text,
            ocr_confidence,
            similarity,
            decision,
            status
        ])

        print()
        print("Image:", image_name)
        print("OCR:", cleaned_text)
        print("OCR Confidence:", ocr_confidence)
        print("Text Similarity:", similarity)
        print("Decision:", decision)
        print("Status:", status)


print()
print("Full pipeline evaluation completed.")
print("Results saved to:", csv_path)