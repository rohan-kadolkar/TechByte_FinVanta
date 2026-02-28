"""
savings_engine.py
────────────────────────────────────────────────────────────────
Identifies savings opportunities and generates human-readable
behavioral alerts.

3 Signal Types
──────────────
1. Category Spike    → "Dining is 2.3x your 3-month average"
2. Subscription Leak → recurring charges you might have forgotten
3. Small Spend Drain → frequent small txns that add up silently

Input  : FinancialFeatures + expense_df
Output : SavingsReport dataclass with actionable alerts
────────────────────────────────────────────────────────────────
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ─────────────────────────────────────────────
# ALERT SCHEMA
# ─────────────────────────────────────────────

@dataclass
class SavingsAlert:
    alert_type: str        # "category_spike" | "subscription_leak" | "small_spend_drain"
    severity: str          # "high" | "medium" | "low"
    title: str             # Short headline
    detail: str            # Explanation sentence
    potential_saving: float  # Estimated monthly ₹ saving
    category: Optional[str] = None
    merchant: Optional[str] = None

    def __str__(self):
        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(self.severity, "⚪")
        saving = f"  💡 Potential saving: ₹{self.potential_saving:,.0f}/month" if self.potential_saving > 0 else ""
        return f"{icon} [{self.alert_type}]  {self.title}\n   {self.detail}{saving}"


@dataclass
class SavingsReport:
    alerts: List[SavingsAlert] = field(default_factory=list)
    total_potential_saving: float = 0.0
    financial_health_score: float = 0.0   # 0–100
    health_breakdown: Dict = field(default_factory=dict)

    def display(self):
        print(f"\n{'━'*55}")
        print(f"  💰  Savings Opportunity Report")
        print(f"{'━'*55}")
        print(f"  Financial Health Score : {self.financial_health_score:.0f} / 100")
        self._print_health_bar()
        print()

        if not self.alerts:
            print("  ✅  No savings leaks detected. You're doing great!")
        else:
            print(f"  Found {len(self.alerts)} opportunity(ies)  |  "
                  f"Total potential saving: ₹{self.total_potential_saving:,.0f}/month\n")
            for alert in sorted(
                self.alerts,
                key=lambda a: {"high": 0, "medium": 1, "low": 2}[a.severity]
            ):
                print(f"  {alert}\n")

        print(f"\n  Health Breakdown:")
        for factor, score in self.health_breakdown.items():
            bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
            print(f"    {factor:<22} [{bar}] {score:.0f}/100")
        print(f"{'━'*55}")

    def _print_health_bar(self):
        s   = int(self.financial_health_score)
        bar = "█" * (s // 5) + "░" * (20 - s // 5)
        print(f"  [{bar}] {s}/100")


# ─────────────────────────────────────────────
# SAVINGS ENGINE
# ─────────────────────────────────────────────

class SavingsEngine:
    """
    Usage
    ─────
    from savings_engine import SavingsEngine

    engine = SavingsEngine(features, expense_df)
    report = engine.analyze()
    report.display()
    """

    # Tuning knobs
    SPIKE_MULTIPLIER   = 1.5   # X times 3-month avg → spike alert
    SMALL_TXN_LIMIT    = 200   # ₹ — what counts as "small"
    SMALL_TXN_FREQ     = 5     # ≥ this many per month → drain alert
    SUB_MONTHLY_THRESH = 2     # recurring in ≥ this many months → subscription

    def __init__(self, features, expense_df: pd.DataFrame):
        self.features   = features
        self.expense_df = expense_df.copy()
        self.alerts: List[SavingsAlert] = []

    # ─────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────

    def analyze(self) -> SavingsReport:
        self.alerts = []

        self._detect_category_spikes()
        self._detect_subscription_leaks()
        self._detect_small_spend_drains()

        total_saving = sum(a.potential_saving for a in self.alerts)
        health_score, breakdown = self._compute_health_score()

        return SavingsReport(
            alerts=self.alerts,
            total_potential_saving=round(total_saving, 2),
            financial_health_score=round(health_score, 1),
            health_breakdown=breakdown,
        )

    # ─────────────────────────────────────────
    # SIGNAL 1 — CATEGORY SPIKE
    # ─────────────────────────────────────────

    def _detect_category_spikes(self):
        cat_monthly = self.features.category_monthly
        if cat_monthly.empty or len(cat_monthly) < 2:
            return

        # 3-month rolling baseline (or all available if < 3)
        window = min(3, len(cat_monthly) - 1)
        baseline = cat_monthly.iloc[:-1].tail(window).mean()
        last_month = cat_monthly.iloc[-1]

        for cat in cat_monthly.columns:
            base_val = baseline.get(cat, 0)
            curr_val = last_month.get(cat, 0)

            if base_val < 100:  # ignore tiny categories
                continue

            ratio = curr_val / base_val if base_val > 0 else 0

            if ratio >= self.SPIKE_MULTIPLIER:
                excess = curr_val - base_val
                severity = "high" if ratio >= 2.5 else "medium"
                self.alerts.append(SavingsAlert(
                    alert_type="category_spike",
                    severity=severity,
                    category=cat,
                    title=f"{cat} spending spiked {ratio:.1f}x",
                    detail=(
                        f"You spent ₹{curr_val:,.0f} on {cat} last month — "
                        f"{ratio:.1f}x your {window}-month average of ₹{base_val:,.0f}."
                    ),
                    potential_saving=round(excess * 0.5, 2),  # conservative: halve the excess
                ))

    # ─────────────────────────────────────────
    # SIGNAL 2 — SUBSCRIPTION LEAK
    # ─────────────────────────────────────────

    def _detect_subscription_leaks(self):
        recurring = self.features.recurring
        if recurring.empty:
            return

        for _, row in recurring.iterrows():
            merchant    = row["merchant"]
            avg_amount  = row["avg_amount"]
            months_seen = row["months_seen"]
            total_spent = row["total_spent"]

            if avg_amount < 50:   # skip trivial amounts
                continue

            # Severity: the more months seen + higher amount → more severe
            if avg_amount > 500 and months_seen >= 3:
                severity = "high"
            elif avg_amount > 200 or months_seen >= 4:
                severity = "medium"
            else:
                severity = "low"

            self.alerts.append(SavingsAlert(
                alert_type="subscription_leak",
                severity=severity,
                merchant=merchant,
                title=f"Recurring charge: {merchant}",
                detail=(
                    f"₹{avg_amount:,.0f}/month to '{merchant}' "
                    f"detected across {months_seen} months "
                    f"(₹{total_spent:,.0f} total). "
                    f"Review if still needed."
                ),
                potential_saving=round(avg_amount, 2),
            ))

    # ─────────────────────────────────────────
    # SIGNAL 3 — SMALL SPEND DRAIN
    # ─────────────────────────────────────────

    def _detect_small_spend_drains(self):
        df = self.expense_df.copy()

        if "month" not in df.columns:
            df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")

        small = df[df["amount"] <= self.SMALL_TXN_LIMIT]

        if small.empty:
            return

        # Count small transactions per month
        monthly_count = small.groupby("month").size()
        monthly_spend = small.groupby("month")["amount"].sum()

        high_freq_months = monthly_count[monthly_count >= self.SMALL_TXN_FREQ]

        if high_freq_months.empty:
            return

        avg_small_spend = float(monthly_spend.mean())
        avg_count       = float(monthly_count.mean())

        self.alerts.append(SavingsAlert(
            alert_type="small_spend_drain",
            severity="medium" if avg_small_spend > 1000 else "low",
            title=f"Frequent small transactions draining wallet",
            detail=(
                f"You average {avg_count:.0f} small transactions (≤₹{self.SMALL_TXN_LIMIT}) "
                f"per month, totalling ₹{avg_small_spend:,.0f}/month. "
                f"These micro-spends often go unnoticed."
            ),
            potential_saving=round(avg_small_spend * 0.25, 2),  # assume 25% reducible
        ))

    # ─────────────────────────────────────────
    # FINANCIAL HEALTH SCORE  (0–100)
    # ─────────────────────────────────────────

    def _compute_health_score(self):
        """
        Weighted scoring across 4 factors.
        Score = 0 (critical) → 100 (excellent)
        """
        summary = self.features.monthly_summary
        breakdown = {}

        # 1. Savings Rate (30 pts)
        avg_savings_rate = float(summary["savings_rate"].mean()) if not summary.empty else 0
        savings_score = min(100, max(0, avg_savings_rate * 200))  # 50% rate = 100 pts
        breakdown["Savings Rate"] = round(savings_score, 1)

        # 2. Cashflow Consistency (25 pts)
        neg_months = len(self.features.negative_cashflow_months)
        total_months = max(len(summary), 1)
        neg_ratio = neg_months / total_months
        cashflow_score = max(0, 100 - neg_ratio * 200)
        breakdown["Cashflow Consistency"] = round(cashflow_score, 1)

        # 3. Expense Stability (25 pts)
        # Low volatility relative to mean = stable
        mean_exp = float(summary["expense"].mean()) if not summary.empty else 1
        vol_ratio = self.features.expense_volatility / max(mean_exp, 1)
        stability_score = max(0, 100 - vol_ratio * 150)
        breakdown["Expense Stability"] = round(stability_score, 1)

        # 4. Spending Trend (20 pts)
        slope = self.features.expense_slope
        # Positive slope (rising spend) is bad; negative is good
        trend_score = max(0, min(100, 70 - slope / max(mean_exp, 1) * 1000))
        breakdown["Spending Trend"] = round(trend_score, 1)

        # Weighted composite
        weights = {
            "Savings Rate":          0.30,
            "Cashflow Consistency":  0.25,
            "Expense Stability":     0.25,
            "Spending Trend":        0.20,
        }
        total_score = sum(breakdown[k] * w for k, w in weights.items())

        # Penalize for high-severity alerts
        high_alerts = sum(1 for a in self.alerts if a.severity == "high")
        total_score = max(0, total_score - high_alerts * 5)

        return total_score, breakdown


# ─────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ─────────────────────────────────────────────

def analyze_savings(features, expense_df: pd.DataFrame) -> SavingsReport:
    """
    One-liner.

    from savings_engine import analyze_savings
    report = analyze_savings(features, expense_df)
    report.display()
    """
    return SavingsEngine(features, expense_df).analyze()


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

    report = analyze_savings(features, expense_df)
    report.display()