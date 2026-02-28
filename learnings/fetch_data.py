import requests
import json

# --- CONFIGURATION ---
# PASTE THE SESSION ID YOU JUST GOT HERE 👇
SESSION_ID    = ""

CLIENT_ID     = ""
CLIENT_SECRET = ""
PRODUCT_ID    = ""

url = f"https://fiu-sandbox.setu.co/v2/sessions/{SESSION_ID}"

headers = {
    "x-client-id": CLIENT_ID,
    "x-client-secret": CLIENT_SECRET,
    "x-product-instance-id": PRODUCT_ID
}

try:
    print(f"🚀 Fetching Data for Session: {SESSION_ID}...")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        
        # Save the encrypted data to a file so we don't lose it
        with open("bank_data.json", "w") as f:
            json.dump(data, f, indent=4)
            
        print("\n🎉 SUCCESS! DATA DOWNLOADED!")
        print("------------------------------------------------")
        print("Status:", data.get('status'))
        
        # Check if payload exists
        if 'payload' in data and len(data['payload']) > 0:
            print("✅ Payload received (Encrypted Bank Statement).")
            print("💾 Saved to file: 'bank_data_encrypted.json'")
            print("------------------------------------------------")
            print("Next Step: DECRYPTION")
        else:
            print("⚠️ Response received, but payload is empty. (Bank might be preparing data)")
            
    else:
        print(f"\n❌ FAILED: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Error: {e}")