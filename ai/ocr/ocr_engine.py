import pytesseract
from PIL import Image, ImageEnhance, ImageFilter


def extract_text(image_path):
    """
    Extract text and confidence score from an image.
    """

    image = Image.open(image_path)

    # Convert to grayscale
    image = image.convert("L")

    # Improve contrast
    image = ImageEnhance.Contrast(image).enhance(2)

    # Sharpen image
    image = image.filter(ImageFilter.SHARPEN)

    # Extract OCR data
    data = pytesseract.image_to_data(
        image,
        config="--psm 6",
        output_type=pytesseract.Output.DICT
    )

    words = []
    confidences = []

    for i in range(len(data["text"])):
        word = data["text"][i].strip()
        confidence = float(data["conf"][i])

        if word and confidence >= 0:
            words.append(word)
            confidences.append(confidence)

    text = " ".join(words)

    if confidences:
        average_confidence = sum(confidences) / len(confidences)
    else:
        average_confidence = 0

    return text, round(average_confidence, 2)