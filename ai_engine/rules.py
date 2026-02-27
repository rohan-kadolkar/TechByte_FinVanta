import re

# -----------------------------
# CATEGORY RULE DEFINITIONS
# -----------------------------
CATEGORY_PATTERNS = {
    "Food & Dining": re.compile(r"swiggy|zomato|restaurant|cafe|eat", re.I),
    "Shopping": re.compile(r"amazon|flipkart|myntra|blinkit", re.I),
    "Transport": re.compile(r"uber|ola|petrol|fuel|irctc", re.I),
    "Utilities": re.compile(r"electricity|water|gas|broadband|recharge|bill", re.I),
}

# -----------------------------
# MERCHANT EXTRACTION
# Works for AA narration format
# -----------------------------
def extract_merchant(narration):
    if not narration:
        return "Unknown"

    parts = narration.split("/")

    # Many AA narrations follow:
    # UPI/DE/.../MerchantName/XXXX
    if len(parts) >= 4:
        return parts[3].strip()

    return narration[:20]  # fallback


# -----------------------------
# RULE-BASED CLASSIFICATION
# -----------------------------
def categorize_transaction(narration):
    if not narration:
        return "Others", 0.0, "Unknown"

    merchant = extract_merchant(narration)

    for category, pattern in CATEGORY_PATTERNS.items():
        if pattern.search(narration):
            return category, 0.9, merchant

    # fallback case (low confidence)
    return "Others", 0.4, merchant
