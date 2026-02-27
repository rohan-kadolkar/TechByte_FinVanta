import requests
import json
import uuid

# --- CONFIGURATION ---
CONSENT_ID    = "" # <--- The one that is ACTIVE
CLIENT_ID     = ""
CLIENT_SECRET = ""
PRODUCT_ID    = ""

url = "https://fiu-sandbox.setu.co/v2/sessions"

headers = {
    "x-client-id": CLIENT_ID,
    "x-client-secret": CLIENT_SECRET,
    "x-product-instance-id": PRODUCT_ID,
    "Content-Type": "application/json"
}

# The payload asks for the data strictly within the range you got consent for
payload = {
    "consentId": CONSENT_ID,
    # "dataRange": {
    #     "from": "2023-04-01T00:00:00Z",
    #     "to": "2023-10-01T00:00:00Z"
    # },
    "dataRange": {
        "from": "2026-01-01T00:00:00Z",
        "to": "2026-02-19T00:00:00Z"
    },
    "format": "json"
}

try:
    print(f"🚀 Initiating Data Session for {CONSENT_ID}...")
    response = requests.post(url, json=payload, headers=headers)
    
    # 201 Created = Success
    if response.status_code == 201:
        data = response.json()
        session_id = data['id']
        print("\n------------------------------------------------")
        print(f"✅ SESSION CREATED!")
        print(f"Session ID: {session_id}") 
        print("------------------------------------------------")
        print("NEXT STEP: Use this Session ID to download the data.")
    else:
        print(f"\n❌ FAILED: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Error: {e}")