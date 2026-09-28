import re

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def run_ocr(image, psm):
    """
    Run Tesseract OCR using a specific page segmentation mode.
    """

    data = pytesseract.image_to_data(
        image,
        config=f"--psm {psm}",
        output_type=pytesseract.Output.DICT
    )

    words = []
    confidences = []

    for i in range(len(data["text"])):

        word = data["text"][i].strip()

        try:
            confidence = float(data["conf"][i])
        except ValueError:
            continue

        if word and confidence >= 0:
            words.append(word)
            confidences.append(confidence)

    text = " ".join(words)

    if confidences:
        average_confidence = (
            sum(confidences) / len(confidences)
        )
    else:
        average_confidence = 0

    return text, average_confidence


def candidate_score(text, confidence):
    """
    Calculate a general OCR quality score.

    This does NOT use the expected/reference text.
    """

    words = text.split()

    if not words:
        return 0

    # Remove obviously noisy single-character tokens
    useful_words = [
        word for word in words
        if len(re.sub(r"[^A-Za-z0-9]", "", word)) >= 2
    ]

    if not useful_words:
        return 0

    useful_ratio = (
        len(useful_words) / len(words)
    )

    # Prefer readable words while still considering
    # Tesseract confidence.
    score = (
        confidence * 0.7
        + useful_ratio * 30
    )

    return round(score, 2)


def extract_text_candidates(image_path):
    """
    Generate OCR candidates using multiple
    Tesseract page segmentation modes.
    """

    image = Image.open(image_path)

    image = image.convert("L")

    width, height = image.size

    image = image.resize(
        (width * 2, height * 2)
    )

    image = ImageEnhance.Contrast(
        image
    ).enhance(2)

    image = image.filter(
        ImageFilter.SHARPEN
    )

    image = ImageOps.autocontrast(
        image
    )

    psm_modes = [6, 11, 12]

    candidates = []

    for psm in psm_modes:

        text, confidence = run_ocr(
            image,
            psm
        )

        score = candidate_score(
            text,
            confidence
        )

        candidates.append({
            "psm": psm,
            "text": text,
            "confidence": round(
                confidence,
                2
            ),
            "score": score
        })

    return candidates


def extract_text(image_path):
    """
    Return the best general OCR candidate.
    """

    candidates = extract_text_candidates(
        image_path
    )

    best = max(
        candidates,
        key=lambda x: x["score"]
    )

    return (
        best["text"],
        best["confidence"]
    )