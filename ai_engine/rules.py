import re

# -----------------------------
# CATEGORY RULE DEFINITIONS (Exact Matches)
# -----------------------------
CATEGORY_PATTERNS = {
    "Food & Dining": re.compile(r"swiggy|zomato|restaurant|cafe|eat|mcdonald|starbucks", re.I),
    "Shopping": re.compile(r"amazon|flipkart|myntra|blinkit|zepto|dmart|shopping", re.I),
    "Transport": re.compile(r"uber|ola|petrol|fuel|irctc|rapido|makemytrip", re.I),
    "Utilities": re.compile(r"electricity|water|gas|broadband|recharge|bill|jio|airtel", re.I),
    "Housing & Rent": re.compile(r"rent|broker|deposit|maintenance", re.I)
}

# -----------------------------
# MERCHANT EXTRACTION
# -----------------------------
def extract_merchant(narration):
    if not narration:
        return "Unknown"

    parts = narration.split("/")

    # If AA format: UPI/DE/.../MerchantName/XXXX
    if len(parts) >= 4 and len(parts[3]) > 2:
        return parts[3].strip()

    return narration[:20]  # fallback


# -----------------------------
# RULE-BASED + HEURISTIC CLASSIFICATION
# -----------------------------
def categorize_transaction(narration, amount=0.0):
    """Now takes amount into consideration for smart guessing!"""
    if not narration:
        return "Others", 0.0, "Unknown"

    merchant = extract_merchant(narration)
    narration_upper = narration.upper()

    # STEP 1: Try exact keyword matches first (High Confidence)
    for category, pattern in CATEGORY_PATTERNS.items():
        if pattern.search(narration):
            return category, 0.9, merchant

    # STEP 2: The Smart Heuristic (For generic Yono / AA Strings)
    
    # 2a. ATM Withdrawals
    if "ATM/DE" in narration_upper or "CASH/DE" in narration_upper:
        return "Others", 0.8, "ATM Withdrawal"
        
    # 2b. Large Bank Transfers (FT/NEFT/IMPS) -> Usually Rent or Big Bills
    if "FT/DE" in narration_upper or "NEFT" in narration_upper or "IMPS" in narration_upper:
        if amount > 10000:
            return "Housing & Rent", 0.6, merchant 
        elif amount > 3000:
            return "Utilities", 0.6, merchant
            
    # 2c. UPI Payments Guessed by Amount
    if "UPI" in narration_upper or "QR" in narration_upper:
        if amount < 500:
            return "Food & Dining", 0.6, merchant
        elif 500 <= amount <= 3000:
            return "Shopping", 0.6, merchant 
        else:
            return "Utilities", 0.6, merchant

    # STEP 3: If all else fails
    return "Others", 0.4, merchant