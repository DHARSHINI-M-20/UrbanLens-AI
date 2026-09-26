# UrbanLens AI - OCR and VLM Cost Estimation

# Assumed cost per image
# OCR is locally executed, so there is no API cost.
OCR_COST_PER_IMAGE = 0.0

# Example estimated VLM API cost per image.
# Replace this value with the actual provider/model pricing
# when a VLM API is connected.
VLM_COST_PER_IMAGE = 0.01

total_images = 5
vlm_escalated = 4
ocr_processed = total_images

ocr_total_cost = ocr_processed * OCR_COST_PER_IMAGE
vlm_total_cost = vlm_escalated * VLM_COST_PER_IMAGE

total_cost = ocr_total_cost + vlm_total_cost

average_cost_per_image = total_cost / total_images

print("UrbanLens AI Cost Analysis")
print("---------------------------")

print("Total Images:", total_images)
print("OCR Processed:", ocr_processed)
print("VLM Escalated:", vlm_escalated)

print()
print("OCR Cost:", f"${ocr_total_cost:.4f}")
print("VLM Estimated Cost:", f"${vlm_total_cost:.4f}")
print("Total Estimated Cost:", f"${total_cost:.4f}")
print("Average Cost per Image:", f"${average_cost_per_image:.4f}")