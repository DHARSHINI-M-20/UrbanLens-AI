from confidence_router import route_result
from ocr_engine import extract_text
from text_cleaner import clean_text
from text_matcher import match_text


image_path = "ai/ocr/sample_sign.jpg"

text, confidence = extract_text(image_path)

cleaned_text = clean_text(text)

reference_text = "MocKUP"

similarity = match_text(
    cleaned_text,
    reference_text
)

print("Original OCR Text:")
print(text)

print("\nCleaned Text:")
print(cleaned_text)

print("\nOCR Confidence:")
print(f"{confidence}%")

print("\nReference Text:")
print(reference_text)

print("\nText Similarity:")
print(f"{similarity}%")