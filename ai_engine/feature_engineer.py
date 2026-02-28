"""
feature_engineer.py
────────────────────────────────────────────────────────────────
Pure aggregation layer that converts transaction-level data into
financial intelligence signals.

Input  : classified expense DataFrame (output of expense_classifier.py)
Output : FinancialFeatures dataclass + monthly_summary DataFrame
────────────────────────────────────────────────────────────────
"""

import re
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ─────────────────────────────────────────────
# OUTPUT SCHEMA
# ─────────────────────────────────────────────

@dataclass
class FinancialFeatures:
    # ── Core monthly aggregates ──────────────
    monthly_income: pd.Series = field(default_factory=pd.Series)
    monthly_expense: pd.Series = field(default_factory=pd.Series)
    monthly_savings: pd.Series = field(default_factory=pd.Series)
    savings_rate: pd.Series = field(default_factory=pd.Series)          # savings / income

    # ── Category breakdown ───────────────────
    category_monthly: pd.DataFrame = field(default_factory=pd.DataFrame)  # pivot: month × category
    category_pct: pd.DataFrame = field(default_factory=pd.DataFrame)       # % of total spend

    # ── Trend & volatility ───────────────────
    expense_slope: float = 0.0          # ₹/month trend (+ means spending rising)
    expense_volatility: float = 0.0     # std-dev of monthly spend
    income_volatility: float = 0.0

    # ── Cash flow ────────────────────────────
    avg_monthly_cashflow: float = 0.0   # avg (income - expense)

    # ── Recurring transactions ───────────────
    recurring: pd.DataFrame = field(default_factory=pd.DataFrame)

    # ── Risk flags ───────────────────────────
    high_expense_months: List[str] = field(default_factory=list)
    negative_cashflow_months: List[str] = field(default_factory=list)

    # ── Raw monthly summary ──────────────────
    monthly_summary: pd.DataFrame = field(default_factory=pd.DataFrame)


# ─────────────────────────────────────────────
# MAIN ENGINEER CLASS
# ─────────────────────────────────────────────

class FeatureEngineer:
    """
    Usage
    ─────
    from feature_engineer import FeatureEngineer

    fe = FeatureEngineer(classified_df, full_df)
    features = fe.compute()
    print(features.monthly_summary)
    """

    def __init__(
        self,
        expense_df: pd.DataFrame,      # DEBIT rows with predicted_category (from expense_classifier)
        full_df: pd.DataFrame,         # ALL rows including CREDIT (from data_loader)
        recurrence_min_months: int = 2,  # how many months to call a txn "recurring"
        high_expense_z: float = 1.0,   # z-score threshold for high-expense flag
    ):
        self.expense_df = expense_df.copy()
        self.full_df = full_df.copy()
        self.recurrence_min_months = recurrence_min_months
        self.high_expense_z = high_expense_z

        # Ensure period columns exist
        for df in [self.expense_df, self.full_df]:
            if "month" not in df.columns:
                df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")

    # ─────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ─────────────────────────────────────────

    def compute(self) -> FinancialFeatures:
        features = FinancialFeatures()

        features.monthly_income  = self._monthly_income()
        features.monthly_expense = self._monthly_expense()
        features.monthly_savings = features.monthly_income - features.monthly_expense

        features.savings_rate = (
            features.monthly_savings / features.monthly_income.replace(0, np.nan)
        ).fillna(0).clip(-1, 1)

        features.category_monthly = self._category_monthly_pivot()
        features.category_pct     = self._category_pct(features.category_monthly, features.monthly_expense)

        features.expense_slope      = self._trend_slope(features.monthly_expense)
        features.expense_volatility = float(features.monthly_expense.std())
        features.income_volatility  = float(features.monthly_income.std())

        features.avg_monthly_cashflow = float(features.monthly_savings.mean())

        features.recurring = self._detect_recurring()

        features.high_expense_months     = self._flag_high_expense_months(features.monthly_expense)
        features.negative_cashflow_months = self._flag_negative_cashflow(features.monthly_savings)

        features.monthly_summary = self._build_summary(features)

        return features

    # ─────────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────────

    def _monthly_income(self) -> pd.Series:
        credits = self.full_df[self.full_df["type"] == "CREDIT"]
        return (
            credits.groupby("month")["amount"].sum()
            .rename("income")
        )

    def _monthly_expense(self) -> pd.Series:
        return (
            self.expense_df.groupby("month")["amount"].sum()
            .rename("expense")
        )

    def _category_monthly_pivot(self) -> pd.DataFrame:
        """Month × Category spend pivot table."""
        if "predicted_category" not in self.expense_df.columns:
            return pd.DataFrame()
        pivot = (
            self.expense_df
            .groupby(["month", "predicted_category"])["amount"]
            .sum()
            .unstack(fill_value=0)
        )
        return pivot

    def _category_pct(
        self,
        category_monthly: pd.DataFrame,
        monthly_expense: pd.Series
    ) -> pd.DataFrame:
        """Each category as % of total spend per month."""
        if category_monthly.empty:
            return pd.DataFrame()
        # Align index
        denom = monthly_expense.reindex(category_monthly.index).replace(0, np.nan)
        return category_monthly.div(denom, axis=0).fillna(0) * 100

    def _trend_slope(self, monthly_series: pd.Series) -> float:
        """
        Simple OLS slope: ₹ change per month.
        Positive → spending is rising.
        """
        if len(monthly_series) < 2:
            return 0.0
        y = monthly_series.values.astype(float)
        x = np.arange(len(y))
        slope = float(np.polyfit(x, y, 1)[0])
        return round(slope, 2)

    def _detect_recurring(self) -> pd.DataFrame:
        """
        Identify transactions that appear with similar merchant + amount
        across multiple months → likely subscriptions / EMIs.

        Strategy:
          Group by (merchant, amount_bucket) and count distinct months.
          amount_bucket = round to nearest 10 to tolerate tiny variations.
        """
        df = self.expense_df.copy()

        if "merchant" not in df.columns:
            return pd.DataFrame()

        df["amount_bucket"] = (df["amount"] / 10).round() * 10
        df["month_str"] = df["month"].astype(str)

        grouped = (
            df.groupby(["merchant", "amount_bucket"])
            .agg(
                months_seen=("month_str", "nunique"),
                total_spent=("amount", "sum"),
                avg_amount=("amount", "mean"),
                first_seen=("date", "min"),
                last_seen=("date", "max"),
            )
            .reset_index()
        )

        recurring = grouped[grouped["months_seen"] >= self.recurrence_min_months].copy()
        recurring = recurring.sort_values("total_spent", ascending=False)
        return recurring.reset_index(drop=True)

    def _flag_high_expense_months(self, monthly_expense: pd.Series) -> List[str]:
        """Months where spend is > mean + z*std."""
        if len(monthly_expense) < 3:
            return []
        threshold = monthly_expense.mean() + self.high_expense_z * monthly_expense.std()
        return [str(m) for m in monthly_expense[monthly_expense > threshold].index]

    def _flag_negative_cashflow(self, monthly_savings: pd.Series) -> List[str]:
        return [str(m) for m in monthly_savings[monthly_savings < 0].index]

    def _build_summary(self, f: FinancialFeatures) -> pd.DataFrame:
        """Single tidy DataFrame with key monthly KPIs — easy to pass to ML models."""
        all_months = sorted(
            set(f.monthly_income.index) | set(f.monthly_expense.index)
        )
        summary = pd.DataFrame(index=all_months)
        summary.index.name = "month"

        summary["income"]       = f.monthly_income.reindex(all_months, fill_value=0)
        summary["expense"]      = f.monthly_expense.reindex(all_months, fill_value=0)
        summary["savings"]      = f.monthly_savings.reindex(all_months, fill_value=0)
        summary["savings_rate"] = f.savings_rate.reindex(all_months, fill_value=0)

        # Tag risk flags
        summary["high_expense_flag"]      = summary.index.astype(str).isin(f.high_expense_months)
        summary["negative_cashflow_flag"] = summary.index.astype(str).isin(f.negative_cashflow_months)

        return summary


# ─────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ─────────────────────────────────────────────

def engineer_features(
    expense_df: pd.DataFrame,
    full_df: pd.DataFrame,
    **kwargs
) -> FinancialFeatures:
    """
    One-liner entry point.

    Example
    -------
    from expense_classifier import classify_expenses
    from data_loader import load_transactions_pro
    from feature_engineer import engineer_features

    full_df    = load_transactions_pro("bank_data.json")
    expense_df = classify_expenses("bank_data.json")
    features   = engineer_features(expense_df, full_df)

    print(features.monthly_summary)
    print(features.recurring)
    """
    return FeatureEngineer(expense_df, full_df, **kwargs).compute()


# ─────────────────────────────────────────────
# SHADOW CREDIT CARD FEATURE
# Standalone — does not touch FeatureEngineer
# or any existing function.
# ─────────────────────────────────────────────

# Keywords that reveal a hidden credit card payment hiding inside
# bank debit rows (e.g. "HDFC CC Bill Pay", "Card Pmt - ICICI")
_CC_PATTERNS = re.compile(
    r"\b(?:cc|credit\s*card|card\s*pmt|card\s*payment|bill\s*pay|creditcard|ccpay|card)\b",
    re.IGNORECASE,
)

# Synthetic transaction templates: (label, category, fraction_of_balance)
# Fractions intentionally don't sum to 1.0 — a small residual is left as
# "Miscellaneous" to make the split feel realistic rather than mechanical.
_SYNTH_TEMPLATES = [
    ("Online Shopping",  "Shopping",       0.35),
    ("Dining & Food",    "Food & Dining",  0.25),
    ("Fuel & Transport", "Transport",      0.20),
    ("Utilities / Bills","Utilities",      0.12),
]
_RESIDUAL_LABEL    = "Miscellaneous"
_RESIDUAL_CATEGORY = "Others"


def generate_shadow_credit_data(df: pd.DataFrame) -> dict:
    """
    Detects hidden credit card repayments inside a debit transaction
    DataFrame and reverse-engineers a plausible set of synthetic
    spend transactions that could explain the balance.

    Detection
    ─────────
    Scans two columns (whichever exist):
      • ``narration``     — raw AA narration string
      • ``clean_merchant``— human-readable merchant (from updated data_loader)
    Rows matching ``_CC_PATTERNS`` are treated as credit card bill payments.

    Inference
    ─────────
    • ``inferred_balance``  — sum of all detected CC payment amounts
    • ``estimated_limit``   — inferred_balance × 5  (conservative 20 % utilisation)
    • ``utilisation_pct``   — inferred_balance / estimated_limit × 100

    Synthetic Transactions
    ──────────────────────
    3–4 synthetic spend rows that sum to ``inferred_balance``, split across
    realistic categories (Shopping 35 %, Food 25 %, Transport 20 %,
    Utilities 12 %, Misc residual).  Each row is a plain dict so it can be
    passed directly to a Jinja2 template or a JSON API response.

    Parameters
    ──────────
    df : pd.DataFrame
        Any transaction DataFrame produced by ``load_transactions_pro``.
        Works with both the full_df (all rows) and expense_df (DEBIT only).

    Returns
    ───────
    dict with keys:
        detected          : bool   — True if at least one CC payment found
        detected_rows     : int    — number of CC payment rows found
        inferred_balance  : float  — total CC spend inferred (₹)
        estimated_limit   : float  — inferred_balance × 5  (₹)
        utilisation_pct   : float  — % of limit used
        synthetic_transactions : List[dict]
            Each dict: {label, category, amount, pct_of_balance, is_synthetic}

    Example
    ───────
    from feature_engineer import generate_shadow_credit_data

    full_df = load_transactions_pro("bank_data.json")
    shadow  = generate_shadow_credit_data(full_df)

    if shadow["detected"]:
        print(f"CC balance : ₹{shadow['inferred_balance']:,.0f}")
        print(f"Est. limit : ₹{shadow['estimated_limit']:,.0f}")
        for txn in shadow["synthetic_transactions"]:
            print(f"  {txn['label']:<22} ₹{txn['amount']:>9,.0f}  ({txn['pct_of_balance']:.0f}%)")
    """
    # ── Guard: empty input ────────────────────────────────────────────
    if df is None or df.empty:
        return _empty_shadow_result()

    # ── Step 1: Build a combined text column to scan ──────────────────
    # Use clean_merchant (new data_loader) when available; fall back to
    # narration; concatenate both so neither signal is lost.
    scan_parts = []
    if "clean_merchant" in df.columns:
        scan_parts.append(df["clean_merchant"].fillna("").astype(str))
    if "narration" in df.columns:
        scan_parts.append(df["narration"].fillna("").astype(str))

    if not scan_parts:
        return _empty_shadow_result()

    combined_text = scan_parts[0]
    for part in scan_parts[1:]:
        combined_text = combined_text + " " + part

    # ── Step 2: Flag CC payment rows ──────────────────────────────────
    cc_mask = combined_text.str.contains(_CC_PATTERNS, regex=True, na=False)
    cc_rows = df[cc_mask].copy()

    if cc_rows.empty:
        return _empty_shadow_result()

    # ── Step 3: Infer balance & limit ────────────────────────────────
    inferred_balance = float(cc_rows["amount"].sum())
    estimated_limit  = round(inferred_balance * 5, 2)
    utilisation_pct  = round((inferred_balance / estimated_limit) * 100, 1) if estimated_limit > 0 else 0.0

    # ── Step 4: Build synthetic transactions ─────────────────────────
    synthetic_txns: List[dict] = []
    allocated = 0.0

    for label, category, frac in _SYNTH_TEMPLATES:
        amt = round(inferred_balance * frac, 2)
        if amt <= 0:
            continue
        allocated += amt
        synthetic_txns.append({
            "label":           label,
            "category":        category,
            "amount":          amt,
            "pct_of_balance":  round(frac * 100, 1),
            "is_synthetic":    True,          # always flag so UI can style it
        })

    # Residual: whatever wasn't assigned to the four templates
    residual = round(inferred_balance - allocated, 2)
    if residual > 0:
        synthetic_txns.append({
            "label":          _RESIDUAL_LABEL,
            "category":       _RESIDUAL_CATEGORY,
            "amount":         residual,
            "pct_of_balance": round((residual / inferred_balance) * 100, 1),
            "is_synthetic":   True,
        })

    return {
        "detected":               True,
        "detected_rows":          int(cc_rows.shape[0]),
        "inferred_balance":       round(inferred_balance, 2),
        "estimated_limit":        estimated_limit,
        "utilisation_pct":        utilisation_pct,
        "synthetic_transactions": synthetic_txns,
    }


def _empty_shadow_result() -> dict:
    """Returns the standard 'no CC detected' shape so callers never need
    to check for missing keys regardless of whether CC data was found."""
    return {
        "detected":               False,
        "detected_rows":          0,
        "inferred_balance":       0.0,
        "estimated_limit":        0.0,
        "utilisation_pct":        0.0,
        "synthetic_transactions": [],
    }


# ─────────────────────────────────────────────
# DEBUG RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))

    from data_loader import load_transactions_pro
    from expense_classifier import classify_expenses

    # Locate a suitable JSON file to use for the debug run. The original
    # hard-coded path may not exist depending on where the repo is opened
    # from (IDE vs module run). Try a few sensible fallbacks relative to
    # this file and exit with a helpful message if none are found.
    candidates = [
        os.path.join(os.path.dirname(__file__), "../bank_data_encrypted.json"),
        os.path.join(os.path.dirname(__file__), "../../learnings/bank_data_encrypted.json"),
        os.path.join(os.path.dirname(__file__), "bank_data_synthetic.json"),
        os.path.join(os.path.dirname(__file__), "../bank_data_month.json"),
    ]

    JSON_PATH = None
    for p in candidates:
        p = os.path.normpath(p)
        if os.path.exists(p):
            JSON_PATH = p
            break

    if JSON_PATH is None:
        print("Error: no suitable JSON data file found for debug run.")
        print("Tried these locations:")
        for p in candidates:
            print("  ", os.path.normpath(p))
        sys.exit(1)

    full_df    = load_transactions_pro(JSON_PATH)
    expense_df = classify_expenses(JSON_PATH)

    features = engineer_features(expense_df, full_df)

    print("\n━━━ Monthly Summary ━━━")
    print(features.monthly_summary.to_string())

    print(f"\n━━━ Expense Trend ━━━")
    print(f"  Slope : ₹{features.expense_slope:+.0f}/month")
    print(f"  Volatility : ₹{features.expense_volatility:.0f}")

    print(f"\n━━━ Cash Flow ━━━")
    print(f"  Avg monthly cashflow : ₹{features.avg_monthly_cashflow:+.0f}")
    print(f"  Negative months      : {features.negative_cashflow_months}")
    print(f"  High-expense months  : {features.high_expense_months}")

    print("\n━━━ Category Breakdown (%) ━━━")
    print(features.category_pct.to_string())

    print("\n━━━ Recurring Transactions ━━━")
    print(features.recurring.head(10).to_string(index=False))

    # ── Shadow Credit Card ──────────────────────────────────────────────
    print("\n━━━ Shadow Credit Card Detection ━━━")
    shadow = generate_shadow_credit_data(full_df)
    if shadow["detected"]:
        print(f"  Detected CC payments  : {shadow['detected_rows']} rows")
        print(f"  Inferred balance      : ₹{shadow['inferred_balance']:,.0f}")
        print(f"  Estimated limit       : ₹{shadow['estimated_limit']:,.0f}")
        print(f"  Utilisation           : {shadow['utilisation_pct']}%")
        print(f"\n  Synthetic Transactions:")
        for t in shadow["synthetic_transactions"]:
            print(f"    {t['label']:<22}  ₹{t['amount']:>9,.0f}  ({t['pct_of_balance']}%)"
                  f"  [{t['category']}]")
    else:
        print("  No credit card payments detected in this dataset.")