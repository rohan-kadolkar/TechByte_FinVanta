import json
import re
import os
import pandas as pd

# ─────────────────────────────────────────────────────────────
# HELPER 1 — Merchant Name Cleaner
# Turns raw narration merchants like 'ZOMATO_123_BLR' → 'Zomato'
# ─────────────────────────────────────────────────────────────
def _clean_merchant(raw: str) -> str:
    """
    Cleans a raw merchant/narration string into a human-readable name.

    Steps:
      1. Extract the merchant segment from AA narration format (UPI/DE/.../Merchant/XXXX)
      2. Strip trailing digits, underscores, city codes (3-letter all-caps), special chars
      3. Title-case the result

    Examples:
      'ZOMATO_123_BLR'       → 'Zomato'
      'SWIGGY_INSTAMART_MUM' → 'Swiggy Instamart'
      'NETFLIX.COM_9878'     → 'Netflix Com'
      'RentOwner_Sharma'     → 'Rentowner Sharma'
      'UPI/DE/123/Zomato/XX' → 'Zomato'
    """
    if not raw or not isinstance(raw, str):
        return "Unknown"

    name = raw.strip()

    # Extract merchant segment from AA narration format: UPI/DE/<ref>/<Merchant>/XXXX
    parts = name.split("/")
    if len(parts) >= 4:
        name = parts[3].strip()

    # Remove trailing reference numbers / transaction IDs (pure digit blocks)
    name = re.sub(r'\b\d+\b', '', name)

    # Remove trailing 3-letter all-caps city/branch codes (e.g. BLR, MUM, DEL, HYD)
    name = re.sub(r'\b[A-Z]{2,4}\b', lambda m: '' if m.group() == m.group().upper() else m.group(), name)

    # Replace underscores, dots, hyphens with spaces
    name = re.sub(r'[_.\-]+', ' ', name)

    # Remove leftover special characters
    name = re.sub(r'[^a-zA-Z0-9\s]', '', name)

    # Collapse multiple spaces
    name = re.sub(r'\s+', ' ', name).strip()

    # Title-case
    name = name.title() if name else "Unknown"

    return name if name else "Unknown"


# ─────────────────────────────────────────────────────────────
# HELPER 2 — Account Type Resolver
# ─────────────────────────────────────────────────────────────
def _resolve_acc_type(json_path: str, acc_info: dict) -> str:
    """
    Determines account type from:
      1. The 'type' or 'accType' field in the account data block
      2. The source file name (e.g. 'credit_card_data.json' → 'Credit Card')
      3. Falls back to 'Savings'
    """
    # Check account summary type field
    summary = acc_info.get("summary", {})
    acc_type_raw = (
        summary.get("type")
        or acc_info.get("accType")
        or acc_info.get("type")
        or "" #isko zara dekhna hai ki kahi transaction type na lele
    ).upper()

    if acc_type_raw in ("CREDIT", "CREDIT_CARD", "CC"):
        return "Credit Card"
    if acc_type_raw in ("SAVINGS", "SAVING", "SB"):
        return "Savings"
    if acc_type_raw in ("CURRENT", "CA"):
        return "Current"

    # Fallback: infer from file name
    fname = os.path.basename(json_path).lower()
    if any(k in fname for k in ("credit", "cc", "card")):
        return "Credit Card"
    if "current" in fname:
        return "Current"

    return "Savings"  # safe default


# ─────────────────────────────────────────────────────────────
# MAIN LOADER
# ─────────────────────────────────────────────────────────────
def load_transactions_pro(json_path):
    with open(json_path, "r") as f:
        raw = json.load(f)

    transactions_list = []
    txn_id_counter = 1001  # Auto-incrementing ID seed

    for fip in raw.get("fips", []):
        for acc in fip.get("accounts", []):
            # ✅ SAFETY GUARD: Check if 'data' exists before digging deeper
            data_block = acc.get("data")
            if not data_block:
                continue  # Skip this account if it's empty/null

            # Now safe to get account info
            acc_info = data_block.get("account", {})     
            acc_no   = acc_info.get("maskedAccNumber") 

            # ── NEW: resolve account type once per account ──
            acc_type = _resolve_acc_type(json_path, acc_info)

            # ✅ SAFETY GUARD: Check if 'transactions' block exists 
            txn_block = acc_info.get("transactions") 
            if not txn_block:
                continue

            transactions = txn_block.get("transaction") or []

            for txn in transactions:
                narration = txn.get("narration")

                # ── NEW: txnId — use source value or generate one ──
                txn_id = txn.get("txnId") or txn.get("id") or str(txn_id_counter)
                txn_id_counter += 1

                # ── NEW: clean_merchant derived from narration ──
                clean_merch = _clean_merchant(narration or "")

                transactions_list.append({
                    "account":        acc_no,
                    # ✅ FIX 1 → Prevent crash if date missing / invalid
                    "date":           pd.to_datetime(txn.get("valueDate"), errors="coerce"),
                    "amount":         float(txn.get("amount", 0)),
                    "type":           txn.get("type"),
                    "narration":      narration,
                    "mode":           txn.get("mode"),
                    "balance":        float(txn.get("currentBalance", 0)),
                    # ── NEW COLUMNS ──────────────────────────────
                    "txnId":          txn_id,
                    "clean_merchant": clean_merch,
                    "acc_type":       acc_type,
                })

    if not transactions_list:
        return pd.DataFrame()

    df = pd.DataFrame(transactions_list)

    # ✅ FIX 2 → Remove rows where AA sent bad timestamps
    df = df.dropna(subset=["date"])

    return df.sort_values(by="date")