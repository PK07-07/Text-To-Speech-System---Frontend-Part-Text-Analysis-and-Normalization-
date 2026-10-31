"""Gold corpus review tooling.

Provides subcommands to export unverified gold items to CSV for human review
and to apply reviewer decisions back to the JSON gold files.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from pathlib import Path


def get_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "tests" / "data"


def export_batches(batch_size: int = 40) -> list[Path]:
    data_dir = get_data_dir()
    sources = [
        data_dir / "gold_inputs.json",
        data_dir / "realistic_calls.json",
    ]

    unreviewed: list[dict] = []
    for src in sources:
        if not src.exists():
            continue
        with open(src, "r", encoding="utf-8") as f:
            items = json.load(f)
        for it in items:
            if not it.get("verified", False):
                entry = dict(it)
                entry["_source_file"] = src.name
                if "category" not in entry:
                    entry["category"] = entry.get("description", "general")
                unreviewed.append(entry)

    if not unreviewed:
        print("No unverified items found to export.")
        return []

    # Clean existing batch files in root or current dir
    created_files: list[Path] = []
    num_batches = (len(unreviewed) + batch_size - 1) // batch_size
    fieldnames = ["id", "source_file", "category", "input", "proposed_output", "decision", "corrected_output"]

    for b_idx in range(num_batches):
        batch_items = unreviewed[b_idx * batch_size : (b_idx + 1) * batch_size]
        batch_path = Path(f"gold_review_batch_{b_idx + 1:02d}.csv")
        with open(batch_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in batch_items:
                writer.writerow({
                    "id": item["id"],
                    "source_file": item["_source_file"],
                    "category": item.get("category", ""),
                    "input": item["input"],
                    "proposed_output": item["proposed_output"],
                    "decision": "",
                    "corrected_output": "",
                })
        created_files.append(batch_path)
        print(f"Exported {len(batch_items)} items to {batch_path.name}")

    print(f"Total unreviewed items exported: {len(unreviewed)} across {len(created_files)} batches.")
    return created_files


def apply_reviews() -> None:
    data_dir = get_data_dir()
    batch_files = sorted(Path(".").glob("gold_review_batch_*.csv"))
    if not batch_files:
        print("No gold_review_batch_*.csv files found.")
        return

    # Load decisions from all batch files
    decisions: dict[str, dict] = {}
    for bf in batch_files:
        with open(bf, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                dec = (row.get("decision") or "").strip().lower()
                if dec:
                    decisions[row["id"]] = {
                        "decision": dec,
                        "corrected_output": (row.get("corrected_output") or "").strip(),
                        "source_file": row.get("source_file", "gold_inputs.json"),
                    }

    if not decisions:
        print("No reviewed decisions (non-blank 'decision' column) found across batch files.")
        return

    # Group decisions by source file
    by_source: dict[str, dict[str, dict]] = {}
    for item_id, info in decisions.items():
        src = info["source_file"]
        by_source.setdefault(src, {})[item_id] = info

    total_ok = 0
    total_fix = 0
    total_skip = 0

    for src_name, src_decisions in by_source.items():
        src_path = data_dir / src_name
        if not src_path.exists():
            print(f"Warning: Source file {src_path} not found.")
            continue

        # Backup
        backup_path = src_path.with_suffix(".json.bak")
        shutil.copyfile(src_path, backup_path)
        print(f"Backed up {src_path.name} to {backup_path.name}")

        with open(src_path, "r", encoding="utf-8") as f:
            items = json.load(f)

        for item in items:
            item_id = item["id"]
            if item_id in src_decisions:
                d = src_decisions[item_id]["decision"]
                if d == "ok":
                    item["verified"] = True
                    total_ok += 1
                elif d == "fix":
                    item["verified"] = True
                    item["proposed_output"] = src_decisions[item_id]["corrected_output"]
                    total_fix += 1
                elif d == "skip":
                    item["verified"] = False
                    total_skip += 1

        with open(src_path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

    print(f"Review decisions applied: {total_ok} verified (ok), {total_fix} corrected (fix), {total_skip} skipped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gold Corpus Review Tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export unreviewed gold items to CSV batches")
    export_parser.add_argument("--batch-size", type=int, default=40, help="Number of items per batch (default 40)")

    subparsers.add_parser("apply", help="Apply reviewed decisions from CSV batches to JSON files")

    args = parser.parse_args()
    if args.command == "export":
        export_batches(batch_size=args.batch_size)
    elif args.command == "apply":
        apply_reviews()


if __name__ == "__main__":
    main()
