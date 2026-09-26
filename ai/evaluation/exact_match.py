import csv

csv_path = "data/evaluation/ocr_evaluation.csv"

total = 0
exact_matches = 0

with open(csv_path, "r", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    for row in reader:
        total += 1

        expected = row["expected_text"].strip().lower()
        actual = row["ocr_text"].strip().lower()

        if expected == actual:
            exact_matches += 1

accuracy = (exact_matches / total) * 100

print("Total Images:", total)
print("Exact Matches:", exact_matches)
print("Exact Text Match Rate:", round(accuracy, 2), "%")
