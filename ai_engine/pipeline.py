"""
pipeline.py
────────────────────────────────────────────────────────────────
Master orchestrator — runs all 4 layers in one call.

Usage
─────
    python pipeline.py bank_data_encrypted.json

Or from code:
    from pipeline import run_pipeline
    result = run_pipeline("bank_data_encrypted.json")
────────────────────────────────────────────────────────────────
"""

import sys
import os
from dataclasses import dataclass

# Ensure local imports work
sys.path.insert(0, os.path.dirname(__file__))

from data_loader       import load_transactions_pro
from expense_classifier import classify_expenses
from feature_engineer  import engineer_features, FinancialFeatures
from prediction_engine import predict_next_month, SpendingPrediction
from anomaly_engine    import detect_anomalies, AnomalyReport
from savings_engine    import analyze_savings, SavingsReport


# ─────────────────────────────────────────────
# FULL PIPELINE RESULT
# ─────────────────────────────────────────────

@dataclass
class PipelineResult:
    features:   FinancialFeatures
    prediction: SpendingPrediction
    anomalies:  AnomalyReport
    savings:    SavingsReport

    def display_all(self):
        print("\n" + "═"*55)
        print("       🏦  FINANCIAL INTELLIGENCE REPORT")
        print("═"*55)

        # ── Layer 2: Features summary ────────
        print("\n📊  Monthly Overview (Last 3 Months)")
        print(self.features.monthly_summary.tail(3).to_string())

        # ── Layer 3: Savings ─────────────────
        self.savings.display()

        # ── Layer 4a: Prediction ─────────────
        self.prediction.display()

        # ── Layer 4b: Anomalies ──────────────
        self.anomalies.display()

        print("\n" + "═"*55)
        print("  ✅  Analysis Complete")
        print("═"*55 + "\n")


# ─────────────────────────────────────────────
# MAIN PIPELINE FUNCTION
# ─────────────────────────────────────────────

def run_pipeline(json_path: str) -> PipelineResult:
    print(f"[1/5] Loading transactions from {json_path}...")
    full_df = load_transactions_pro(json_path)

    if full_df.empty:
        raise ValueError("No transactions found in the provided JSON.")

    print(f"[2/5] Classifying expenses ({len(full_df)} transactions)...")
    expense_df = classify_expenses(json_path)

    print(f"[3/5] Engineering financial features...")
    features = engineer_features(expense_df, full_df)

    print(f"[4/5] Running prediction + anomaly detection...")
    prediction = predict_next_month(features)
    anomalies  = detect_anomalies(expense_df, features)

    print(f"[5/5] Computing savings opportunities + health score...")
    savings = analyze_savings(features, expense_df)

    return PipelineResult(
        features=features,
        prediction=prediction,
        anomalies=anomalies,
        savings=savings,
    )


# ─────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <path_to_json>")
        sys.exit(1)

    json_path = sys.argv[1]
    result = run_pipeline(json_path)
    result.display_all()