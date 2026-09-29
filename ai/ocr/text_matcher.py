from difflib import SequenceMatcher


def match_text(ocr_text, reference_text):
    """
    Compare OCR text with reference text
    and return a similarity score.
    """

    ocr_text = ocr_text.lower().strip()
    reference_text = reference_text.lower().strip()

    score = SequenceMatcher(
        None,
        ocr_text,
        reference_text
    ).ratio()

    return round(score * 100, 2)