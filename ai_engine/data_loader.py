import json
import os
import pandas as pd

def _clean_merchant(raw: str) -> str:
    # Keep your existing logic here if you want, but your new JSON
    # already has clean names like "Zomato" and "Netflix"!
    if not raw or not isinstance(raw, str):
        return "Unknown"
    return str(raw).strip()

# ─────────────────────────────────────────────────────────────
# MAIN LOADER (UPDATED FOR SIBLING JSON STRUCTURE)
# ─────────────────────────────────────────────────────────────
def load_transactions_pro(json_path):
    with open(json_path, "r") as f:
        raw = json.load(f)

    transactions_list = []
    
    # --- HELPER TO EXTRACT TRANSACTIONS ---
    def parse_and_append(txns, acc_type_label, default_acc_no="Unknown", balance=0):
        for txn in txns:
            txn_id = txn.get("txnId") or txn.get("id") or "UNKNOWN"
            
            # Handle negative amounts
            raw_amount = float(txn.get("amount", 0))
            abs_amount = abs(raw_amount)
            
            # Determine Credit/Debit (Treat BUY as Debit, SELL as Credit for investments)
            t_type = str(txn.get("type", "")).upper()
            if t_type in ["BUY", "DEBIT"] or raw_amount < 0:
                txn_type = "DEBIT"
            else:
                txn_type = "CREDIT"

            # Check for descriptions or narrations
            narration = txn.get("description") or txn.get("narration") or "Unknown"
            clean_merch = _clean_merchant(narration)
            
            # Check for different date keys
            date_str = txn.get("date") or txn.get("transactionDateTime")

            transactions_list.append({
                "account":        default_acc_no,
                "date":           pd.to_datetime(date_str, errors="coerce"),
                "amount":         abs_amount, 
                "type":           txn_type,
                "narration":      narration,
                "mode":           txn.get("category") or txn.get("mode") or "OTHER",
                "balance":        float(balance),
                "txnId":          txn_id,
                "clean_merchant": clean_merch,
                "acc_type":       acc_type_label,
            })

    # 1. PARSE BANK ACCOUNTS
    for acc in raw.get("bankAccounts", []):
        acc_type = "Savings" if acc.get("accountType") == "SAVINGS" else "Current"
        parse_and_append(acc.get("transactions", []), acc_type, acc.get("accountId"), acc.get("balance", 0))

    # 2. PARSE AMC ACCOUNT
    amc = raw.get("amcAccount")
    if amc:
        amc_data = amc.get("data", {}).get("account", {})
        amc_txns = amc_data.get("transactions", {}).get("transaction", [])
        parse_and_append(amc_txns, "Investment", amc_data.get("maskedAccNumber"))

    # 3. PARSE BROKERAGE ACCOUNT
    brok = raw.get("brokerageAccount")
    if brok:
        brok_data = brok.get("data", {}).get("account", {})
        brok_txns = brok_data.get("transactions", {}).get("transaction", [])
        parse_and_append(brok_txns, "Investment", brok_data.get("maskedAccNumber"))

    if not transactions_list:
        return pd.DataFrame()

    df = pd.DataFrame(transactions_list)
    df = df.dropna(subset=["date"])
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None)
    
    return df.sort_values(by="date")