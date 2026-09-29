import os

from ai.ocr.ocr_engine import extract_text_candidates
from ai.ocr.text_cleaner import clean_text
from ai.ocr.text_matcher import match_text
from ai.routing.confidence_router import route_result
from ai.routing.vlm_correction_simulator import (
    correct_text_with_vlm_simulation
)


images_folder = "data/evaluation/images"

target_texts = {
    "image 1.jpg": "MARCO PIERRE WHITE",
    "image 2.jpg": "PANDORA",
    "image 3.jpg": "Dubai English Speaking School",
    "image 4.jpg": "West Suffolk Hospital",
    "image 5.jpg": "Percy Ingle"
}


def normalize_text(text):
    return clean_text(text).lower().strip()


total_images = 0
exact_matches = 0


for image_name, target_text in target_texts.items():

    image_path = os.path.join(
        images_folder,
        image_name
    )

    if not os.path.exists(image_path):
        print("Image not found:", image_name)
        continue

    total_images += 1

    candidates = extract_text_candidates(
        image_path
    )

    # Select the OCR candidate using the
    # same general OCR quality score as the pipeline.
    pipeline_candidate = max(
        candidates,
        key=lambda x: x["score"]
    )

    ocr_text = clean_text(
        pipeline_candidate["text"]
    )

    ocr_confidence = (
        pipeline_candidate["confidence"]
    )

    similarity = match_text(
        ocr_text,
        target_text
    )

    decision = route_result(
        ocr_confidence,
        similarity
    )

    if decision == "ACCEPT_OCR":

        final_text = ocr_text
        source = "OCR"

    else:

        final_text = (
            correct_text_with_vlm_simulation(
                image_path
            )
        )

        source = "VLM_SIMULATION"

    exact_match = (
        normalize_text(final_text)
        == normalize_text(target_text)
    )

    if exact_match:
        exact_matches += 1

    print()
    print("=" * 60)
    print("IMAGE:", image_name)
    print("=" * 60)

    print("Target:", target_text)
    print("OCR Text:", ocr_text)
    print("OCR Confidence:", ocr_confidence)
    print("OCR Similarity:", similarity, "%")
    print("Routing Decision:", decision)
    print("Final Text:", final_text)
    print("Final Source:", source)
    print("Exact Match:", exact_match)


print()
print("=" * 60)
print("FINAL PIPELINE SIMULATION")
print("=" * 60)

print("Total Images:", total_images)
print("Exact Matches:", exact_matches)

if total_images > 0:

    exact_match_rate = (
        exact_matches / total_images
    ) * 100

else:

    exact_match_rate = 0

print(
    "Exact Match Rate:",
    round(exact_match_rate, 2),
    "%"
)

print()
print(
    "NOTE: The VLM result is simulated using "
    "ground-truth text for pipeline testing."
)
print(
    "It must NOT be reported as actual VLM accuracy."
)