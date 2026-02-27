import requests
import time
import json
import sys

# --- CONFIGURATION ---
# 👇 PASTE YOUR LATEST SESSION ID HERE 👇
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

print(f"🚀 Tracking Session: {SESSION_ID}")
print("Waiting for Bank to prepare data...", end="")

# --- THE LOOP: Check status every 2 seconds ---
for i in range(10): # Try for 20 seconds max
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        status = data.get('status')
        
        # CASE 1: Data is Ready!
        if status == "COMPLETED":
            print(f"\n\n✅ STATUS: {status}")
            print("🎉 Data is ready! Saving to file...")
            
            with open("bank_data_final.json", "w") as f:
                json.dump(data, f, indent=4)
                
            print(f"📂 Saved to: 'bank_data_final.json'")
            print("👉 Open this file to see your transactions.")
            break
            
        # CASE 2: Still Working
        elif status == "PENDING" or status == "PROCESSING":
            print(".", end="", flush=True) # Print dots ....
            time.sleep(2) # Wait 2 seconds
            
        # CASE 3: Failed
        else:
            print(f"\n❌ Status: {status}")
            print("The bank failed to fetch this session.")
            break
    else:
        print(f"\n❌ API Error: {response.status_code}")
        break
else:
    print("\n\n⚠️ TIMEOUT: The bank is taking too long.")
    print("Try running this script again in 1 minute.")