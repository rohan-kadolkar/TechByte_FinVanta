import json
import random
import uuid
from datetime import datetime, timedelta

# ---------- CONFIG ----------
USERS = [
    {"user_id": "user_001", "name": "Aarav Sharma"},
    {"user_id": "user_002", "name": "Rohan Mehta"},
    {"user_id": "user_003", "name": "Neha Verma"},
    {"user_id": "user_004", "name": "Priya Kulkarni"},
]

MERCHANTS = [
    "Swiggy", "Zomato", "Amazon", "Flipkart",
    "Uber", "Ola", "BigBasket", "DMart",
    "Netflix", "Spotify", "CRED", "PhonePe",
    "Google Pay", "Electricity Bill", "Airtel Recharge",
    "LIC Premium", "Rent Payment", "SIP Investment"
]

CATEGORIES = {
    "Swiggy": "Food",
    "Zomato": "Food",
    "Amazon": "Shopping",
    "Flipkart": "Shopping",
    "Uber": "Travel",
    "Ola": "Travel",
    "BigBasket": "Groceries",
    "DMart": "Groceries",
    "Netflix": "Entertainment",
    "Spotify": "Entertainment",
    "CRED": "Credit Card Payment",
    "PhonePe": "UPI",
    "Google Pay": "UPI",
    "Electricity Bill": "Utilities",
    "Airtel Recharge": "Utilities",
    "LIC Premium": "Insurance",
    "Rent Payment": "Housing",
    "SIP Investment": "Investment"
}

# ---------- FUNCTIONS ----------

def random_date_within_6_months():
    start_date = datetime.now() - timedelta(days=180)
    random_days = random.randint(0, 180)
    return (start_date + timedelta(days=random_days)).strftime("%Y-%m-%d")

def generate_transactions(account_type):
    transactions = []

    for _ in range(random.randint(80, 120)):
        merchant = random.choice(MERCHANTS)
        amount = round(random.uniform(100, 8000), 2)

        if merchant == "SIP Investment":
            amount = round(random.uniform(2000, 10000), 2)

        transaction = {
            "txnId": str(uuid.uuid4()),
            "date": random_date_within_6_months(),
            "description": merchant,
            "category": CATEGORIES[merchant],
            "amount": -amount,
            "currency": "INR",
            "type": "DEBIT"
        }

        transactions.append(transaction)

    # Salary Credit
    transactions.append({
        "txnId": str(uuid.uuid4()),
        "date": random_date_within_6_months(),
        "description": "Salary Credit",
        "category": "Income",
        "amount": round(random.uniform(80000, 90000), 2),
        "currency": "INR",
        "type": "CREDIT"
    })

    # Suspicious Transaction
    transactions.append({
        "txnId": str(uuid.uuid4()),
        "date": random_date_within_6_months(),
        "description": "International POS - Unknown",
        "category": "Suspicious",
        "amount": -49999.99,
        "currency": "INR",
        "type": "DEBIT",
        "flagged": True
    })

    return sorted(transactions, key=lambda x: x["date"], reverse=True)

def generate_user_data(user):
    accounts = [
        {"accountType": "SAVINGS", "balance": round(random.uniform(20000, 150000), 2)},
        {"accountType": "CURRENT", "balance": round(random.uniform(10000, 100000), 2)},
        {"accountType": "AMC", "balance": round(random.uniform(50000, 300000), 2)},
        {"accountType": "BROKERAGE", "balance": round(random.uniform(50000, 500000), 2)}
    ]

    for acc in accounts:
        acc["accountId"] = str(uuid.uuid4())
        acc["transactions"] = generate_transactions(acc["accountType"])

    return {
        "userId": user["user_id"],
        "name": user["name"],
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "accounts": accounts
    }

# ---------- GENERATE FILES ----------

for user in USERS:
    user_data = generate_user_data(user)
    filename = f"{user['user_id']}_data.json"

    with open(filename, "w") as f:
        json.dump(user_data, f, indent=4)

    print(f"Generated: {filename}")

print("\n✅ All 4 users data generated successfully!")