def escalate_to_vlm(image_path, ocr_text, ocr_confidence):
    """
    Prepare an uncertain OCR result for VLM processing.
    """

    result = {
        "image_path": image_path,
        "ocr_text": ocr_text,
        "ocr_confidence": ocr_confidence,
        "status": "VLM_ESCALATION_REQUIRED"
    }

    return result