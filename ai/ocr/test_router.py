from confidence_router import route_result


ocr_confidence = 26.0
similarity = 85.71

decision = route_result(
    ocr_confidence,
    similarity
)

print("OCR Confidence:", ocr_confidence)
print("Text Similarity:", similarity)
print("Routing Decision:", decision)