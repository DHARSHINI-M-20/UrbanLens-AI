from process_result import process_result


image_path = "ai/ocr/sample_sign.jpg"
ocr_text = "MocKUP a"
ocr_confidence = 26.0
similarity = 85.71


result = process_result(
    image_path,
    ocr_text,
    ocr_confidence,
    similarity
)


print("Complete Processing Result:")
print(result)