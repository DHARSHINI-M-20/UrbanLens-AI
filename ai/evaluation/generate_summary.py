import csv
import os


csv_path = "data/evaluation/ocr_evaluation.csv"
output_path = "data/evaluation/evaluation_summary.txt"


total_images = 0
target_detected = 0

ocr_accepted = 0
vlm_escalated = 0

confidences = []
similarities = []
word_coverages = []


with open(
    csv_path,
    "r",
    encoding="utf-8"
) as file:

    reader = csv.DictReader(file)

    for row in reader:

        total_images += 1

        if row["overall_detection"].lower() == "true":
            target_detected += 1

        if row["routing_decision"] == "ACCEPT_OCR":
            ocr_accepted += 1

        elif row["routing_decision"] == "ESCALATE_TO_VLM":
            vlm_escalated += 1

        confidences.append(
            float(row["ocr_confidence"])
        )

        similarities.append(
            float(row["target_similarity"])
        )

        word_coverages.append(
            float(row["word_coverage"])
        )


if total_images > 0:

    detection_rate = (
        target_detected
        / total_images
    ) * 100

    ocr_acceptance_rate = (
        ocr_accepted
        / total_images
    ) * 100

    vlm_escalation_rate = (
        vlm_escalated
        / total_images
    ) * 100

else:

    detection_rate = 0
    ocr_acceptance_rate = 0
    vlm_escalation_rate = 0


average_confidence = (
    sum(confidences) / len(confidences)
    if confidences else 0
)

average_similarity = (
    sum(similarities) / len(similarities)
    if similarities else 0
)

average_word_coverage = (
    sum(word_coverages) / len(word_coverages)
    if word_coverages else 0
)


summary = f"""
UrbanLens AI - OCR Evaluation Summary
=====================================

Dataset
-------
Total Evaluation Images: {total_images}

Target Text Detection
---------------------
Target Text Detected: {target_detected}
Target Detection Rate: {detection_rate:.2f}%

OCR Routing
-----------
OCR Accepted: {ocr_accepted}
OCR Acceptance Rate: {ocr_acceptance_rate:.2f}%

VLM Escalation: {vlm_escalated}
VLM Escalation Rate: {vlm_escalation_rate:.2f}%

OCR Metrics
-----------
Average OCR Confidence: {average_confidence:.2f}%
Average Target Similarity: {average_similarity:.2f}%
Average Word Coverage: {average_word_coverage:.2f}%

Interpretation
--------------
The evaluation uses multiple Tesseract OCR page segmentation
modes (PSM 6, PSM 11 and PSM 12).

Target Text Detection measures whether the primary
business/institution/sign text can be identified despite
OCR noise or minor recognition errors.

The OCR routing system accepts high-confidence results
and escalates uncertain results to the VLM stage.

The current VLM component is an escalation interface and
has not yet been connected to an external VLM API.

Limitations
-----------
1. The evaluation dataset contains only {total_images} images.
2. Images contain background text and visual noise.
3. OCR performance varies depending on text size,
   orientation and image quality.
4. Target Detection Rate is an evaluation metric and
   should not be treated as production accuracy.
5. Additional images are required for a stronger evaluation.

Status
------
OCR evaluation baseline completed.
Confidence-based routing implemented.
VLM escalation interface implemented.
Actual VLM API integration is pending.
"""


with open(
    output_path,
    "w",
    encoding="utf-8"
) as file:

    file.write(
        summary.strip()
    )


print(summary)

print()
print(
    "Summary saved to:",
    output_path
)