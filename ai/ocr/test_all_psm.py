from ai.ocr.ocr_engine import extract_text_candidates


images = [
    "data/evaluation/images/image 1.jpg",
    "data/evaluation/images/image 2.jpg",
    "data/evaluation/images/image 3.jpg",
    "data/evaluation/images/image 4.jpg",
    "data/evaluation/images/image 5.jpg"
]


for image_path in images:

    print()
    print("=" * 70)
    print("IMAGE:", image_path)
    print("=" * 70)

    candidates = extract_text_candidates(
        image_path
    )

    for candidate in candidates:

        print()
        print("PSM:", candidate["psm"])
        print("Confidence:", candidate["confidence"])
        print("Score:", candidate["score"])
        print("OCR:")
        print(candidate["text"])