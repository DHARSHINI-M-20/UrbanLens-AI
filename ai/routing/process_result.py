from ai.routing.confidence_router import route_result
from ai.routing.vlm_escalation import escalate_to_vlm


def process_result(image_path, ocr_text, ocr_confidence, similarity):
    """
    Process OCR result and decide whether to accept OCR
    or escalate the result to a VLM.
    """

    decision = route_result(
        ocr_confidence,
        similarity
    )

    if decision == "ACCEPT_OCR":

        return {
            "image_path": image_path,
            "final_text": ocr_text,
            "decision": "ACCEPT_OCR",
            "ocr_confidence": ocr_confidence,
            "text_similarity": similarity
        }

    else:

        return escalate_to_vlm(
            image_path,
            ocr_text,
            ocr_confidence
        )