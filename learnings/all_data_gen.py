import json
import random
import uuid
from datetime import datetime, timedelta

# ---------------- USERS ----------------

USERS = [
    {"user_id": "user_0011", "name": "Aarav Sharma"},
    {"user_id": "user_0021", "name": "Rohan Mehta"},
    {"user_id": "user_0031", "name": "Neha Verma"},
    {"user_id": "user_0041", "name": "Priya Kulkarni"},
]

# ---------------- UTILITIES ----------------

def random_date():
    start = datetime.now() - timedelta(days=180)
    return (start + timedelta(days=random.randint(0,180))).strftime("%Y-%m-%d")

def random_datetime():
    start = datetime.now() - timedelta(days=180)
    return (start + timedelta(days=random.randint(0,180))).strftime("%Y-%m-%dT%H:%M:%S+00:00")

# ---------------- BANK ACCOUNT ----------------

MERCHANTS = ["Swiggy","Zomato","Amazon","Flipkart","Uber","Ola","DMart",
             "Electricity Bill","Netflix","Rent Payment","UPI Transfer"]

def generate_bank_account(acc_type):
    transactions = []

    for _ in range(random.randint(100,150)):
        amt = round(random.uniform(100,8000),2)
        transactions.append({
            "txnId": str(uuid.uuid4()),
            "date": random_date(),
            "description": random.choice(MERCHANTS),
            "amount": -amt,
            "type": "DEBIT",
            "currency": "INR"
        })

    # Salary
    transactions.append({
        "txnId": str(uuid.uuid4()),
        "date": random_date(),
        "description": "Salary Credit",
        "amount": round(random.uniform(40000,90000),2),
        "type": "CREDIT",
        "currency": "INR"
    })

    # Fraud txn
    transactions.append({
        "txnId": "FRAUD-"+str(uuid.uuid4())[:8],
        "date": random_date(),
        "description": "International POS - Unknown",
        "amount": -49999.99,
        "type": "DEBIT",
        "currency": "INR",
        "flagged": True
    })

    transactions = sorted(
        transactions,
        key=lambda x: x["date"],
        reverse=True
    )

    return {
        "accountType": acc_type,
        "accountId": str(uuid.uuid4()),
        "balance": round(random.uniform(20000,200000),2),
        "transactions": transactions
    }

# ---------------- AMC ACCOUNT ----------------

def generate_amc_account(user_name):

    link_ref = str(uuid.uuid4())

    holdings = []
    for _ in range(random.randint(3,6)):
        nav = round(random.uniform(80,250),2)
        units = random.randint(10,500)
        holdings.append({
            "amc": random.choice(["HDFC Mutual Fund","ICICI Prudential","SBI Mutual Fund"]),
            "registrar": "CAMS",
            "schemeCode": str(uuid.uuid4())[:12],
            "schemeOption": "GROWTH",
            "schemeTypes": "EQUITY_SCHEMES",
            "schemeCategory": "LARGE_CAP",
            "isin": "IN"+str(random.randint(1000000000,9999999999)),
            "isinDescription": "Equity Growth Fund",
            "ucc": str(uuid.uuid4())[:20],
            "amfiCode": str(random.randint(10000000,99999999)),
            "folioNo": str(random.randint(1000000000000,9999999999999)),
            "fatcaStatus": "No",
            "closingUnits": str(units),
            "lienUnits": "0",
            "nav": str(nav),
            "navDate": "2025-02-01",
            "lockinUnits": "0"
        })

    transactions = []
    for _ in range(random.randint(20,40)):
        transactions.append({
            "amc": random.choice(["HDFC Mutual Fund","ICICI Prudential"]),
            "registrar": "CAMS",
            "schemeCode": str(uuid.uuid4())[:12],
            "schemePlan": "REGULAR",
            "isin": "IN"+str(random.randint(1000000000,9999999999)),
            "amfiCode": str(random.randint(10000000,99999999)),
            "ucc": str(uuid.uuid4())[:20],
            "amount": str(round(random.uniform(5000,200000),2)),
            "nav": str(round(random.uniform(100,400),2)),
            "navDate": "2025-01-15",
            "type": random.choice(["BUY","SELL"]),
            "lock-inFlag": "",
            "lock-inDays": "",
            "mode": "DEMAT",
            "narration": f"SIP/{user_name}/AUTO",
            "txnId": str(uuid.uuid4())[:18],
            "isinDescription": "Equity Growth Fund",
            "units": str(random.randint(10,200)),
            "transactionDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })


    transactions = sorted(
    transactions,
    key=lambda x: x["transactionDate"],
    reverse=True
    )

    return {
        "FIstatus": "READY",
        "linkRefNumber": link_ref,
        "data": {
            "account": {
                "linkedAccRef": link_ref,
                "maskedAccNumber": "XXXXXXXX"+str(random.randint(1000,9999)),
                "type": "mutual_funds",
                "version": "1.1",
                "profile": {
                    "holders": {
                        "type": "SINGLE",
                        "holder": [{
                            "address": "Pune, Maharashtra",
                            "dob": "1999-04-10",
                            "email": f"{user_name.lower().replace(' ','')}@demo.com",
                            "mobile": str(random.randint(9000000000,9999999999)),
                            "name": user_name,
                            "nominee": "REGISTERED",
                            "pan": "ABCDE1234F"
                        }]
                    }
                },
                "summary": {
                    "investment": {
                        "holdings": {
                            "holding": holdings
                        }
                    },
                    "costValue": str(round(random.uniform(50000,300000),2)),
                    "currentValue": str(round(random.uniform(60000,400000),2))
                },
                "transactions": {
                    "startDate": "2025-09-01",
                    "endDate": "2026-02-28",
                    "transaction": transactions
                }
            }
        }
    }

# ---------------- BROKERAGE ACCOUNT ----------------

def generate_brokerage_account(user_name):

    link_ref = str(uuid.uuid4())

    holdings = []
    for _ in range(random.randint(3,6)):
        rate = round(random.uniform(100,800),2)
        units = random.randint(5,200)
        holdings.append({
            "description": "",
            "investmentDateTime": random_datetime(),
            "isin": "IN"+str(random.randint(1000000000,9999999999)),
            "issuerName": random.choice(["Reliance Industries","TCS","Infosys"]),
            "lastTradedPrice": str(rate),
            "rate": str(rate- random.uniform(5,50)),
            "units": str(units)
        })

    transactions = []
    for _ in range(random.randint(20,40)):
        transactions.append({
            "companyName": random.choice(["TCS","Reliance","HDFC Bank"]),
            "equityCategory": random.choice(["EQUITY_DERIVATIVES","CURRENCY_DERIVATIVES"]),
            "exchange": random.choice(["NSE","BSE"]),
            "instrumentType": random.choice(["FUTURES","OPTIONS"]),
            "isin": "IN"+str(random.randint(1000000000,9999999999)),
            "narration": f"EQUITY/{user_name}",
            "optionType": random.choice(["CALL","PUT"]),
            "orderId": str(uuid.uuid4())[:14],
            "otherCharges": str(round(random.uniform(100,500),2)),
            "rate": str(round(random.uniform(100,700),2)),
            "shareHolderEquityType": str(round(random.uniform(100,2000),2)),
            "strikePrice": str(round(random.uniform(100,800),2)),
            "symbol": random.choice(["TCS","RELIANCE","HDFCBANK"]),
            "totalCharge": str(round(random.uniform(10000,50000),2)),
            "tradeValue": str(round(random.uniform(100,800),2)),
            "transactionDateTime": random_datetime(),
            "txnId": str(uuid.uuid4())[:18],
            "type": random.choice(["BUY","SELL"]),
            "units": str(random.randint(1,500))
        })

    # Suspicious Trade
    transactions.append({
        "companyName": "Unknown Small Cap",
        "equityCategory": "EQUITY_DERIVATIVES",
        "exchange": "OTHERS",
        "instrumentType": "OPTIONS",
        "isin": "IN9999999999",
        "narration": "High Risk Intraday",
        "optionType": "CALL",
        "orderId": "RISK123456",
        "otherCharges": "999.99",
        "rate": "950.00",
        "shareHolderEquityType": "0",
        "strikePrice": "900.00",
        "symbol": "RISK",
        "totalCharge": "150000.00",
        "tradeValue": "950.00",
        "transactionDateTime": random_datetime(),
        "txnId": "FRAUDTRADE001",
        "type": "BUY",
        "units": "500"
    })

    transactions = sorted(
        transactions,
        key=lambda x: x["transactionDateTime"],
        reverse=True
    )
    
    return {
        "FIstatus": "READY",
        "linkRefNumber": link_ref,
        "data": {
            "account": {
                "linkedAccRef": link_ref,
                "maskedAccNumber": "XXXXXXXX"+str(random.randint(1000,9999)),
                "type": "equities",
                "version": "1.1",
                "profile": {
                    "holders": {
                        "type": "SINGLE",
                        "holder": [{
                            "address": "Pune, Maharashtra",
                            "ckycCompliance": "true",
                            "dob": "1999-04-10",
                            "email": f"{user_name.lower().replace(' ','')}@demo.com",
                            "mobile": str(random.randint(9000000000,9999999999)),
                            "name": user_name,
                            "nominee": "REGISTERED",
                            "pan": "ABCDE1234F",
                            "dematId": "IN303575XXXX",
                            "boId": "XXXX",
                            "dpId": "IN303575",
                            "brokerName": "Zerodha Broking Ltd"
                        }]
                    }
                },
                "summary": {
                    "investment": {
                        "holdings": {
                            "holding": holdings
                        }
                    },
                    "currentValue": str(round(random.uniform(100000,500000),2)),
                    "investmentValue": str(round(random.uniform(80000,400000),2))
                },
                "transactions": {
                    "startDate": "2025-09-01",
                    "endDate": "2026-02-28",
                    "transaction": transactions
                }
            }
        }
    }

# ---------------- GENERATE USERS ----------------

for user in USERS:

    user_data = {
        "userId": user["user_id"],
        "name": user["name"],
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "bankAccounts": [
            generate_bank_account("SAVINGS"),
            generate_bank_account("CURRENT")
        ],
        "amcAccount": generate_amc_account(user["name"]),
        "brokerageAccount": generate_brokerage_account(user["name"])
    }

    filename = f"{user['user_id']}_full_data.json"

    with open(filename,"w") as f:
        json.dump(user_data,f,indent=4)

    print(f"Generated {filename}")

print("\n🔥 All 4 users full structured data generated successfully!")