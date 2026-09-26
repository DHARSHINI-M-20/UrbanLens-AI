import re


def clean_text(text):
    """
    Clean noisy OCR output.
    """

    # Remove unwanted special characters
    text = re.sub(r"[^A-Za-z0-9\s]", " ", text)

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()