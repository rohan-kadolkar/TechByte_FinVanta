"""
prediction_engine.py
────────────────────────────────────────────────────────────────
Predicts next month's spending range using historical features.

Strategy
────────
1. Baseline  → weighted moving average (always works, even with <6 months data)
2. ML Model  → Gradient Boosting Regressor (kicks in when ≥6 months data)
3. Output    → point estimate + ±confidence interval band

Input  : FinancialFeatures (from feature_engineer.py)
Output : SpendingPrediction dataclass
────────────────────────────────────────────────────────────────
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, Tuple


# ─────────────────────────────────────────────
# OUTPUT SCHEMA
# ─────────────────────────────────────────────

@dataclass
class SpendingPrediction:
    predicted_amount: float          # Point estimate ₹
    lower_bound: float               # ₹ (pessimistic)
    upper_bound: float               # ₹ (optimistic)
    confidence_pct: float            # Model confidence 0–100
    method_used: str                 # "weighted_avg" | "gradient_boost" | "linear"
    prediction_month: str            # e.g. "2024-05"
    feature_importances: dict        # {} if baseline method

    def display(self):
        print(f"\n{'━'*45}")
        print(f"  📅  Prediction for  : {self.prediction_month}")
        print(f"  💰  Estimated Spend : ₹{self.predicted_amount:,.0f}")
        print(f"  📉  Lower Bound     : ₹{self.lower_bound:,.0f}")
        print(f"  📈  Upper Bound     : ₹{self.upper_bound:,.0f}")
        print(f"  🎯  Confidence      : {self.confidence_pct:.0f}%")
        print(f"  🔧  Method          : {self.method_used}")
        if self.feature_importances:
            print(f"\n  Top Drivers:")
            for feat, imp in sorted(
                self.feature_importances.items(), key=lambda x: -x[1]
            )[:5]:
                print(f"    • {feat:<25} {imp*100:.1f}%")
        print(f"{'━'*45}")


# ─────────────────────────────────────────────
# PREDICTION ENGINE
# ─────────────────────────────────────────────

class PredictionEngine:
    """
    Usage
    ─────
    from prediction_engine import PredictionEngine

    engine = PredictionEngine(features)
    pred   = engine.predict()
    pred.display()
    """

    MIN_MONTHS_FOR_ML = 6    # fall back to weighted avg below this

    def __init__(self, features, confidence_interval: float = 0.15):
        """
        features            : FinancialFeatures object
        confidence_interval : fraction for bound width (0.15 = ±15%)
        """
        self.features = features
        self.ci = confidence_interval
        self.summary = features.monthly_summary.copy()

    # ─────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────

    def predict(self) -> SpendingPrediction:
        n = len(self.summary)

        if n < 2:
            return self._fallback_prediction()

        if n >= self.MIN_MONTHS_FOR_ML:
            return self._ml_prediction()
        else:
            return self._weighted_avg_prediction()

    # ─────────────────────────────────────────
    # METHOD 1 — WEIGHTED MOVING AVERAGE
    # (works with 2–5 months of data)
    # ─────────────────────────────────────────

    def _weighted_avg_prediction(self) -> SpendingPrediction:
        expenses = self.summary["expense"].values.astype(float)

        # Exponential weights — recent months matter more
        weights = np.exp(np.linspace(0, 1, len(expenses)))
        weights /= weights.sum()

        predicted = float(np.dot(weights, expenses))

        # Adjust by trend slope
        slope = self.features.expense_slope
        predicted += slope  # add one month's trend

        lower, upper = self._bounds(predicted, self.features.expense_volatility)
        next_month   = self._next_month_label()

        return SpendingPrediction(
            predicted_amount=round(predicted, 2),
            lower_bound=round(lower, 2),
            upper_bound=round(upper, 2),
            confidence_pct=self._confidence_score(method="weighted_avg"),
            method_used="weighted_avg",
            prediction_month=next_month,
            feature_importances={},
        )

    # ─────────────────────────────────────────
    # METHOD 2 — GRADIENT BOOSTING
    # (kicks in with ≥6 months of data)
    # ─────────────────────────────────────────

    def _ml_prediction(self) -> SpendingPrediction:
        try:
            from sklearn.ensemble import GradientBoostingRegressor
        except ImportError:
            # sklearn not installed — fall back gracefully
            return self._weighted_avg_prediction()

        X, y = self._build_feature_matrix()

        if len(X) < 3:
            return self._weighted_avg_prediction()

        model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=3,
            random_state=42,
        )
        model.fit(X, y)

        # Predict next month
        X_next = self._next_month_features(X)
        predicted = float(model.predict(X_next)[0])
        predicted = max(predicted, 0)  # no negative spend

        vol = self.features.expense_volatility
        lower, upper = self._bounds(predicted, vol)
        next_month   = self._next_month_label()

        importances = dict(zip(X.columns, model.feature_importances_))

        return SpendingPrediction(
            predicted_amount=round(predicted, 2),
            lower_bound=round(lower, 2),
            upper_bound=round(upper, 2),
            confidence_pct=self._confidence_score(method="gradient_boost"),
            method_used="gradient_boost",
            prediction_month=next_month,
            feature_importances=importances,
        )

    # ─────────────────────────────────────────
    # FEATURE MATRIX BUILDER
    # ─────────────────────────────────────────

    def _build_feature_matrix(self) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Each row = one month.
        Features for month T → predict expense at T+1.
        """
        df = self.summary.copy()
        df = df.reset_index()

        feature_rows = []
        targets = []

        for i in range(1, len(df)):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]

            row = {
                "prev_expense":       prev["expense"],
                "prev_income":        prev["income"],
                "prev_savings_rate":  prev["savings_rate"],
                "expense_slope":      self.features.expense_slope,
                "expense_volatility": self.features.expense_volatility,
                "month_index":        i,
            }

            # Add category % features if available
            if not self.features.category_pct.empty:
                cat_pct = self.features.category_pct
                prev_month = prev["month"]
                if prev_month in cat_pct.index:
                    for col in cat_pct.columns:
                        row[f"cat_pct_{col}"] = cat_pct.loc[prev_month, col]

            feature_rows.append(row)
            targets.append(curr["expense"])

        X = pd.DataFrame(feature_rows).fillna(0)
        y = pd.Series(targets, name="expense")

        return X, y

    def _next_month_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """Use last row of X as proxy for next-month features."""
        last = X.iloc[-1].copy()
        last["month_index"] = last["month_index"] + 1

        # Update prev_expense with actual last month
        last["prev_expense"] = self.summary["expense"].iloc[-1]
        last["prev_income"]  = self.summary["income"].iloc[-1]
        last["prev_savings_rate"] = self.summary["savings_rate"].iloc[-1]

        return pd.DataFrame([last])

    # ─────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────

    def _bounds(self, predicted: float, volatility: float) -> Tuple[float, float]:
        """
        Use actual volatility to set bounds.
        Falls back to ci% of predicted if volatility is 0.
        """
        band = max(volatility, predicted * self.ci)
        return max(0, predicted - band), predicted + band

    def _confidence_score(self, method: str) -> float:
        n = len(self.summary)
        base = {"weighted_avg": 55, "gradient_boost": 78, "linear": 65}
        score = base.get(method, 50)
        # More data → more confidence (up to +15)
        score += min(15, n * 2)
        # High volatility → less confidence
        vol_ratio = self.features.expense_volatility / max(
            self.summary["expense"].mean(), 1
        )
        score -= min(20, vol_ratio * 50)
        return round(min(95, max(30, score)), 1)

    def _next_month_label(self) -> str:
        last_month = self.summary.index[-1]
        # Period arithmetic
        try:
            next_p = last_month + 1
            return str(next_p)
        except Exception:
            return "Next Month"

    def _fallback_prediction(self) -> SpendingPrediction:
        """Absolute fallback — single data point or empty."""
        if self.summary.empty:
            val = 0.0
        else:
            val = float(self.summary["expense"].iloc[-1])

        return SpendingPrediction(
            predicted_amount=val,
            lower_bound=val * 0.85,
            upper_bound=val * 1.15,
            confidence_pct=30.0,
            method_used="fallback",
            prediction_month=self._next_month_label(),
            feature_importances={},
        )


# ─────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ─────────────────────────────────────────────

def predict_next_month(features) -> SpendingPrediction:
    """
    One-liner.

    from prediction_engine import predict_next_month
    pred = predict_next_month(features)
    pred.display()
    """
    return PredictionEngine(features).predict()


# ─────────────────────────────────────────────
# DEBUG RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))

    from data_loader import load_transactions_pro
    from expense_classifier import classify_expenses
    from feature_engineer import engineer_features

    JSON_PATH = "../bank_data_encrypted.json"

    full_df    = load_transactions_pro(JSON_PATH)
    expense_df = classify_expenses(JSON_PATH)
    features   = engineer_features(expense_df, full_df)

    pred = predict_next_month(features)
    pred.display()