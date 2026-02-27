import requests
import uuid
import time
import sys

# --- CONFIGURATION ---
CLIENT_ID     = ""
CLIENT_SECRET = ""
PRODUCT_ID    = ""

# 1. SETUP: Create a truly fresh user
# fresh_mobile = f"99{str(uuid.uuid4().int)[:8]}"  # Random 10-digit number
# print(f"🆔 Generated Fresh User: {fresh_mobile}")

# --- STEP 1: CREATE CONSENT ---
url_consent = "https://fiu-sandbox.setu.co/v2/consents"
headers = {
    "x-client-id": CLIENT_ID,
    "x-client-secret": CLIENT_SECRET,
    "x-product-instance-id": PRODUCT_ID,
    "Content-Type": "application/json"
}


payload_consent = {
    "consentMode": "STORE",
    "fetchType": "PERIODIC",
    "frequency": {
        "unit": "HOUR",  # Options: HOUR, DAY, MONTH, YEAR
        "value": 10       # Meaning: "I can fetch data once every 1 hour"
    },
    "consentTypes": ["TRANSACTIONS", "PROFILE", "SUMMARY"],
    "vua": "9741877174",
    "dataRange": {
        "from": "2023-01-01T00:00:00Z",
        "to": "2023-04-01T00:00:00Z"
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
    print("\n📡 Step 1: Creating Consent...")
    resp = requests.post(url_consent, json=payload_consent, headers=headers)
    
    if resp.status_code == 201:
        data = resp.json()
        new_id = data['id']
        auth_url = data['url']
        
        print(f"✅ CONSENT ID: {new_id}")
        print(f"\n👉 ACTION REQUIRED: Open this URL and Approve (OTP: 123456)")
        print(f"🔗 {auth_url}")
        print("\n⏳ I am waiting here... Press ENTER once you have approved.")
        input() 
        print("🔍 Waiting for consent to become ACTIVE...")

        while True:
            status_resp = requests.get(f"{url_consent}/{new_id}", headers=headers)
            consent_data = status_resp.json()
            status = consent_data.get("status")

            print("Current status:", status)

            if status == "ACTIVE":
                print("✅ Consent is ACTIVE. Proceeding to session creation.")
                break

            time.sleep(3)

        # --- STEP 2: CREATE SESSION ---
        print("\n📡 Step 2: Creating Data Session...")
        url_session = "https://fiu-sandbox.setu.co/v2/sessions"
        payload_session = {
            "consentId": new_id, 
            "dataRange": {
                "from": "2023-01-01T00:00:00Z",
                "to": "2023-04-01T00:00:00Z"
            },
            "format": "json"
        }
        
        resp_sess = requests.post(url_session, json=payload_session, headers=headers)
        
        if resp_sess.status_code == 201:
            sess_data = resp_sess.json()
            print("\n🎉 SUCCESS! DATA SESSION CREATED!")
            print(f"🔑 Session ID: {sess_data['id']}")
            print("\nCopy this Session ID for the final decryption step.")
        else:
            print(f"❌ Session Failed: {resp_sess.text}")
            
    else:
        print(f"❌ Consent Failed: {resp.text}")

except Exception as e:
    print(f"Error: {e}")