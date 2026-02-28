import requests

print("\n--- 🚀 FINAL ATTEMPT: FIXED TYPO ---")

# --- 1. CREDENTIALS ---
CLIENT_ID     = ""
CLIENT_SECRET = ""
PRODUCT_ID    = ""

url = "https://fiu-sandbox.setu.co/v2/consents"

headers = {
    "x-client-id": CLIENT_ID.strip(),
    "x-client-secret": CLIENT_SECRET.strip(),
    "x-product-instance-id": PRODUCT_ID.strip(),
    "Content-Type": "application/json"
}

payload = {
    "consentMode": "STORE",
    "fetchType": "PERIODIC",
    "frequency": {
        "unit": "HOUR",  # Options: HOUR, DAY, MONTH, YEAR
        "value": 10       # Meaning: "I can fetch data once every 1 hour"
    },
    "consentTypes": ["TRANSACTIONS", "PROFILE", "SUMMARY"],
    "vua": "7464847437", 
    "dataRange": {
        "from": "2026-01-01T00:00:00Z",
        "to": "2026-04-01T00:00:00Z"
    },
    "consentDuration": {
        "unit": "MONTH",
        "value": "12"
    },
    "purpose": {
        "code": "102",
        "text": "Customer spending and budget analysis",
        "category": {
            "type": "PERSONAL_FINANCE"
        },
        "refUri": "https://api.rebit.org.in/aa/purpose/102.xml"
    },
    "fiTypes": ["DEPOSIT", "MUTUAL_FUNDS", "EQUITIES"],
    "redirectUrl": "https://google.com"
}

try:
    print(f"📡 Sending Corrected Payload...")
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 201:
        print("\n🎉 SUCCESS! WE ARE IN!")
        print("------------------------------------------------")
        print("Id:", response.json()['id'])
        print("URL:", response.json()['url'])
        print("Status:", response.json()['status'])
        print("------------------------------------------------")
    else:
        print(f"\n❌ ERROR {response.status_code}")
        print("Setu Response:", response.text)

except Exception as e:
    print(f"\n❌ SYSTEM ERROR: {e}")
