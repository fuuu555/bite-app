"""Import official Tourism Administration JSON archives.

Usage:
    uv run --project apps/backend python apps/backend/scripts/import_tourism_data.py
    uv run --project apps/backend python apps/backend/scripts/import_tourism_data.py --dataset food
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from api.core.database import session_factory
from api.services.tourism_data import (
    DATASET_CONFIGS,
    download_dataset_document,
    import_dataset_document,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run(datasets: list[str]) -> None:
    reports = []
    async with session_factory() as session:
        for dataset in datasets:
            logger.info("downloading tourism dataset: %s", dataset)
            document = await download_dataset_document(dataset)  # type: ignore[arg-type]
            report = await import_dataset_document(session, dataset, document)  # type: ignore[arg-type]
            await session.commit()
            reports.append(report.__dict__)
            logger.info("imported tourism dataset: %s", report)

    print(json.dumps(reports, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import official Tourism Administration data")
    parser.add_argument(
        "--dataset",
        action="append",
        choices=sorted(DATASET_CONFIGS),
        help="Dataset to import; repeat the flag. Defaults to food and attraction.",
    )
    args = parser.parse_args()
    asyncio.run(run(args.dataset or list(DATASET_CONFIGS)))


if __name__ == "__main__":
    main()
