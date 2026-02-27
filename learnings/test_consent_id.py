import requests
import json

# --- CONFIGURATION ---
CONSENT_ID    = ""  # <--- REPLACE THIS with the ID from the previous step
CLIENT_ID     = ""
CLIENT_SECRET = ""
PRODUCT_ID    = ""

url = f"https://fiu-sandbox.setu.co/v2/consents/{CONSENT_ID}"

headers = {
    "x-client-id": CLIENT_ID,
    "x-client-secret": CLIENT_SECRET,
    "x-product-instance-id": PRODUCT_ID
}

try:
    print(f"🔍 Checking status for: {CONSENT_ID}...")
    response = requests.get(url, headers=headers)
    
    data = response.json()
    status = data.get('status', 'UNKNOWN')
    
    print("\n------------------------------------------------")
    print(f"STATUS:  {status}")
    print("------------------------------------------------")
    
    if status == "ACTIVE":
        print("✅ SUCCESS! You can now fetch data.")
        print(f"Consent Handle: {data.get('consentHandle')}")
    elif status == "PENDING":
        print("⏳ WAITING... Did you finish the flow on your phone?")
    elif status == "REJECTED":
        print("❌ DENIED. The user (you) rejected the request.")
        
except Exception as e:
    print(f"Error: {e}")