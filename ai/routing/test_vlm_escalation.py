from vlm_escalation import escalate_to_vlm


image_path = "ai/ocr/sample_sign.jpg"
ocr_text = "MocKUP a"
ocr_confidence = 26.0

result = escalate_to_vlm(
    image_path,
    ocr_text,
    ocr_confidence
)

print("VLM Escalation Result:")
print(result)