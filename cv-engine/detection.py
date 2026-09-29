from pathlib import Path
import argparse
import json

from ultralytics import YOLO


def detect_objects(image_path):
    image_path = Path(image_path)

    if not image_path.is_file():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    # Load a general-purpose pretrained YOLO model
    model = YOLO("yolo11n.pt")

    # Run detection
    results = model.predict(
        source=str(image_path),
        conf=0.25,
        verbose=False
    )

    observations = []

    for result in results:
        for box in result.boxes:
            class_id = int(box.cls.item())
            confidence = float(box.conf.item())

            x1, y1, x2, y2 = (
                float(value)
                for value in box.xyxy[0].tolist()
            )

            observations.append({
                "entity_type": result.names[class_id],
                "bbox": [
                    round(x1, 2),
                    round(y1, 2),
                    round(x2, 2),
                    round(y2, 2)
                ],
                "confidence": round(confidence, 4),
                "model": "yolo11n",
                "processing_route": "lightweight"
            })

        # Save an annotated image
        result.save(filename="cv-engine/test_output.jpg")

    return observations


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--image",
        required=True,
        help="Path to the image"
    )

    args = parser.parse_args()

    predictions = detect_objects(args.image)

    print(json.dumps(predictions, indent=2))