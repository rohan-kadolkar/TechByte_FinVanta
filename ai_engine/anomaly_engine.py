"""
anomaly_engine.py
────────────────────────────────────────────────────────────────
Detects unusual transactions using a 3-layer approach:

Layer 1 — Amount anomaly   : IQR + Z-score on per-category spend
Layer 2 — Merchant anomaly : new/rare merchant not seen before
Layer 3 — Time anomaly     : transaction at unusual hour/day

Each transaction gets an anomaly_score (0–1) and a list of reasons.
Score ≥ threshold → flagged as anomalous.

Frontend-aware output (NEW)
──────────────────────────
AnomalyReport.frontend_records → List[Dict], one dict per flagged txn.
Each dict contains:
  txn_id       : str   — links back to data_loader txnId (or generated ID)
  date         : str   — ISO date string
  amount       : float
  category     : str
  clean_merchant: str  — human-readable merchant name
  anomaly_score: float
  severity     : str   — "low" | "medium" | "high"  (based on × mean spend)
  insight_text : str   — one sentence for Jinja2 templates / dashboard cards
  anomaly_reasons: str — full technical reason string (unchanged)

Jinja2 usage example:
  {% for row in report.frontend_records %}
    <tr class="severity-{{ row.severity }}">
      <td>{{ row.date }}</td>
      <td>{{ row.clean_merchant }}</td>
      <td>₹{{ row.amount | int }}</td>
      <td>{{ row.insight_text }}</td>
      <td><span class="badge {{ row.severity }}">{{ row.severity }}</span></td>
    </tr>
  {% endfor %}

Input  : expense_df (from expense_classifier) + FinancialFeatures
Output : AnomalyReport dataclass
────────────────────────────────────────────────────────────────
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict


# ─────────────────────────────────────────────
# OUTPUT SCHEMA
# ─────────────────────────────────────────────

@dataclass
class AnomalyReport:
    flagged_transactions: pd.DataFrame   # rows with anomaly_score ≥ threshold
    all_transactions: pd.DataFrame       # full df with scores attached
    summary: Dict                        # quick stats
    threshold_used: float
    # NEW — frontend-ready list of dicts, one per flagged transaction
    frontend_records: List[Dict] = field(default_factory=list)

    def display(self):
        n_flagged = len(self.flagged_transactions)
        total     = len(self.all_transactions)
        print(f"\n{'━'*50}")
        print(f"  🚨  Anomaly Detection Report")
        print(f"{'━'*50}")
        print(f"  Total transactions scanned : {total}")
        print(f"  Flagged as anomalous       : {n_flagged}")
        print(f"  Detection threshold        : {self.threshold_used}")
        print()

        if n_flagged == 0:
            print("  ✅  No anomalies detected.")
        else:
            cols = ["date", "amount", "predicted_category", "merchant",
                    "anomaly_score", "anomaly_reasons"]
            show = [c for c in cols if c in self.flagged_transactions.columns]
            print(self.flagged_transactions[show].to_string(index=False))

        print(f"\n  Category Breakdown:")
        for cat, cnt in self.summary.get("by_category", {}).items():
            print(f"    • {cat:<25} {cnt} flagged")

        # NEW — print frontend records if present
        if self.frontend_records:
            print(f"\n  Frontend Records ({len(self.frontend_records)} flagged):")
            sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            for rec in self.frontend_records:
                icon = sev_icon.get(rec["severity"], "⚪")
                print(f"    {icon} [{rec['severity'].upper():<6}] "
                      f"txn_id={rec['txn_id']:<8}  "
                      f"₹{rec['amount']:>9,.0f}  "
                      f"{rec['clean_merchant']:<22}  "
                      f"{rec['insight_text']}")
        print(f"{'━'*50}")


# ─────────────────────────────────────────────
# ANOMALY ENGINE
# ─────────────────────────────────────────────

class AnomalyEngine:
    """
    Usage
    ─────
    from anomaly_engine import AnomalyEngine

    engine = AnomalyEngine(expense_df, features)
    report = engine.detect()
    report.display()
    """

    def __init__(
        self,
        expense_df: pd.DataFrame,
        features,                          # FinancialFeatures
        threshold: float = 0.5,            # flag if anomaly_score ≥ this
        z_score_cutoff: float = 2.5,       # z-score for amount anomaly
        rare_merchant_min_seen: int = 2,   # seen < this → "rare merchant"
        unusual_hour_range: tuple = (6, 23), # outside this window → unusual
    ):
        self.df        = expense_df.copy()
        self.features  = features
        self.threshold = threshold
        self.z_cut     = z_score_cutoff
        self.rare_min  = rare_merchant_min_seen
        self.hour_min, self.hour_max = unusual_hour_range

        # Pre-compute baselines
        self._merchant_freq   = self._compute_merchant_freq()
        self._category_stats  = self._compute_category_stats()
        # NEW — global mean spend across all expense rows (for severity thresholds)
        self._global_mean_spend = self._compute_global_mean()

    # ─────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────

    def detect(self) -> AnomalyReport:
        df = self.df.copy()

        # Ensure time features
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        if "hour" not in df.columns:
            df["hour"] = df["date"].dt.hour
        if "weekday" not in df.columns:
            df["weekday"] = df["date"].dt.day_name()

        # ── Score each layer ─────────────────
        df["score_amount"]   = df.apply(self._score_amount, axis=1)
        df["score_merchant"] = df.apply(self._score_merchant, axis=1)
        df["score_time"]     = df.apply(self._score_time, axis=1)

        # ── Composite score ──────────────────
        # Weighted: amount matters most
        df["anomaly_score"] = (
            0.55 * df["score_amount"] +
            0.25 * df["score_merchant"] +
            0.20 * df["score_time"]
        ).round(3)

        # ── Human-readable reasons ───────────
        df["anomaly_reasons"] = df.apply(self._build_reasons, axis=1)

        # ── Flag anomalies ───────────────────
        flagged = df[df["anomaly_score"] >= self.threshold].copy()
        flagged = flagged.sort_values("anomaly_score", ascending=False)

        summary          = self._build_summary(flagged)
        # NEW — serialise flagged rows into frontend-ready dicts
        frontend_records = self._build_frontend_records(flagged)

        return AnomalyReport(
            flagged_transactions=flagged.reset_index(drop=True),
            all_transactions=df.reset_index(drop=True),
            summary=summary,
            threshold_used=self.threshold,
            frontend_records=frontend_records,
        )

    # ─────────────────────────────────────────
    # LAYER 1 — AMOUNT ANOMALY
    # ─────────────────────────────────────────

    def _compute_category_stats(self) -> Dict:
        """Per-category mean and std for amount."""
        stats = {}
        if "predicted_category" not in self.df.columns:
            return stats
        for cat, grp in self.df.groupby("predicted_category"):
            amounts = grp["amount"].values
            stats[cat] = {
                "mean": float(np.mean(amounts)),
                "std":  float(np.std(amounts)) if len(amounts) > 1 else 0.0,
                "q1":   float(np.percentile(amounts, 25)),
                "q3":   float(np.percentile(amounts, 75)),
            }
        return stats

    def _score_amount(self, row) -> float:
        cat    = row.get("predicted_category", "Others")
        amount = row.get("amount", 0)
        stats  = self._category_stats.get(cat)

        if not stats:
            return 0.0

        # IQR method
        iqr    = stats["q3"] - stats["q1"]
        iqr_upper = stats["q3"] + 1.5 * iqr
        iqr_flag  = amount > iqr_upper

        # Z-score method
        std = stats["std"] if stats["std"] > 0 else 1.0
        z   = (amount - stats["mean"]) / std
        z_flag = z > self.z_cut

        if z_flag and iqr_flag:
            return min(1.0, 0.6 + (z - self.z_cut) * 0.1)
        elif z_flag or iqr_flag:
            return 0.5
        elif z > 1.5:
            return 0.3
        return 0.0

    # ─────────────────────────────────────────
    # LAYER 2 — MERCHANT ANOMALY
    # ─────────────────────────────────────────

    def _compute_merchant_freq(self) -> Dict[str, int]:
        if "merchant" not in self.df.columns:
            return {}
        return self.df["merchant"].value_counts().to_dict()

    def _score_merchant(self, row) -> float:
        merchant = row.get("merchant", "Unknown")

        if merchant in ("Unknown", "", None):
            return 0.2   # slightly suspicious but not definitive

        freq = self._merchant_freq.get(merchant, 0)

        if freq == 1:    # first-ever transaction with this merchant
            return 0.6
        elif freq < self.rare_min:
            return 0.3
        return 0.0

    # ─────────────────────────────────────────
    # LAYER 3 — TIME ANOMALY
    # ─────────────────────────────────────────

    def _score_time(self, row) -> float:
        hour = row.get("hour")
        if pd.isna(hour):
            return 0.0

        hour = int(hour)
        # Outside normal operating hours
        if hour < self.hour_min or hour > self.hour_max:
            # Deep night (midnight–5am) → more suspicious
            if hour < 5 or hour == 23:
                return 0.7
            return 0.4
        return 0.0

    # ─────────────────────────────────────────
    # HUMAN-READABLE REASONS
    # ─────────────────────────────────────────

    def _build_reasons(self, row) -> str:
        reasons = []

        if row["score_amount"] >= 0.5:
            cat   = row.get("predicted_category", "category")
            stats = self._category_stats.get(cat, {})
            mean  = stats.get("mean", 0)
            reasons.append(
                f"Amount ₹{row['amount']:,.0f} is unusually high "
                f"for {cat} (avg ₹{mean:,.0f})"
            )

        if row["score_merchant"] >= 0.5:
            reasons.append(
                f"First-time merchant: '{row.get('merchant', 'Unknown')}'"
            )

        if row["score_time"] >= 0.4:
            reasons.append(
                f"Transaction at unusual hour: {int(row.get('hour', 0))}:00"
            )

        return " | ".join(reasons) if reasons else "Borderline anomaly"

    # ─────────────────────────────────────────
    # NEW — FRONTEND-AWARE LAYER
    # These three methods do NOT touch the ML
    # detection logic above. They purely format
    # the already-flagged rows for Rohan's UI.
    # ─────────────────────────────────────────

    def _compute_global_mean(self) -> float:
        """
        Single mean spend across ALL expense rows.
        Used as the baseline for severity thresholds:
          low    → amount < 2× global mean
          medium → 2× ≤ amount < 4× global mean
          high   → amount ≥ 4× global mean
        Kept separate from per-category stats so the
        ML scoring logic (which uses category stats)
        is not coupled to severity bucketing.
        """
        if self.df.empty or "amount" not in self.df.columns:
            return 1.0
        return float(self.df["amount"].mean()) or 1.0

    def _assign_severity(self, amount: float) -> str:
        """
        Buckets a transaction amount into low / medium / high
        relative to the user's own mean spend.

        Thresholds (tunable):
          high   : amount ≥ 4× global mean   → genuinely alarming
          medium : amount ≥ 2× global mean   → worth investigating
          low    : everything else            → mild anomaly
        """
        mean = self._global_mean_spend
        if amount >= 4 * mean:
            return "high"
        elif amount >= 2 * mean:
            return "medium"
        return "low"

    def _build_insight_text(self, row: pd.Series) -> str:
        """
        Generates a single, human-readable sentence for each flagged
        transaction. Prefers clean_merchant (from updated data_loader)
        over raw merchant. Designed to drop directly into a Jinja2
        template or a dashboard card without further formatting.

        Pattern:
          [trigger phrase] at [Merchant] on [Day, Date] — [context]
        """
        # Prefer clean_merchant (set by updated data_loader), fall back to merchant
        merchant = (
            row.get("clean_merchant")
            or row.get("merchant")
            or "an unknown merchant"
        )
        if not merchant or merchant in ("Unknown", ""):
            merchant = "an unknown merchant"

        amount   = row.get("amount", 0)
        category = row.get("predicted_category", "Others")
        severity = row.get("severity", "low")
        hour     = row.get("hour")

        # Choose opening phrase based on the dominant signal
        score_amount   = row.get("score_amount",   0)
        score_merchant = row.get("score_merchant", 0)
        score_time     = row.get("score_time",     0)

        # Build the core sentence
        if score_amount >= 0.5:
            stats = self._category_stats.get(category, {})
            avg   = stats.get("mean", 0)
            text  = (
                f"Unusually high {category} spend of ₹{amount:,.0f} at {merchant}"
                f" — your average is ₹{avg:,.0f}"
            )
        elif score_merchant >= 0.5:
            text = f"First-time transaction at {merchant} for ₹{amount:,.0f}"
        elif score_time >= 0.4 and hour is not None:
            text = (
                f"₹{amount:,.0f} spent at {merchant}"
                f" at an unusual hour ({int(hour):02d}:00)"
            )
        else:
            text = f"Borderline anomaly: ₹{amount:,.0f} at {merchant}"

        # Append severity context for high-severity items
        if severity == "high":
            text += " — flagged as HIGH risk"

        return text

    def _build_frontend_records(self, flagged: pd.DataFrame) -> List[Dict]:
        """
        Converts the flagged DataFrame into a list of flat dicts.
        Each dict is safe to pass directly to:
          - A Jinja2 template  ({{ row.insight_text }}, {{ row.severity }})
          - A JSON API response (json.dumps ready, no pandas types)
          - app.py's /api/analyze route

        Keys guaranteed on every dict:
          txn_id, date, amount, category, clean_merchant,
          anomaly_score, severity, insight_text, anomaly_reasons
        """
        if flagged.empty:
            return []

        records: List[Dict] = []
        for _, row in flagged.iterrows():
            severity = self._assign_severity(float(row.get("amount", 0)))

            # Attach severity back onto row so _build_insight_text can use it
            row = row.copy()
            row["severity"] = severity

            # Resolve txn_id: use txnId column (new data_loader) or fall back
            txn_id = (
                str(row.get("txnId", ""))
                or str(row.get("txn_id", ""))
                or str(row.get("id",    ""))
                or f"TXN-{_}"        # absolute last resort
            )

            records.append({
                # ── Linkage ─────────────────────────────
                "txn_id":         txn_id,
                # ── Core transaction fields ──────────────
                "date":           str(row.get("date", ""))[:10],   # YYYY-MM-DD only
                "amount":         float(row.get("amount", 0)),
                "category":       str(row.get("predicted_category", "Others")),
                "clean_merchant": str(row.get("clean_merchant") or row.get("merchant") or "Unknown"),
                "mode":           str(row.get("mode", "")),
                "account":        str(row.get("account", "")),
                # ── Detection output ─────────────────────
                "anomaly_score":  float(row.get("anomaly_score", 0)),
                "anomaly_reasons": str(row.get("anomaly_reasons", "")),
                # ── NEW frontend fields ──────────────────
                "severity":       severity,
                "insight_text":   self._build_insight_text(row),
            })

        return records

    # ─────────────────────────────────────────
    # SUMMARY STATS
    # ─────────────────────────────────────────

    def _build_summary(self, flagged: pd.DataFrame) -> Dict:
        summary: Dict = {"total_flagged": len(flagged)}

        if flagged.empty:
            summary["by_category"] = {}
            summary["total_anomalous_spend"] = 0.0
            return summary

        if "predicted_category" in flagged.columns:
            summary["by_category"] = flagged["predicted_category"].value_counts().to_dict()

        summary["total_anomalous_spend"] = float(flagged["amount"].sum())
        summary["highest_anomaly_score"] = float(flagged["anomaly_score"].max())
        summary["avg_anomalous_amount"]  = float(flagged["amount"].mean())

        return summary


# ─────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ─────────────────────────────────────────────

def detect_anomalies(expense_df: pd.DataFrame, features, **kwargs) -> AnomalyReport:
    """
    One-liner.

    from anomaly_engine import detect_anomalies
    report = detect_anomalies(expense_df, features)
    report.display()
    """
    return AnomalyEngine(expense_df, features, **kwargs).detect()


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

    report = detect_anomalies(expense_df, features)
    report.display()