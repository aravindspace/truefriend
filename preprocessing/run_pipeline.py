"""
Pipeline Runner — Orchestrates all 6 preprocessing steps.

Usage:
    python run_pipeline.py                  # Run full pipeline (steps 1-6)
    python run_pipeline.py --start-from 3   # Resume from step 3
"""

import argparse
import importlib
import sys
import time

# ---------------------------------------------------------------------------
# Step definitions
# ---------------------------------------------------------------------------

STEPS = [
    (1, "01_extract_chunks", "Semantic chunking of Gita transcript"),
    (2, "02_tag_chunks", "Metadata tagging of chunks"),
    (3, "03_build_routing_json", "Build routing schema"),
    (4, "04_load_qdrant", "Embed and store in Qdrant"),
    (5, "05_build_kuzu", "Build knowledge graph"),
    (6, "06_build_lineage", "Build Kuru dynasty lineage"),
]


def run_pipeline(start_from: int = 1, skip_preflight: bool = False) -> None:
    """Execute pipeline steps starting from the given step number."""
    pipeline_start = time.time()

    print("\n" + "=" * 70)
    print("  GITA RAG — DATA INJECTION PIPELINE")
    print("=" * 70)

    # Run preflight check before starting
    if not skip_preflight and start_from == 1:
        print("\n  Running preflight checks …\n")
        preflight = importlib.import_module("preflight")
        if not preflight.main():
            print("\n  ❌ Preflight failed — aborting pipeline.")
            sys.exit(1)

    if start_from > 1:
        print(f"  Resuming from step {start_from}")

    print()

    for step_num, module_name, description in STEPS:
        if step_num < start_from:
            print(f"  [SKIP] Step {step_num}: {description}")
            continue

        print(f"\n{'=' * 70}")
        print(f"  === Step {step_num}: {description} ===")
        print(f"{'=' * 70}\n")

        step_start = time.time()

        try:
            module = importlib.import_module(module_name)
            module.main()
        except Exception as exc:
            elapsed = time.time() - step_start
            print(f"\n  [FAILED] Step {step_num} failed after {elapsed:.1f}s")
            print(f"  Error: {exc}")
            print(f"\n  To resume, run: python run_pipeline.py --start-from {step_num}")
            sys.exit(1)

        elapsed = time.time() - step_start
        print(f"\n  [DONE] Step {step_num} completed in {elapsed:.1f}s")

    total_elapsed = time.time() - pipeline_start
    minutes = int(total_elapsed // 60)
    seconds = total_elapsed % 60

    print(f"\n{'=' * 70}")
    print(f"  PIPELINE COMPLETE!")
    print(f"  Total time: {minutes}m {seconds:.1f}s")
    print(f"{'=' * 70}\n")


def main() -> None:
    """Parse arguments and run the pipeline."""
    parser = argparse.ArgumentParser(
        description="Gita RAG — Data Injection Pipeline Runner",
    )
    parser.add_argument(
        "--start-from",
        type=int,
        default=1,
        choices=range(1, 7),
        metavar="N",
        help="Step number to start from (1-6, default: 1)",
    )
    args = parser.parse_args()
    run_pipeline(start_from=args.start_from)


if __name__ == "__main__":
    main()
