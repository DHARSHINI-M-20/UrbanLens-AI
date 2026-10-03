"""Run the registered offline evaluation fixture from the backend venv."""

from __future__ import annotations

import argparse
import json

from app.evaluation.runner import EvaluationRunner, FIXTURE_DATASET_ID, FIXTURE_VERSION


def main() -> None:
    parser = argparse.ArgumentParser(description="Run UrbanLens' registered synthetic evaluation fixture.")
    parser.add_argument("--dataset-id", default=FIXTURE_DATASET_ID)
    parser.add_argument("--dataset-version", default=FIXTURE_VERSION)
    parser.add_argument("--subset", action="append", help="image_id to include; may be repeated")
    parser.add_argument("--category", action="append", dest="categories", help="metric category; may be repeated")
    args = parser.parse_args()
    result = EvaluationRunner().run(
        dataset_id=args.dataset_id,
        dataset_version=args.dataset_version,
        subset=args.subset,
        categories=args.categories,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
