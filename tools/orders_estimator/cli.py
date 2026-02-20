"""
Orders Estimator CLI

Usage:
    python tools/orders_estimator/cli.py train "Traning data algorith order estimation V2.csv"
    python tools/orders_estimator/cli.py train "Traning data algorith order estimation V2.csv" --force
    python tools/orders_estimator/cli.py train "Traning data algorith order estimation V2.csv" --skip-sweep
    python tools/orders_estimator/cli.py evaluate "Traning data algorith order estimation V2.csv"
    python tools/orders_estimator/cli.py predict enrichment.csv --output-csv predictions.csv
    python tools/orders_estimator/cli.py predict --sheet "https://docs.google.com/..." --worksheet "results"
"""

import argparse
import os
import sys

# Ensure tools/ is on the path so subpackage imports work
_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)


def cmd_train(args):
    """Train models from labeled data."""
    from orders_estimator.train import train_pipeline

    result = train_pipeline(
        csv_path=args.csv_path,
        output_dir=args.output_dir,
        force=args.force,
        skip_sweep=args.skip_sweep,
    )

    if result.get("skipped"):
        print("Training skipped (data unchanged). Use --force to retrain.")
        return

    meta = result.get("training_meta", {})
    print(f"\nFinal CV WAPE: {meta.get('cv_wape_mean', 'N/A'):.3f}")
    print(f"Models saved to: {result['models_dir']}")


def cmd_evaluate(args):
    """Cross-validate and report metrics (no model saved)."""
    import pandas as pd
    import json

    from orders_estimator.features import prepare_features
    from orders_estimator.evaluate import cross_validate, check_leakage
    from orders_estimator.config import REPORTS_DIR

    print("Loading data...")
    df = pd.read_csv(args.csv_path, encoding="utf-8-sig")
    print(f"  {len(df)} rows loaded.")

    print("Preparing features...")
    X, y, warnings = prepare_features(df, require_target=True)
    for w in warnings:
        print(f"  WARNING: {w}")

    print("Checking for leakage...")
    leakage = check_leakage(X, y)
    for w in leakage:
        print(f"  WARNING: {w}")

    print("Running cross-validation...")
    result = cross_validate(X, y)
    m = result["metrics"]

    print(f"\n{'='*50}")
    print(f"  EVALUATION REPORT ({result['n_folds']} folds, {result['n_samples']} samples)")
    print(f"{'='*50}")
    print(f"  WAPE:          {m['wape']['mean']:.3f} (+/- {m['wape']['std']:.3f})")
    print(f"  MAE:           {m['mae']['mean']:.0f} (+/- {m['mae']['std']:.0f})")
    print(f"  MdAE:          {m['mdae']['mean']:.0f} (+/- {m['mdae']['std']:.0f})")
    print(f"  R²:            {m['r2']['mean']:.3f} (+/- {m['r2']['std']:.3f})")
    print(f"  Spearman:      {m['spearman']['mean']:.3f} (+/- {m['spearman']['std']:.3f})")
    print(f"  Bucket exact:  {m['exact']['mean']:.1%}")
    print(f"  Bucket ±1:     {m['within_1']['mean']:.1%}")
    print(f"  Baseline WAPE: {result['baseline_naive_median_wape']:.3f}")

    if result.get("overfitting_warnings"):
        print("\n  Overfitting warnings:")
        for w in result["overfitting_warnings"]:
            print(f"    {w}")

    # Save report
    if args.report:
        report_path = args.report
    else:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        report_path = os.path.join(REPORTS_DIR, "cv_report.json")

    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n  Report saved: {report_path}")


def cmd_predict(args):
    """Generate predictions for stores."""
    import pandas as pd

    from orders_estimator.predict import predict_batch, load_models
    from orders_estimator.export_predictions import (
        export_to_google_sheet,
        read_enrichment_from_sheet,
    )

    # Load models first
    print("Loading models...")
    loaded = load_models(args.models_dir)
    meta = loaded["training_meta"]
    print(f"  Model v{meta.get('version', '?')} (trained {meta.get('trained_at', '?')[:10]})")
    print(f"  CV WAPE: {meta.get('cv_wape_mean', 'N/A')}")

    # Load input data
    if args.csv_path:
        print(f"\nLoading data from CSV: {args.csv_path}")
        df = pd.read_csv(args.csv_path, encoding="utf-8-sig")
    elif args.sheet:
        print(f"\nLoading data from Google Sheet...")
        df = read_enrichment_from_sheet(args.sheet, args.worksheet)
    else:
        print("ERROR: Provide either a CSV path or --sheet URL.", file=sys.stderr)
        sys.exit(1)

    print(f"  {len(df)} stores loaded.")

    # Predict
    print("\nGenerating predictions...")
    result_df = predict_batch(df, loaded=loaded)

    # Summary
    p50 = result_df["predicted_orders_p50"]
    print(f"\n  Prediction summary:")
    print(f"    Stores:  {len(result_df)}")
    print(f"    P50 min: {p50.min()}")
    print(f"    P50 max: {p50.max()}")
    print(f"    P50 median: {p50.median():.0f}")
    conf = result_df["prediction_confidence"].value_counts()
    for level in ["high", "medium", "low"]:
        print(f"    Confidence '{level}': {conf.get(level, 0)}")

    # Output to CSV
    if args.output_csv:
        output_cols = ["domain"] + [c for c in result_df.columns if c.startswith("predicted_") or c in ["prediction_confidence", "model_version"]]
        if "domain" not in result_df.columns:
            # Try common domain column names
            for col in ["domain (Seller key)", "Domain", "domain"]:
                if col in result_df.columns:
                    result_df["domain"] = result_df[col]
                    break
        result_df[output_cols].to_csv(args.output_csv, index=False)
        print(f"\n  Predictions saved to: {args.output_csv}")

    # Output to Google Sheet
    if args.sheet:
        print(f"\nExporting predictions to Google Sheet...")
        domain_col = "domain"
        if domain_col not in result_df.columns:
            for col in ["domain (Seller key)", "Domain"]:
                if col in result_df.columns:
                    result_df["domain"] = result_df[col]
                    break

        export_result = export_to_google_sheet(
            result_df,
            spreadsheet_url=args.sheet,
            worksheet_name=args.output_worksheet,
        )
        if export_result["success"]:
            print(f"  Written to: {export_result['data']['sheet_url']}")
            print(f"  Tab: '{export_result['data']['worksheet_name']}'")
            print(f"  Rows: {export_result['data']['rows_written']}")
        else:
            print(f"  ERROR: {export_result['error']}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Melonn Orders Estimator v1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- train ---
    train_parser = subparsers.add_parser("train", help="Train models from labeled data")
    train_parser.add_argument("csv_path", help="Path to training CSV")
    train_parser.add_argument("--force", action="store_true", help="Force retrain even if data unchanged")
    train_parser.add_argument("--skip-sweep", action="store_true", help="Skip hyperparameter sweep")
    train_parser.add_argument("--output-dir", default=None, help="Custom output directory")

    # --- evaluate ---
    eval_parser = subparsers.add_parser("evaluate", help="Cross-validate and report metrics")
    eval_parser.add_argument("csv_path", help="Path to training CSV")
    eval_parser.add_argument("--report", default=None, help="Output report path (JSON)")

    # --- predict ---
    pred_parser = subparsers.add_parser("predict", help="Generate predictions for stores")
    pred_parser.add_argument("csv_path", nargs="?", default=None, help="Path to enrichment CSV")
    pred_parser.add_argument("--sheet", default=None, help="Google Sheet URL")
    pred_parser.add_argument("--worksheet", default=None, help="Worksheet tab to read from")
    pred_parser.add_argument("--output-worksheet", default="predictions", help="Tab for predictions output")
    pred_parser.add_argument("--output-csv", default=None, help="Save predictions to local CSV")
    pred_parser.add_argument("--models-dir", default=None, help="Custom models directory")

    args = parser.parse_args()

    if args.command == "train":
        cmd_train(args)
    elif args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "predict":
        cmd_predict(args)


if __name__ == "__main__":
    main()
