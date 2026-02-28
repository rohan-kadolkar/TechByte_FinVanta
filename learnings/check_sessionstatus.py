import requests

# --- CONFIGURATION ---
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

# --- CHECK STATUS ---
response = requests.get(url, headers=headers)

if response.status_code == 200:
    data = response.json()
    
    # Extract the status field from the JSON response
    current_status = data.get('status')
    
    print(f"🔍 Session Status is: {current_status}")
    
    if current_status == "COMPLETED":
        print("✅ The data is ready! You can now process the payload.")
    elif current_status in ["PENDING", "PROCESSING"]:
        print("⏳ The bank is still gathering the data. Check again in a few seconds.")
    elif current_status == "FAILED":
        print("❌ The bank failed to gather the data.")
else:
    print(f"❌ API Error: {response.status_code}")
    print(response.text)