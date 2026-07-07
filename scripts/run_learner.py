#!/usr/bin/env python3
"""Trigger Gita Learner batch job — studies concepts, writes MD notes.

Usage:
    python scripts/run_learner.py                    # Study all concepts from graph
    python scripts/run_learner.py --concepts karma dharma   # Study specific concepts
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.gita_learner import run_learner

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def main(concepts: list[str] | None, output_dir: str) -> None:
    generated = await run_learner(output_dir=output_dir, concepts=concepts)
    logger.info(f"\nGenerated {len(generated)} study notes:")
    for path in generated:
        logger.info(f"  -> {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Gita Learner batch study")
    parser.add_argument("--concepts", nargs="+", help="Specific concepts to study")
    parser.add_argument("--output-dir", default="knowledge/notes", help="Output directory")
    args = parser.parse_args()
    
    asyncio.run(main(args.concepts, args.output_dir))
