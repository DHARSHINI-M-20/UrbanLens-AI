import csv
import os

from ai.ocr.ocr_engine import extract_text_candidates
from ai.ocr.text_cleaner import clean_text
from ai.ocr.text_matcher import match_text
from ai.routing.confidence_router import route_result


images_folder = "data/evaluation/images"
csv_path = "data/evaluation/ocr_evaluation.csv"


target_texts = {
    "image 1.jpg": "MARCO PIERRE WHITE",
    "image 2.jpg": "PANDORA",
    "image 3.jpg": "Dubai English Speaking School",
    "image 4.jpg": "West Suffolk Hospital",
    "image 5.jpg": "Percy Ingle"
}


def normalize_text(text):
    text = clean_text(text)
    return text.lower().strip()


def word_coverage(target_text, ocr_text):

    target_words = normalize_text(
        target_text
    ).split()

    ocr_words = normalize_text(
        ocr_text
    ).split()

    if not target_words:
        return 0

    matched_words = 0

    for target_word in target_words:

        for ocr_word in ocr_words:

            if (
                target_word == ocr_word
                or target_word in ocr_word
                or ocr_word in target_word
            ):
                matched_words += 1
                break

    return round(
        (matched_words / len(target_words)) * 100,
        2
    )


with open(
    csv_path,
    "w",
    newline="",
    encoding="utf-8"
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "image_name",
        "target_text",
        "best_ocr_text",
        "best_psm",
        "ocr_confidence",
        "target_similarity",
        "word_coverage",
        "exact_detection",
        "overall_detection",
        "pipeline_psm",
        "pipeline_confidence",
        "routing_decision"
    ])

    total_images = 0
    detected_images = 0

    for image_name, target_text in target_texts.items():

        image_path = os.path.join(
            images_folder,
            image_name
        )

        if not os.path.exists(image_path):
            print(
                "Image not found:",
                image_name
            )
            continue

        total_images += 1

        candidates = extract_text_candidates(
            image_path
        )

        # --------------------------------
        # Evaluation:
        # Find the OCR candidate that
        # detects the target best.
        # --------------------------------

        best_candidate = None
        best_selection_score = -1

        for candidate in candidates:

            ocr_text = clean_text(
                candidate["text"]
            )

            similarity = match_text(
                ocr_text,
                target_text
            )

            coverage = word_coverage(
                target_text,
                ocr_text
            )

            normalized_target = normalize_text(
                target_text
            )

            normalized_ocr = normalize_text(
                ocr_text
            )

            exact_detection = (
                normalized_target
                in normalized_ocr
            )

            if exact_detection:
                selection_score = 100

            else:
                selection_score = (
                    coverage * 0.7
                    + similarity * 0.3
                )

            if selection_score > best_selection_score:

                best_selection_score = (
                    selection_score
                )

                best_candidate = {
                    "text": ocr_text,
                    "psm": candidate["psm"],
                    "confidence": candidate[
                        "confidence"
                    ],
                    "similarity": similarity,
                    "coverage": coverage,
                    "exact": exact_detection
                }

        # --------------------------------
        # Overall target detection
        # --------------------------------

        overall_detection = (
            best_candidate["exact"]
            or best_candidate["coverage"] >= 75
            or best_candidate["similarity"] >= 70
        )

        if overall_detection:
            detected_images += 1

        # --------------------------------
        # Actual pipeline candidate
        # --------------------------------

        pipeline_candidate = max(
            candidates,
            key=lambda x: x["score"]
        )

        pipeline_text = clean_text(
            pipeline_candidate["text"]
        )

        pipeline_confidence = (
            pipeline_candidate["confidence"]
        )

        pipeline_similarity = match_text(
            pipeline_text,
            target_text
        )

        routing_decision = route_result(
            pipeline_confidence,
            pipeline_similarity
        )

        # --------------------------------
        # Save evaluation result
        # --------------------------------

        writer.writerow([
            image_name,
            target_text,
            best_candidate["text"],
            best_candidate["psm"],
            best_candidate["confidence"],
            best_candidate["similarity"],
            best_candidate["coverage"],
            best_candidate["exact"],
            overall_detection,
            pipeline_candidate["psm"],
            pipeline_confidence,
            routing_decision
        ])

        print()
        print("Image:", image_name)
        print("Target:", target_text)

        print()
        print("Best Target Candidate")
        print(
            "PSM:",
            best_candidate["psm"]
        )
        print(
            "OCR:",
            best_candidate["text"]
        )
        print(
            "Confidence:",
            best_candidate["confidence"]
        )
        print(
            "Similarity:",
            best_candidate["similarity"],
            "%"
        )
        print(
            "Word Coverage:",
            best_candidate["coverage"],
            "%"
        )
        print(
            "Exact Detection:",
            best_candidate["exact"]
        )
        print(
            "Overall Detection:",
            overall_detection
        )

        print()
        print("Actual Pipeline Candidate")
        print(
            "PSM:",
            pipeline_candidate["psm"]
        )
        print(
            "Confidence:",
            pipeline_confidence
        )
        print(
            "Routing:",
            routing_decision
        )

    print()
    print("--------------------------------")
    print("Target Text Detection Evaluation")
    print("--------------------------------")

    print(
        "Total Images:",
        total_images
    )

    print(
        "Target Detected:",
        detected_images
    )

    if total_images > 0:

        detection_rate = (
            detected_images
            / total_images
        ) * 100

    else:

        detection_rate = 0

    print(
        "Target Detection Rate:",
        round(
            detection_rate,
            2
        ),
        "%"
    )


print()
print("Evaluation completed.")
print(
    "Results saved to:",
    csv_path
)