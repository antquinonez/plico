#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Inspect Parquet Result Files

Usage:
    python scripts/manifest_inspect.py <parquet_file> [options]

Examples:
    # Show summary and data preview (first/last 10 rows)
    python scripts/manifest_inspect.py ./outputs/results.parquet

    # Show only summary statistics
    python scripts/manifest_inspect.py ./outputs/results.parquet --summary

    # Show extended view with response column
    python scripts/manifest_inspect.py ./outputs/results.parquet --extended

    # Show full view with all columns
    python scripts/manifest_inspect.py ./outputs/results.parquet --full

    # Show only failed executions
    python scripts/manifest_inspect.py ./outputs/results.parquet --failed

    # Show all rows (be careful with large files)
    python scripts/manifest_inspect.py ./outputs/results.parquet --all

    # Export to CSV
    python scripts/manifest_inspect.py ./outputs/results.parquet --export csv

    # Filter by status
    python scripts/manifest_inspect.py ./outputs/results.parquet --status success
    python scripts/manifest_inspect.py ./outputs/results.parquet --status failed
    python scripts/manifest_inspect.py ./outputs/results.parquet --status skipped
"""

import argparse
import os
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator.results import ResultsFrame


def inspect_parquet(
    parquet_path: str,
    show_summary: bool = False,
    show_failed: bool = False,
    show_all: bool = False,
    status_filter: str | None = None,
    limit: int = 5,
    export_format: str | None = None,
    export_path: str | None = None,
    extended: bool = False,
    full: bool = False,
):
    if not os.path.exists(parquet_path):
        print(f"Error: File not found: {parquet_path}")
        return 1

    df = pl.read_parquet(parquet_path)

    total_rows = len(df)

    if status_filter:
        df = df.filter(pl.col("status") == status_filter)

    if show_failed:
        df = df.filter(pl.col("status") == "failed")

    if export_format:
        if export_path is None:
            base = os.path.splitext(parquet_path)[0]
            if export_format == "csv":
                export_path = f"{base}.csv"
            elif export_format == "json":
                export_path = f"{base}.json"

        if export_format == "csv":
            df.write_csv(export_path)
            print(f"Exported to CSV: {export_path}")
        elif export_format == "json":
            df.write_json(export_path)
            print(f"Exported to JSON: {export_path}")
        return 0

    print("\n" + "=" * 70)
    print("PARQUET FILE INSPECTION")
    print("=" * 70)
    print(f"File: {parquet_path}")
    print(f"Size: {os.path.getsize(parquet_path) / 1024:.1f} KB")
    print(f"Total rows: {total_rows}")

    if status_filter:
        print(f"Filtered by status: {status_filter} ({len(df)} rows)")

    if show_failed:
        print(f"Showing only failed executions ({len(df)} rows)")

    print("=" * 70)

    print("\nSCHEMA:")
    print("-" * 70)
    for col in df.schema:
        dtype = df.schema[col]
        print(f"  {col}: {dtype}")

    print("\nSTATISTICS:")
    print("-" * 70)

    frame = ResultsFrame.from_parquet(parquet_path)
    summary = frame.summary(is_batch_mode=True)

    for status in ("success", "failed", "skipped"):
        count = summary.get(status, 0)
        total = summary.get("total_prompts", len(df))
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {status}: {count} ({pct:.1f}%)")

    attempts_stats = df.select(
        [
            pl.col("attempts").min().alias("min"),
            pl.col("attempts").max().alias("max"),
            pl.col("attempts").mean().alias("avg"),
        ]
    )
    print(
        f"\n  Attempts: min={attempts_stats['min'][0]}, max={attempts_stats['max'][0]}, avg={attempts_stats['avg'][0]:.2f}"
    )

    if "batch_id" in df.columns and df["batch_id"].null_count() < len(df):
        print(f"  Batches: {summary.get('total_batches', 'n/a')}")

    if "client" in df.columns and df["client"].null_count() < len(df):
        clients = df.filter(pl.col("client").is_not_null()).select("client").unique()
        print(f"  Clients: {clients['client'].to_list()}")

    if show_summary:
        print("\n" + "=" * 70)
        return 0

    if full:
        display_cols = list(df.columns)
    elif extended:
        display_cols = [
            "sequence",
            "prompt_name",
            "client",
            "status",
            "attempts",
            "condition_result",
            "response",
        ]
    else:
        display_cols = ["sequence", "prompt_name", "client", "status", "attempts"]

    available_cols = [c for c in display_cols if c in df.columns]

    if "batch_id" in df.columns and df["batch_id"].null_count() < len(df):
        available_cols = ["batch_id", "batch_name"] + [
            c for c in available_cols if c not in ("batch_id", "batch_name")
        ]

    def format_table(dataframe, cols, is_full=False, is_extended=False):
        result = dataframe.select(cols)
        for col in cols:
            if col not in result.columns:
                continue
            if col == "batch_name":
                result = result.with_columns(
                    pl.col(col).fill_null("-").cast(pl.Utf8).str.slice(0, 12)
                )
            elif col == "prompt_name":
                result = result.with_columns(
                    pl.col(col).fill_null("-").cast(pl.Utf8).str.slice(0, 22)
                )
            elif col == "prompt":
                result = result.with_columns(
                    pl.col(col).fill_null("-").cast(pl.Utf8).str.slice(0, 40)
                )
            elif col == "response":
                max_len = 80 if is_extended else 50
                result = result.with_columns(
                    pl.col(col).fill_null("-").cast(pl.Utf8).str.slice(0, max_len)
                )
            elif col == "history":
                result = result.with_columns(
                    pl.col(col).fill_null("-").cast(pl.Utf8).str.slice(0, 30)
                )
            elif col in ("condition", "references"):
                result = result.with_columns(
                    pl.col(col).fill_null("-").cast(pl.Utf8).str.slice(0, 25)
                )
            elif col == "error":
                result = result.with_columns(
                    pl.col(col).fill_null("-").cast(pl.Utf8).str.slice(0, 30)
                )
            elif col == "client":
                result = result.with_columns(
                    pl.col(col).fill_null("-").cast(pl.Utf8).str.slice(0, 10)
                )
            elif col in ("batch_id", "sequence", "attempts"):
                result = result.with_columns(pl.col(col).fill_null("-").cast(pl.Utf8))
            elif col == "condition_result":
                result = result.with_columns(
                    pl.col(col).fill_null("-").cast(pl.Utf8).str.slice(0, 8)
                )
            else:
                result = result.with_columns(
                    pl.col(col).fill_null("-").cast(pl.Utf8).str.slice(0, 15)
                )
        return result

    if show_all:
        print("\nDATA (ALL ROWS):")
        print("-" * 120)
        formatted = format_table(df, available_cols, is_full=full, is_extended=extended)
        print(formatted)
        print(f"\nTotal rows: {len(df)}")
    else:
        view_name = "FULL" if full else "EXTENDED" if extended else ""
        print(f"\nDATA PREVIEW {view_name}(FIRST 10 ROWS):".strip())
        print("-" * 120)
        first_10 = df.head(10)
        formatted = format_table(first_10, available_cols, is_full=full, is_extended=extended)
        print(formatted)

        if len(df) > 20:
            print(f"\nDATA PREVIEW {view_name}(LAST 10 ROWS):".strip())
            print("-" * 120)
            last_10 = df.tail(10)
            formatted = format_table(last_10, available_cols, is_full=full, is_extended=extended)
            print(formatted)
        elif len(df) > 10:
            remaining = len(df) - 10
            print(f"\n... and {remaining} more rows")

    if show_failed and len(df) > 0:
        print("\n" + "-" * 70)
        print("ERROR DETAILS:")
        print("-" * 70)
        failed_df = df.filter(pl.col("status") == "failed")
        for row in failed_df.iter_rows(named=True):
            print(f"\n  Sequence: {row.get('sequence')}")
            print(f"  Prompt: {row.get('prompt_name')}")
            print(f"  Error: {row.get('error')}")
            print(f"  Attempts: {row.get('attempts')}")

    print("\n" + "=" * 70)

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Inspect parquet result files from orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("parquet", help="Path to parquet file")
    parser.add_argument(
        "--summary",
        "-s",
        action="store_true",
        help="Show only summary statistics (no data preview)",
    )
    parser.add_argument(
        "--failed",
        "-f",
        action="store_true",
        help="Show only failed executions with error details",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Show all rows (not just preview)",
    )
    parser.add_argument(
        "--status",
        choices=["success", "failed", "skipped"],
        help="Filter by execution status",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=5,
        help="Number of rows to preview (default: 5)",
    )
    parser.add_argument(
        "--export",
        choices=["csv", "json"],
        help="Export data to CSV or JSON format",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path for export (default: same name as parquet)",
    )
    parser.add_argument(
        "--extended",
        "-e",
        action="store_true",
        help="Show extended view with response column",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Show all columns in the table",
    )

    args = parser.parse_args()

    return inspect_parquet(
        parquet_path=args.parquet,
        show_summary=args.summary,
        show_failed=args.failed,
        show_all=args.all,
        status_filter=args.status,
        limit=args.limit,
        export_format=args.export,
        export_path=args.output,
        extended=args.extended,
        full=args.full,
    )


if __name__ == "__main__":
    sys.exit(main())
