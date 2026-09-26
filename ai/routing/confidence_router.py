def route_result(ocr_confidence, similarity):
    """
    Decide whether to accept OCR or escalate to VLM.
    """

    if ocr_confidence >= 70 and similarity >= 70:
        return "ACCEPT_OCR"

    return "ESCALATE_TO_VLM"