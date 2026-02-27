from data_loader import load_transactions_pro
from rules import categorize_transaction
import pandas as pd


def classify_expenses(json_path):

    # ---------------------------------
    # 1. LOAD TRANSACTIONS
    # ---------------------------------
    df = load_transactions_pro(json_path)

    if df.empty:
        print("No transactions found.")
        return df

    # ---------------------------------
    # 2. KEEP ONLY EXPENSES (DEBIT)
    # ---------------------------------
    df = df[df["type"] == "DEBIT"].copy()

    if df.empty:
        print("No debit transactions to analyze.")
        return df

    # ---------------------------------
    # 3. HANDLE MISSING NARRATIONS
    # ---------------------------------
    df["narration"] = df["narration"].fillna("")

    # ---------------------------------
    # 4. APPLY RULE ENGINE
    # ---------------------------------
    results = df["narration"].apply(
        lambda x: pd.Series(categorize_transaction(x))
    )

    results.columns = ["predicted_category", "confidence", "merchant"]

    df = pd.concat([df, results], axis=1)

    # ---------------------------------
    # 5. SAFETY → Ensure valid datetime before feature creation
    # ---------------------------------
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    # ---------------------------------
    # 6. FEATURE ENGINEERING (Needed Later)
    # ---------------------------------
    df["month"] = df["date"].dt.to_period("M")
    df["weekday"] = df["date"].dt.day_name()
    df["hour"] = df["date"].dt.hour

    return df


# ---------------------------------
# DEBUG RUN
# ---------------------------------
if __name__ == "__main__":

    result = classify_expenses("../bank_data_encrypted.json")

    print("\n--- Sample Classified Expenses ---")
    print(result[[
        "date",
        "amount",
        "predicted_category",
        "merchant",
        "confidence"
    ]].head()) #isko zara dekhna yah aprint nahi hoga isko json mea update karna h

    print("\n--- Category Summary ---")
    print(result["predicted_category"].value_counts())
