#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT

"""
Extract output prompts from orchestration parquet files.

Usage:
    python scripts/manifest_extract.py <parquet_file> [options]

Examples:
    # Auto-detect output prompts (from parquet metadata or convention)
    python scripts/manifest_extract.py ./outputs/linkedin_ai_post/20260324193142.parquet

    # List all prompt names in the parquet
    python scripts/manifest_extract.py ./outputs/results.parquet --list

    # Extract specific prompts
    python scripts/manifest_extract.py ./outputs/results.parquet --prompts final_post,summary

    # Output to specific directory (default: same folder as parquet)
    python scripts/manifest_extract.py ./outputs/results.parquet --output-dir ./extracted

Output structure:
    outputs/linkedin_ai_post/
    ├── 20260324193142.parquet
    └── 20260324193142/
        ├── final_post.md
        ├── hashtags.json
        ├── image_prompt.json
        └── _summary.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import polars as pl


def get_parquet_info(parquet_path: str) -> dict:
    """Get basic info from parquet file.

    Reads manifest metadata directly from parquet file.
    Falls back to convention-based detection if no metadata.

    Args:
        parquet_path: Path to parquet file.

    Returns:
        Dictionary with parquet metadata.

    """
    df = pl.read_parquet(parquet_path)
    parquet_file = Path(parquet_path)

    # Try to read metadata from parquet
    manifest_name = parquet_file.parent.name
    output_prompts = []

    try:
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(parquet_path)
        metadata = pf.schema_arrow.metadata or {}

        if b"manifest_name" in metadata:
            manifest_name = metadata[b"manifest_name"].decode("utf-8")
        if b"output_prompts" in metadata:
            output_prompts = json.loads(metadata[b"output_prompts"])
    except Exception:
        pass

    return {
        "parquet_path": parquet_path,
        "manifest_name": manifest_name,
        "output_prompts": output_prompts,
        "total_rows": len(df),
        "prompt_names": df["prompt_name"].to_list(),
    }


def detect_output_prompts(
    df: pl.DataFrame, specified_prompts: list[str] | None = None
) -> list[str]:
    """Determine which prompts to extract.

    Priority:
    1. Explicitly specified prompts (CLI --prompts)
    2. Prompts from manifest.yaml output_prompts field
    3. Convention: prompts named final_* or output_*
    4. Fallback: last prompt in sequence

    Args:
        df: DataFrame with prompt results.
        specified_prompts: Optional list of prompts from CLI.

    Returns:
        List of prompt names to extract.

    """
    if specified_prompts:
        return specified_prompts

    prompt_names = df["prompt_name"].to_list()

    # Convention: final_* or output_*
    final_prompts = [
        p for p in prompt_names if p and (p.startswith("final_") or p.startswith("output_"))
    ]
    if final_prompts:
        return final_prompts

    # Fallback: last prompt in sequence
    last_seq = df.select(["sequence", "prompt_name"]).sort("sequence").tail(1)
    if len(last_seq) > 0:
        last_prompt = last_seq["prompt_name"][0]
        if last_prompt:
            return [last_prompt]

    return []


def extract_prompt_response(df: pl.DataFrame, prompt_name: str) -> dict | None:
    """Extract response for a specific prompt.

    Args:
        df: DataFrame with prompt results.
        prompt_name: Name of prompt to extract.

    Returns:
        Dictionary with prompt data or None if not found.

    """
    filtered = df.filter(pl.col("prompt_name") == prompt_name)
    if len(filtered) == 0:
        return None

    row = filtered.row(0, named=True)
    return {
        "prompt_name": row["prompt_name"],
        "response": row.get("response"),
        "status": row.get("status"),
        "sequence": row.get("sequence"),
    }


def is_json_content(text: str | None) -> bool:
    """Check if text looks like JSON.

    Args:
        text: Text to check.

    Returns:
        True if text appears to be JSON.

    """
    if not text:
        return False
    text = text.strip()
    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        if len(lines) > 1:
            text = lines[1].strip()
    return text.startswith("{") or text.startswith("[")


def parse_json_safely(text: str | None) -> any:
    """Parse JSON, handling markdown code blocks.

    Args:
        text: Text to parse.

    Returns:
        Parsed JSON or None.

    """
    if not text:
        return None

    text = text.strip()

    # Remove markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        if len(lines) > 2:
            text = "\n".join(lines[1:-1])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def get_output_dir(parquet_path: str) -> Path:
    """Get output directory for extracted files.

    Output structure: same folder as parquet, with timestamp subfolder.

    Args:
        parquet_path: Path to parquet file.

    Returns:
        Path to output directory.

    """
    parquet_file = Path(parquet_path)
    # outputs/manifest_name/20260324193142.parquet -> outputs/manifest_name/20260324193142/
    timestamp = parquet_file.stem  # Already just the timestamp
    return parquet_file.parent / timestamp


def extract_results(
    parquet_path: str,
    prompts: list[str] | None = None,
    output_dir: str | None = None,
) -> dict:
    """Extract output prompts from parquet file.

    Args:
        parquet_path: Path to parquet file.
        prompts: Optional list of prompt names to extract.
        output_dir: Optional output directory override.

    Returns:
        Dictionary with extracted results.

    """
    df = pl.read_parquet(parquet_path)
    info = get_parquet_info(parquet_path)

    all_candidates = prompts or info["output_prompts"] or None
    output_prompts = detect_output_prompts(df, all_candidates)

    results = {
        "parquet_path": parquet_path,
        "manifest_name": info["manifest_name"],
        "extracted_at": datetime.now().isoformat(),
        "output_prompts": output_prompts,
        "extracted": {},
        "execution_summary": [],
    }

    # Extract each prompt
    for prompt_name in output_prompts:
        data = extract_prompt_response(df, prompt_name)
        if data:
            results["extracted"][prompt_name] = data

    # Build execution summary
    for row in (
        df.select(["sequence", "prompt_name", "status", "attempts"]).sort("sequence").iter_rows()
    ):
        results["execution_summary"].append(
            {
                "sequence": row[0],
                "prompt_name": row[1],
                "status": row[2],
                "attempts": row[3],
            }
        )

    return results


def save_results(results: dict, output_dir: Path | None = None) -> None:
    """Save extracted results to files.

    Args:
        results: Results dictionary from extract_results().
        output_dir: Optional output directory override.

    """
    if output_dir is None:
        output_dir = get_output_dir(results["parquet_path"])

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save each extracted prompt
    for prompt_name, data in results.get("extracted", {}).items():
        response = data.get("response")
        if not response:
            continue

        if is_json_content(response):
            # Save as JSON
            json_path = output_dir / f"{prompt_name}.json"
            parsed = parse_json_safely(response)
            if parsed:
                with open(json_path, "w") as f:
                    json.dump(parsed, f, indent=2)
            else:
                with open(json_path, "w") as f:
                    f.write(response)
            print(f"Saved: {json_path}")
        else:
            # Save as Markdown
            md_path = output_dir / f"{prompt_name}.md"
            with open(md_path, "w") as f:
                f.write(response)
                if not response.endswith("\n"):
                    f.write("\n")
            print(f"Saved: {md_path}")

    # Save summary
    summary_path = output_dir / "_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Saved: {summary_path}")


def print_results(results: dict) -> None:
    """Print extracted results to console.

    Args:
        results: Results dictionary from extract_results().

    """
    print(f"Parquet: {results['parquet_path']}")
    print(f"Manifest: {results['manifest_name']}")
    print(f"Output prompts: {results['output_prompts']}")
    print()

    for prompt_name, data in results.get("extracted", {}).items():
        print("=" * 70)
        print(f"{prompt_name.upper()}:")
        print("=" * 70)
        response = data.get("response")
        if response:
            # Try to pretty-print JSON
            parsed = parse_json_safely(response)
            if parsed:
                print(json.dumps(parsed, indent=2))
            else:
                print(response)
        else:
            print("(no response)")
        print()

    print("=" * 70)
    print("EXECUTION SUMMARY:")
    print("=" * 70)
    for item in results["execution_summary"]:
        status = item["status"]
        if status == "skipped":
            print(f"  {item['sequence']:2d}. {item['prompt_name']}: skipped")
        else:
            print(
                f"  {item['sequence']:2d}. {item['prompt_name']}: {status} ({item['attempts']} attempts)"
            )


def list_prompts(parquet_path: str) -> None:
    """List all prompt names in parquet file.

    Args:
        parquet_path: Path to parquet file.

    """
    df = pl.read_parquet(parquet_path)
    info = get_parquet_info(parquet_path)

    print(f"Parquet: {parquet_path}")
    print(f"Manifest: {info['manifest_name']}")
    print(f"Total prompts: {info['total_rows']}")
    print()
    print("Prompts:")

    for row in df.select(["sequence", "prompt_name", "status"]).sort("sequence").iter_rows():
        marker = ""
        if row[1] in info["output_prompts"]:
            marker = " [output]"
        elif row[1] and (row[1].startswith("final_") or row[1].startswith("output_")):
            marker = " [auto-detect]"
        print(f"  {row[0]:2d}. {row[1]} ({row[2]}){marker}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract output prompts from orchestration parquet files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("parquet", help="Path to parquet file")
    parser.add_argument(
        "--prompts",
        "-p",
        help="Comma-separated list of prompt names to extract (default: auto-detect)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        help="Output directory for extracted files (default: <parquet_dir>/<timestamp>/)",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List all prompt names in the parquet",
    )
    parser.add_argument(
        "--save",
        "-s",
        action="store_true",
        help="Save extracted results to files",
    )

    args = parser.parse_args()

    if not os.path.exists(args.parquet):
        print(f"Error: File not found: {args.parquet}")
        return 1

    if args.list:
        list_prompts(args.parquet)
        return 0

    prompts = None
    if args.prompts:
        prompts = [p.strip() for p in args.prompts.split(",")]

    results = extract_results(args.parquet, prompts=prompts, output_dir=args.output_dir)

    if args.save or args.output_dir:
        save_results(results, args.output_dir)
    else:
        print_results(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
