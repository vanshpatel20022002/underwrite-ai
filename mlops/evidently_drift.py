"""Evidently data drift report for property sales data.

Compares a reference dataset (training split) against a current sample.
If only one CSV is available, the script splits it 80/20 to demonstrate
the drift-detection workflow — this is clearly noted in the output.

Usage:
    python mlops/evidently_drift.py
    python mlops/evidently_drift.py --reference data/property_sales.csv
    python mlops/evidently_drift.py --reference data/property_sales.csv \\
                                    --current   data/property_sales_new.csv
    python mlops/evidently_drift.py --output reports/my_report.html

Output:
    reports/evidently_drift_report.html

Install Evidently:
    pip install evidently
"""

import argparse
import sys
from pathlib import Path

REPORT_COLUMNS = ["sale_price", "square_footage", "lot_size", "year_built", "property_type"]
DEFAULT_REFERENCE = Path(__file__).parent.parent / "data" / "property_sales.csv"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "reports" / "evidently_drift_report.html"


def _load_csv(path: Path, label: str):
    try:
        import pandas as pd
    except ImportError:
        print("ERROR: pandas is required. Install with: pip install pandas")
        sys.exit(1)

    if not path.exists():
        print(f"ERROR: {label} file not found: {path}")
        print("Run seed_data.py first to generate property_sales.csv")
        sys.exit(1)

    df = pd.read_csv(path, usecols=lambda c: c in REPORT_COLUMNS + ["latitude", "longitude"])
    available = [c for c in REPORT_COLUMNS if c in df.columns]
    return df[available]


def run_drift_report(reference_path: Path, current_path: Path | None, output_path: Path) -> None:
    try:
        from evidently import ColumnMapping
        from evidently.report import Report
        from evidently.metric_preset import DataDriftPreset, DataQualityPreset
    except ImportError:
        print(
            "Evidently is not installed.\n"
            "Install it with:  pip install evidently\n"
            "Then re-run:      python mlops/evidently_drift.py"
        )
        sys.exit(0)

    import pandas as pd

    reference_df = _load_csv(reference_path, "reference")

    if current_path is not None:
        current_df = _load_csv(current_path, "current")
        split_note = f"Reference: {reference_path.name}  |  Current: {current_path.name}"
    else:
        # Split the single file 80/20 to demonstrate the workflow
        split_idx = int(len(reference_df) * 0.8)
        current_df = reference_df.iloc[split_idx:].copy()
        reference_df = reference_df.iloc[:split_idx].copy()
        split_note = (
            f"Single file split 80/20 for demonstration — "
            f"reference={len(reference_df):,} rows, current={len(current_df):,} rows.\n"
            "In production, supply a separate --current file with newer data."
        )

    print(f"\nEvidently Drift Report")
    print(f"  {split_note}")
    print(f"  Columns: {', '.join(REPORT_COLUMNS)}")

    # Encode property_type as numeric for drift detection
    if "property_type" in reference_df.columns:
        for df in (reference_df, current_df):
            df["property_type"] = df["property_type"].astype("category").cat.codes

    column_mapping = ColumnMapping(target="sale_price")

    report = Report(metrics=[DataQualityPreset(), DataDriftPreset()])
    report.run(reference_data=reference_df, current_data=current_df, column_mapping=column_mapping)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report.save_html(str(output_path))
    print(f"\n  Report saved: {output_path}")
    print("  Open in browser to view drift results per column.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evidently drift report for property sales data")
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE,
                        help=f"Reference CSV (default: {DEFAULT_REFERENCE})")
    parser.add_argument("--current", type=Path, default=None,
                        help="Current/newer CSV to compare against (optional)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Output HTML report path (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    run_drift_report(args.reference, args.current, args.output)


if __name__ == "__main__":
    main()
