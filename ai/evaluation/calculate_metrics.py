import csv

csv_path = "data/evaluation/ocr_evaluation.csv"

confidences = []
similarities = []
accepted = 0
escalated = 0

with open(csv_path, "r", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    for row in reader:
        confidences.append(float(row["ocr_confidence"]))
        similarities.append(float(row["text_similarity"]))

        if row["routing_decision"] == "ACCEPT_OCR":
            accepted += 1
        elif row["routing_decision"] == "ESCALATE_TO_VLM":
            escalated += 1

average_confidence = sum(confidences) / len(confidences)
average_similarity = sum(similarities) / len(similarities)

print("Number of Images:", len(confidences))
print("Average OCR Confidence:", round(average_confidence, 2), "%")
print("Average Text Similarity:", round(average_similarity, 2), "%")
print("OCR Accepted:", accepted)
print("VLM Escalated:", escalated)
