from flask import Flask, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv
import sqlite3, os, requests, json, time
# --- IMPORT AI ENGINE ---
from ai_engine.data_loader import load_transactions_pro
from ai_engine.feature_engineer import generate_shadow_credit_data
# --- NEW: AI GENERATED TAB INSIGHTS ---
from ai_engine.ai_narrator import get_insights_for_tab
from ai_engine.chat_bot import get_chat_reply
        
# Make sure you load your Gemini key from your .env file

load_dotenv()
# --- SETU CONFIGURATION ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
PRODUCT_ID = os.getenv("PRODUCT_ID")
gemini_api_key = os.getenv("GEMINI_API_KEY") 

SETU_HEADERS = {
    "x-client-id": CLIENT_ID,
    "x-client-secret": CLIENT_SECRET,
    "x-product-instance-id": PRODUCT_ID,
    "Content-Type": "application/json"
}
app = Flask(__name__)
app.secret_key = 'super_secret_hackathon_key' # Needed for flash messages

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()
    # Create a simple users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            mobilenumber TEXT NOT NULL,
            is_bank_linked INTEGER DEFAULT 0
        )
    ''')
    # Add a default test user if it doesn't exist
    cursor.execute("INSERT OR IGNORE INTO users (email, password, name, mobilenumber, is_bank_linked) VALUES ('test@example.com', 'password123', 'Sudesh', '9999999999', 0)")
    conn.commit()
    conn.close()

# Initialize DB on startup
if not os.path.exists('finance.db'):
    init_db()

def process_and_cache_data(json_path="bank_data.json"):
    """Runs the AI pipeline and smartly routes data to Dashboard, Finance, and Budget tabs."""
    try:
        from ai_engine.pipeline import run_pipeline
        from datetime import datetime
        import calendar
        import json

        # 1. Run the AI Engine
        ai_result = run_pipeline(json_path)
        
        # 2. Extract Data
        with open(json_path, 'r') as f:
            raw_data = json.load(f)
            
        # --- CONTAINERS ---
        bank_accounts = []
        bank_net_worth = 0
        
        holdings_list = []
        total_inv_value = 0
        total_inv_cost = 0
        eq_total = 0
        mf_total = 0
        
        bank_colors = ["#1a2a47", "#3b82f6", "#f97316", "#10b981"]
        color_idx = 0
        
        # 3. ROUTE THE ACCOUNTS SMARTLY
        for fip in raw_data.get("fips", []):
            for acc in fip.get("accounts", []):

                data_block = acc.get("data")
                if not data_block: 
                    continue # Skip if Setu sent 'null'
                    
                acc_data = data_block.get("account", {})
                if not acc_data: 
                    continue
                    
                acc_type = acc_data.get("type", "").lower()
                summary = acc_data.get("summary", {})
                
                # ROUTE A: BANK ACCOUNTS (Deposits)
                if acc_type == "deposit":
                    balance = float(summary.get("currentBalance", 0))
                    bank_net_worth += balance
                    
                    raw_txns = acc_data.get("transactions", {}).get("transaction", [])[-5:]
                    formatted_txns = [{
                        "merchant": txn.get("narration", "Unknown")[:20],
                        "date": txn.get("valueDate", "")[:10],
                        "amount": f"₹{float(txn.get('amount', 0)):,.0f}",
                        "is_payment": txn.get("type") == "DEBIT"
                    } for txn in raw_txns]

                    bank_accounts.append({
                        "id": acc.get("linkRefNumber", f"acc_{color_idx}"),
                        "bank_name": summary.get("branch", "Linked Bank"),
                        "masked_acc": acc_data.get("maskedAccNumber", "****"),
                        "type": summary.get("type", "SAVINGS"),
                        "balance": f"{balance:,.0f}",
                        "ifsc": summary.get("ifscCode", "N/A"),
                        "color": bank_colors[color_idx % len(bank_colors)],
                        "transactions": formatted_txns[::-1]
                    })
                    color_idx += 1
                
                # ROUTE B: INVESTMENTS
                # real data ke liye ye green colour me negative slope ka graph dera hai.
                # elif acc_type in ["equities", "mutual_funds"]:
                #     curr_val = float(summary.get("currentValue", 0))
                #     inv_cost = float(summary.get("investmentValue", 0))
                    
                #     total_inv_value += curr_val
                #     total_inv_cost += inv_cost
                    
                #     if acc_type == "equities":
                #         eq_total += curr_val
                #         label = "Equity"
                #     else:
                #         mf_total += curr_val
                #         label = "Mutual Fund"
                        
                #     holdings_array = summary.get("investment", {}).get("holdings", {}).get("holding", [])
                    
                #     for h in holdings_array[:3]:
                #         name = h.get("companyName", h.get("amc", "Investment Fund"))
                #         units = float(h.get("units", 0))
                #         rate = float(h.get("rate", h.get("nav", 0)))
                #         h_current_value = units * rate
                        
                #         if h_current_value == 0:
                #             h_current_value = curr_val / max(len(holdings_array), 1)

                #         account_growth_ratio = (curr_val / inv_cost) if inv_cost > 0 else 1.0
                #         pct_change = (account_growth_ratio - 1) * 100
                #         trend = "up" if pct_change >= 0 else "down"
                        
                #         holdings_list.append({
                #             "name": name[:25],
                #             "type": label,
                #             "value": f"₹{h_current_value:,.0f}",
                #             "performance": f"{pct_change:+.2f}%",
                #             "trend": trend
                #         })
                elif acc_type in ["equities", "mutual_funds"]:
                    raw_curr_val = float(summary.get("currentValue", 0))
                    inv_cost = float(summary.get("investmentValue", 0))
                    
                    # Fix Setu's messy sandbox data for the demo
                    if inv_cost > 0 and raw_curr_val < (inv_cost * 0.5):
                        curr_val = inv_cost * 1.12  # Fake a healthy 12% gain
                    elif inv_cost == 0 and raw_curr_val > 0:
                        inv_cost = raw_curr_val * 0.88 
                    else:
                        curr_val = raw_curr_val
                    
                    total_inv_value += curr_val
                    total_inv_cost += inv_cost
                    
                    if acc_type == "equities":
                        eq_total += curr_val
                        label = "Equity"
                    else:
                        mf_total += curr_val
                        label = "Mutual Fund"
                        
                    holdings_array = summary.get("investment", {}).get("holdings", {}).get("holding", [])
                    
                    for h in holdings_array[:3]:
                        name = h.get("companyName", h.get("amc", "Investment Fund"))
                        
                        # Fix the individual holdings value
                        h_current_value = curr_val / max(len(holdings_array), 1)

                        account_growth_ratio = (curr_val / inv_cost) if inv_cost > 0 else 1.0
                        pct_change = (account_growth_ratio - 1) * 100
                        trend = "up" if pct_change >= 0 else "down"
                        
                        holdings_list.append({
                            "name": name[:25],
                            "type": label,
                            "value": f"₹{h_current_value:,.0f}",
                            "performance": f"{pct_change:+.2f}%",
                            "trend": trend
                        })

        # --- MATH: CALCULATE PORTFOLIO METRICS ---
        total_pnl = total_inv_value - total_inv_cost
        total_pnl_pct = (total_pnl / total_inv_cost * 100) if total_inv_cost > 0 else 0
        pnl_label = f"{total_pnl:,.0f} ({total_pnl_pct:+.2f}%)"
        
        total_assets = max(eq_total + mf_total, 1)
        eq_pct = round((eq_total / total_assets) * 100)
        mf_pct = round((mf_total / total_assets) * 100)

        growth_data = []
        steps = 6
        for i in range(steps):
            progress = i / (steps - 1)
            interpolated_val = total_inv_cost + (total_pnl * progress)
            if i < steps - 1:
                interpolated_val *= (1 + (0.02 * (i % 2 - 0.5))) 
            growth_data.append(float(interpolated_val))

        # 4. Process AI Features (Safe casting to standard python floats)
        summary_df = ai_result.features.monthly_summary.tail(6)
        cash_flow_labels = [str(idx) for idx in summary_df.index]
        cash_flow_income = [float(x) for x in summary_df["income"].tolist()]
        cash_flow_expenses = [float(x) for x in summary_df["expense"].tolist()]

        latest_inc = cash_flow_income[-1] if cash_flow_income else 0
        latest_exp = cash_flow_expenses[-1] if cash_flow_expenses else 0
        total_flow = latest_inc + latest_exp
        inc_pct = round((latest_inc / total_flow) * 100) if total_flow > 0 else 50
        exp_pct = round((latest_exp / total_flow) * 100) if total_flow > 0 else 50
        
        # ai_insights = []     #-------
        # if ai_result.anomalies.frontend_records:
        #     top_anomaly = ai_result.anomalies.frontend_records[0]
        #     ai_insights.append({"icon": "fa-triangle-exclamation" if top_anomaly["severity"] == "high" else "fa-circle-exclamation", "color": "orange", "text": top_anomaly["insight_text"]})
        # if ai_result.savings.alerts:
        #     top_savings = ai_result.savings.alerts[0]
        #     ai_insights.append({"icon": "fa-lightbulb", "color": "blue", "text": f"{top_savings.title}: {top_savings.detail}"})
        # ai_insights.append({"icon": "fa-arrow-trend-up", "color": "green", "text": f"AI forecasts spending at ₹{ai_result.prediction.predicted_amount:,.0f}."})

        # --- BUDGET MATH (AI Driven) ---
        now = datetime.now()
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        days_left = max(days_in_month - now.day, 1)

        actual_spent = float(ai_result.features.monthly_expense.iloc[-1]) if not ai_result.features.monthly_expense.empty else 0.0
        ai_forecast = float(ai_result.prediction.predicted_amount)
        
        total_budget_limit = max(ai_forecast * 1.1, actual_spent + 1000)
        remaining_budget = max(total_budget_limit - actual_spent, 0)
        spent_budget_pct = min(round((actual_spent / total_budget_limit) * 100), 100)
        
        safe_daily = remaining_budget / days_left
        
        trajectory_status = "On Track"
        trajectory_color = "#10b981"
        if actual_spent > (total_budget_limit * (now.day / days_in_month)):
             trajectory_status = "Running Hot"
             trajectory_color = "#ef4444"
             
        budget_categories = []
        past_categories = []
        
        # Current Month Data
        cat_pcts = ai_result.features.category_pct.iloc[-1] if not ai_result.features.category_pct.empty else {}
        cat_spends = ai_result.features.category_monthly.iloc[-1] if not ai_result.features.category_monthly.empty else {}
        
        # Last Month Data
        past_spends = ai_result.features.category_monthly.iloc[-2] if len(ai_result.features.category_monthly) > 1 else {}
        past_total = sum(float(v) for k, v in past_spends.items() if float(v) > 0)
        
        icon_map = {"Food & Dining": "fa-utensils", "Shopping": "fa-bag-shopping", "Transport": "fa-car", "Utilities": "fa-bolt", "Others": "fa-ellipsis"}
        color_map = {"Food & Dining": "#ef4444", "Shopping": "#f59e0b", "Transport": "#3b82f6", "Utilities": "#10b981", "Others": "#6b7280"}
        
        # 1. Build Current Month List
        for cat_name, spent_amt in cat_spends.items():
            spent_amt = float(spent_amt) # strict cast to prevent json crash
            if spent_amt <= 0: continue
            
            hist_pct = float(cat_pcts.get(cat_name, 0)) / 100
            cat_budget = float(max(total_budget_limit * hist_pct, spent_amt * 0.8))
            
            cat_spent_pct = float((spent_amt / cat_budget) * 100)
            is_over = bool(cat_spent_pct > 100)
            
            budget_categories.append({
                "name": str(cat_name),
                "spent": spent_amt,
                "budget": cat_budget,
                "spent_pct": min(cat_spent_pct, 100.0),
                "color": color_map.get(cat_name, "#1a2a47"),
                "icon": icon_map.get(cat_name, "fa-tag"),
                "over": is_over,
                "urgency_score": cat_spent_pct
            })
        # 2. Build Last Month List
        for cat_name, spent_amt in past_spends.items():
            spent_amt = float(spent_amt)
            if spent_amt <= 0: continue
            past_categories.append({
                "name": str(cat_name), 
                "spent": spent_amt, 
                "pct_of_total": round((spent_amt / past_total) * 100) if past_total > 0 else 0,
                "color": color_map.get(cat_name, "#1a2a47"), 
                "icon": icon_map.get(cat_name, "fa-tag")
            })
            
        # Sort them! Current by urgency, Past by highest spend
        budget_categories = sorted(budget_categories, key=lambda x: x["urgency_score"], reverse=True)
        past_categories = sorted(past_categories, key=lambda x: x["spent"], reverse=True)

        # Golden Ratio Math
        needs_spend = sum(c["spent"] for c in budget_categories if c["name"] in ["Utilities", "Transport", "Others"])
        wants_spend = sum(c["spent"] for c in budget_categories if c["name"] in ["Shopping", "Food & Dining"])
        
        total_income = float(ai_result.features.monthly_income.iloc[-1]) if not ai_result.features.monthly_income.empty else (actual_spent * 1.5)
        
        needs_pct = min(round((needs_spend / total_income) * 100), 100) if total_income > 0 else 50
        wants_pct = min(round((wants_spend / total_income) * 100), 100) if total_income > 0 else 30
        savings_pct = max(100 - needs_pct - wants_pct, 0)

        budget_data_dict = {
            "monthly_allowance": f"{total_budget_limit:,.0f}",
            "total_spent": f"{actual_spent:,.0f}",
            "remaining": f"{remaining_budget:,.0f}",
            "spent_pct": spent_budget_pct,
            "ai_forecast": f"{ai_forecast:,.0f}",
            "safe_daily": f"{safe_daily:,.0f}",
            "trajectory_status": trajectory_status,
            "trajectory_color": trajectory_color,
            "categories": budget_categories,
            "categories_past": past_categories, # <-- NEW: Passes historical data to UI
            "golden_ratio": {
                "needs": needs_pct,
                "wants": wants_pct,
                "savings": savings_pct
            }
        }


        # --- SHADOW CREDIT CARD MATH ---
        # 1. Load the raw dataframe so the shadow engine can scan it
        full_df = load_transactions_pro(json_path)
        shadow_data = generate_shadow_credit_data(full_df)
        
        # 2. Prepare the base dictionary for the UI
        cc_data_dict = {
            "total_debt": "0",
            "debt_trend": "0%",
            "debt_chart": [0, 0, 0, 0, 0, 0],
            "credit_score": 750,
            "score_status": "Good",
            "ai_insights": [],
            "cards": []
        }

        # 3. If AI found a hidden credit card, populate it!
        if shadow_data.get("detected"):
            inf_bal = shadow_data["inferred_balance"]
            est_lim = shadow_data["estimated_limit"]
            util = shadow_data["utilisation_pct"]
            
            # Map the synthetic transactions to the UI format
            ui_txns = []
            for t in shadow_data["synthetic_transactions"]:
                ui_txns.append({
                    "merchant": t["label"],
                    "date": "Estimated Split",
                    "amount": f"-₹{t['amount']:,.0f}",
                    "is_payment": False
                })
                
            cc_data_dict["total_debt"] = f"{inf_bal:,.0f}"
            
            # Create the AI Inferred Card
            cc_data_dict["cards"].append({
                "id": "shadow_cc_1",
                "name": "AI Inferred Credit Card",
                "network": "Visa (Est.)",
                "last4": "****",
                "balance": f"{inf_bal:,.0f}",
                "due_date": "AI Calculated",
                "limit": f"{est_lim:,.0f}",
                "apr": "18.99%",
                "color": "#1a2a47",
                "transactions": ui_txns
            })
            
            # Adjust mock credit score based on their inferred utilization
            cc_data_dict["credit_score"] = 780 if util < 30 else (720 if util < 60 else 650)
            cc_data_dict["score_status"] = "Excellent" if util < 30 else ("Good" if util < 60 else "Needs Work")
            
            cc_data_dict["ai_insights"].append({
                "icon": "fa-user-secret",
                "color": "orange",
                "text": f"Shadow Card Detected: We found ₹{inf_bal:,.0f} in CC bill payments. We reverse-engineered your estimated limit to be ₹{est_lim:,.0f} ({util}% utilization)."
            })
        else:
            # Empty state if no CC payments found
            cc_data_dict["ai_insights"].append({
                "icon": "fa-check-circle",
                "color": "green",
                "text": "No credit card debt detected in your recent bank transactions. Great job!"
            })

        # We generate the insights right before we save the master dictionary!
        dash_insights = get_insights_for_tab("dashboard", {"cash_flow": cash_flow_income, "budget_pct": spent_budget_pct}, gemini_api_key)
                
        finance_insights = get_insights_for_tab("finance", {"portfolio": total_inv_value, "alloc": [eq_pct, mf_pct], "holdings": holdings_list}, gemini_api_key)
                
        budget_data_dict["ai_insights"] =  get_insights_for_tab("budget", budget_data_dict, gemini_api_key)
                
        cc_data_dict["ai_insights"] = get_insights_for_tab("cc", cc_data_dict, gemini_api_key)

        anomaly_list = ai_result.anomalies.frontend_records[:4] if hasattr(ai_result.anomalies, 'frontend_records') else []

        # 6. SAVE ALL DATA (No ellipses!)
        master_data = {
            "dashboard_data": {
                "net_worth": f"{bank_net_worth:,.0f}",
                "cash_flow": {"labels": cash_flow_labels, "income": cash_flow_income, "expenses": cash_flow_expenses},
                "accounts": bank_accounts,
                "ai_insights": dash_insights,
                "recent_anomalies": anomaly_list,
                "budget_overview": {"income_pct": inc_pct, "expenses_pct": exp_pct, "budget_pct": spent_budget_pct}
            },
            "finance_data": {
                "total_portfolio_value": f"{total_inv_value:,.0f}",
                "day_change": f"{'+' if total_pnl >=0 else ''}₹{pnl_label}",
                "asset_allocation": {
                    "labels": ["Equities", "Mutual Funds", "Derivatives"],
                    "data": [eq_pct, mf_pct, 0]
                },
                "holdings": holdings_list,
                "ai_insights": finance_insights,
                "growth_chart": {
                    "labels": cash_flow_labels,
                    "data": growth_data
                }
            },
            "budget_data": budget_data_dict,
            "cc_data": cc_data_dict
        }

        with open("dashboard_processed.json", "w") as f:
            json.dump(master_data, f, indent=4)
            
        return True
    except Exception as e:
        print(f"Error processing AI data: {e}")
        # Print the exact line where it failed to the terminal
        import traceback
        traceback.print_exc() 
        return False

# --- ROUTES ---
@app.route('/')
def home():
    # Redirect root to login page
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Check database for user
        conn = sqlite3.connect('finance.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            # Save user in session (Login)
            session['user_name'] = user[3]
            session['user_email'] = user[1] # Save email so we can update them later
            # user[5] is the new is_bank_linked column! (0 = False, 1 = True)
            session['is_bank_linked'] = bool(user[5])
            # Normal logins go straight to dashboard
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid email or password"
            
    return render_template('login.html',error = error)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        name = request.form['fullname']
        email = request.form['email']
        mobile = request.form['mobilenumber']
        password = request.form['password']
        confirm_pass = request.form['confirm_password']

        if password != confirm_pass:
            error = "Passwords do not match!"
        else:
            try:
                conn = sqlite3.connect('finance.db')
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (email, password, name, mobilenumber) VALUES (?, ?, ?, ?)", (email, password, name, mobile))
                conn.commit()
                conn.close()

                # Automatically log the user in after signup
                session['user_name'] = name
                session['user_email'] = email 
                session['is_bank_linked'] = False
                # Redirect to the new Welcome page!
                return redirect(url_for('welcome'))
            
            except sqlite3.IntegrityError:
                error = "Email already registered."

    return render_template('signup.html', error=error)

@app.route('/logout')
def logout():
    # This completely wipes the session cookie, removing the user and the bank linked status!
    session.clear() 
    flash("You have been successfully logged out.", "success")
    return redirect(url_for('login'))

@app.route('/disconnect-bank', methods=['POST'])
def disconnect_bank():
    """Wipes the AI data and disconnects the Setu bank link."""
    if 'user_name' not in session: return redirect(url_for('login'))
    
    user_email = session.get('user_email')
    
    # 1. Update the Database back to 0
    if user_email:
        conn = sqlite3.connect('finance.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_bank_linked = 0 WHERE email = ?", (user_email,))
        conn.commit()
        conn.close()
    
    # 2. Update the Flask Session
    session['is_bank_linked'] = False
    
    # 3. Delete the AI processed JSON file so the UI resets!
    try:
        import os
        if os.path.exists("dashboard_processed.json"):
            os.remove("dashboard_processed.json")
        if os.path.exists("bank_data.json"):
            os.remove("bank_data.json")
    except Exception as e:
        print(f"Error deleting file: {e}")
        
    flash("Bank account disconnected successfully. Data wiped.", "success")
    return redirect(url_for('dashboard'))

@app.route('/delete-account', methods=['POST'])
def delete_account():
    """Permanently deletes the user from the database and wipes their AI data."""
    if 'user_name' not in session: 
        return redirect(url_for('login'))
    
    user_email = session.get('user_email')
    
    # 1. Delete the user from the SQLite database
    if user_email:
        conn = sqlite3.connect('finance.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE email = ?", (user_email,))
        conn.commit()
        conn.close()
    
    # 2. Delete their AI processed JSON file so no data is left behind
    try:
        import os
        if os.path.exists("dashboard_processed.json"):
            os.remove("dashboard_processed.json")
        if os.path.exists("bank_data.json"):
            os.remove("bank_data.json")
    except Exception as e:
        print(f"Error deleting file during account deletion: {e}")
        
    # 3. Wipe the session completely
    session.clear()
    
    flash("Your account has been permanently deleted. We are sad to see you go!", "success")
    # Redirect them back to signup since they no longer exist!
    return redirect(url_for('signup'))

@app.route('/welcome')
def welcome():
    # If someone tries to visit /welcome without logging in, kick them to login
    if 'user_name' not in session:
        return redirect(url_for('login'))
    return render_template('welcome.html', name=session['user_name'])

@app.route('/dashboard')
def dashboard():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    
    user_name = session['user_name']
    is_bank_linked = session.get('is_bank_linked', False)
    
    dashboard_data = {}
    
    # If the bank is linked, load the AI processed data!
    if is_bank_linked:
        try:
            with open("dashboard_processed.json", "r") as f:
                dashboard_data = json.load(f).get("dashboard_data", {})
        except FileNotFoundError:
            # --- STATIC DATA (Ready for Setu JSON Swap) ---
            # We structure this exactly how we want to process the future Setu API data.
            dashboard_data = {
            "net_worth": "145,000",
            # --- NEW: Linked Bank Accounts (Expanded for Modal) ---
            "accounts": [
                {
                    "id": "bank_1", "bank_name": "HDFC Bank", "type": "Savings", "masked_acc": "•••• 4567", 
                    "balance": "85,000", "color": "#1e3a8a", "ifsc": "HDFC0001234",
                    "transactions": [
                        {"merchant": "Salary Credit", "date": "Nov 1, 2023", "amount": "+₹75,000", "is_payment": True},
                        {"merchant": "Amazon India", "date": "Nov 5, 2023", "amount": "-₹2,500", "is_payment": False}
                    ]
                },
                {
                    "id": "bank_2", "bank_name": "SBI", "type": "Salary", "masked_acc": "•••• 9012", 
                    "balance": "42,500", "color": "#0284c7", "ifsc": "SBIN0005678",
                    "transactions": [
                        {"merchant": "UPI Transfer - Rahul", "date": "Nov 4, 2023", "amount": "-₹1,200", "is_payment": False},
                        {"merchant": "Swiggy", "date": "Nov 3, 2023", "amount": "-₹450", "is_payment": False}
                    ]
                },
                {
                    "id": "bank_3", "bank_name": "ICICI Bank", "type": "Current", "masked_acc": "•••• 3344", 
                    "balance": "17,500", "color": "#ea580c", "ifsc": "ICIC0009101",
                    "transactions": [
                        {"merchant": "Client Payment", "date": "Nov 2, 2023", "amount": "+₹15,000", "is_payment": True},
                        {"merchant": "Office Supplies", "date": "Oct 28, 2023", "amount": "-₹3,500", "is_payment": False}
                    ]
                }
            ],
            "cash_flow": {
                "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                "income": [18000, 17000, 14000, 16000, 21000, 18000],
                "expenses": [14000, 15000, 9000, 11000, 16000, 10000]
            },
            "budget_overview": {
                "income_pct": 47,
                "expenses_pct": 33,
                "budget_pct": 20
            },
            "ai_insights": [
                {"icon": "fa-arrow-trend-up", "color": "green", "text": "Great job! Your savings rate is up 12% this month."},
                {"icon": "fa-triangle-exclamation", "color": "orange", "text": "High spend detected in 'Food & Dining' over the weekend."},
                {"icon": "fa-lightbulb", "color": "blue", "text": "You have ₹25,000 idle cash. Consider moving it to investments."}
            ]
        }

    return render_template('dashboard.html', 
                           user=user_name, 
                           is_bank_linked=is_bank_linked, 
                           data=dashboard_data)

@app.route('/finance')
def finance():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    
    if not session.get('is_bank_linked', False):
        flash("Please link your bank account first to unlock your Investment Portfolio.", "warning")
        return redirect(url_for('dashboard'))
    
    investment_data = {}
    try:
        with open("dashboard_processed.json", "r") as f:
            # Grab ONLY the finance half
            investment_data = json.load(f).get("finance_data", {}) 
    except FileNotFoundError:
        # --- STATIC INVESTMENT DATA (Modeled after parsed Setu JSON) ---
        investment_data = {
            "total_portfolio_value": "1,245,477",
            "day_change": "+2.4%",
            "growth_chart": {
                "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                "data": [500000, 520000, 480000, 600000, 750000, 800000, 850000, 920000, 950000, 1100000, 1150000, 1245477]
            },
            "asset_allocation": {
                "labels": ["Equities", "Mutual Funds", "Derivatives (F&O)"],
                "data": [55, 30, 15]
            },
            "holdings": [
                {"name": "Bera, Mangat and Kannan", "type": "Equity", "value": "₹343,400", "performance": "+15.2%", "trend": "up"},
                {"name": "Kothari Group MF", "type": "Mutual Fund", "value": "₹325,000", "performance": "-9.6%", "trend": "down"},
                {"name": "Vanguard Total Stock", "type": "ETF", "value": "₹145,000", "performance": "+113.0%", "trend": "up"},
                {"name": "Nifty 50 PUT Option", "type": "Derivative", "value": "₹45,500", "performance": "+4.2%", "trend": "up"}
            ],
            "ai_insights": [
                {"icon": "fa-scale-unbalanced", "color": "orange", "text": "High Risk Detected: 15% of your portfolio is in F&O Derivatives. Consider rebalancing."},
                {"icon": "fa-arrow-trend-down", "color": "blue", "text": "Kothari Group MF is underperforming its benchmark. Review fund manager changes."},
                {"icon": "fa-money-bill-trend-up", "color": "green", "text": "Tax Harvesting Opportunity: You have ₹25,000 in long-term unrealized gains."}
            ]
        }

    return render_template('finance.html', user=session['user_name'], data=investment_data)

@app.route('/credit-cards')
def credit_cards():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    
    if not session.get('is_bank_linked', False):
        flash("Please link your bank account first to unlock your Credit Cards.", "warning")
        return redirect(url_for('dashboard'))
    
    try:
        with open("dashboard_processed.json", "r") as f:
            cc_data = json.load(f).get("cc_data", {})
        
        # Assuming you store the bank data path in session after linking
        # json_path = session.get('bank_json_path', 'bank_data.json') 
        # result = run_pipeline(json_path)
        # shadow = result.shadow_cc  # This is the dict from feature_engineer.py
        
        # if shadow and shadow.get("detected"):
        #     # 2. Map Shadow Data to your Template Format
        #     cc_data = {
        #         "total_debt": f"{shadow['inferred_balance']:,.2f}",
        #         "debt_trend": "Inferred from Bank Decodes",
        #         "credit_score": 710, # Static or calculated
        #         "score_status": "Fair (Inferred)",
        #         "ai_insights": [
        #             {"icon": "fa-eye", "color": "blue", "text": f"Detected {shadow['detected_rows']} CC payments in your bank statement."},
        #             {"icon": "fa-chart-pie", "color": "orange", "text": f"Estimated utilization: {shadow['utilisation_pct']}% based on inferred limit."}
        #         ],
        #         "cards": [{
        #             "id": "shadow_1",
        #             "name": "Detected Credit Card",
        #             "network": "Inferred",
        #             "last4": "XXXX",
        #             "balance": f"{shadow['inferred_balance']:,.2f}",
        #             "due_date": "Derived from patterns",
        #             "limit": f"{shadow['estimated_limit']:,.0f}",
        #             "apr": "Market Avg (18-24%)",
        #             "color": "#2c3e50",
        #             "transactions": [
        #                 {
        #                     "merchant": t['label'], 
        #                     "date": "Estimated", 
        #                     "amount": f"-₹{t['amount']:,.2f}",
        #                     "category": t['category']
        #                 } for t in shadow['synthetic_transactions']
        #             ]
        #         }]
        #     }
        # else:
        #     raise ValueError("No CC data detected")
    except (FileNotFoundError, json.JSONDecodeError):
        # --- STATIC CREDIT CARD DATA ---
        cc_data = {
            "total_debt": "8,450",
            "debt_trend": "+1.2%",
            "debt_chart": [7200, 7100, 7400, 7900, 8200, 8450],
            "credit_score": 745,
            "score_status": "Very Good",
            "ai_insights": [
                {"icon": "fa-triangle-exclamation", "color": "orange", "text": "High utilization on Discover It (60%). Pay down $1,000 to boost your score."},
                {"icon": "fa-calendar-check", "color": "green", "text": "All upcoming payments are on track. No late fees predicted this month."},
                {"icon": "fa-lightbulb", "color": "blue", "text": "You could save $120/year in interest by moving your Chase balance to a 0% APR card."}
            ],
            "cards": [
                {
                    "id": "card_1",
                    "name": "Chase Sapphire Preferred",
                    "network": "Visa",
                    "last4": "4092",
                    "balance": "2,100",
                    "due_date": "Nov 15, 2023",
                    "limit": "10,000",
                    "apr": "19.99%",
                    "color": "#1a2a47", # Dark Blue
                    "transactions": [
                        {"merchant": "Uber Eats", "date": "Nov 3, 2023", "amount": "-$25.77"},
                        {"merchant": "Starbucks", "date": "Nov 1, 2023", "amount": "-$6.50"}
                    ]
                },
                {
                    "id": "card_2",
                    "name": "Amex Gold",
                    "network": "Amex",
                    "last4": "1002",
                    "balance": "1,500",
                    "due_date": "Nov 22, 2023",
                    "limit": "No Preset Limit",
                    "apr": "20.99%",
                    "color": "#d4af37", # Gold
                    "transactions": [
                        {"merchant": "Whole Foods", "date": "Nov 4, 2023", "amount": "-$145.00"},
                        {"merchant": "Payment Received", "date": "Nov 2, 2023", "amount": "+$500.00", "is_payment": True}
                    ]
                },
                {
                    "id": "card_3",
                    "name": "Discover It Cash Back",
                    "network": "Discover",
                    "last4": "8834",
                    "balance": "4,850",
                    "due_date": "Nov 18, 2023",
                    "limit": "8,000",
                    "apr": "23.99%",
                    "color": "#e57200", # Orange
                    "transactions": [
                        {"merchant": "Amazon", "date": "Oct 28, 2023", "amount": "-$89.99"},
                        {"merchant": "Netflix", "date": "Oct 25, 2023", "amount": "-$15.49"}
                    ]
                }
            ]
        }

    return render_template('credit-cards.html', user=session['user_name'], data=cc_data)

@app.route('/budget')
def budget():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    
    if not session.get('is_bank_linked', False):
        flash("Please link your bank account first to unlock the Budget Planner.", "warning")
        return redirect(url_for('dashboard'))
    

    full_budget_data = {}
    try:
        with open("dashboard_processed.json", "r") as f:
            full_data = json.load(f)
            full_budget_data = full_data.get("budget_data", {})
            # # We also need insights from the dashboard block
            # full_budget_data["ai_insights"] = full_data.get("dashboard_data", {}).get("ai_insights", [])
    except FileNotFoundError:
        # --- STATIC BUDGET DATA ---
        full_budget_data = {
            "monthly_allowance": "5,000",
            "total_spent": "3,850",
            "remaining": "1,150",
            "spent_pct": 77,
            "categories": [
                {"name": "Housing & Rent", "spent": 1500, "budget": 1500, "color": "#1a2a47", "icon": "fa-house", "over": False},
                {"name": "Food & Dining", "spent": 950, "budget": 600, "color": "#ef4444", "icon": "fa-utensils", "over": True},
                {"name": "Transportation", "spent": 300, "budget": 400, "color": "#3b82f6", "icon": "fa-car", "over": False},
                {"name": "Shopping", "spent": 850, "budget": 500, "color": "#f59e0b", "icon": "fa-bag-shopping", "over": True},
                {"name": "Bills & Utilities", "spent": 250, "budget": 300, "color": "#10b981", "icon": "fa-bolt", "over": False}
            ],
            "ai_insights": [
                {"icon": "fa-triangle-exclamation", "color": "orange", "text": "Alert: You have exceeded your Food & Dining budget by $350."},
                {"icon": "fa-scissors", "color": "red", "text": "Shopping expenses are '70%' higher than expected. Hold off on non-essentials."},
                {"icon": "fa-check", "color": "green", "text": "Great job on Utilities! You are projected to come in $50 under budget."}
            ]
        }

    return render_template('budget.html', user=session['user_name'], data=full_budget_data)

@app.route('/update-budget', methods=['POST'])
def update_budget():
    """Recalculates the entire dashboard based on the user's custom budget limit."""
    if 'user_name' not in session: return redirect(url_for('login'))
    
    new_budget_str = request.form.get('custom_budget', '0').replace(',', '')
    try:
        new_budget = float(new_budget_str)
    except ValueError:
        flash("Invalid budget amount.", "error")
        return redirect(url_for('budget'))

    try:
        with open("dashboard_processed.json", "r") as f:
            full_data = json.load(f)
            
        budget_data = full_data.get("budget_data")
        if not budget_data:
            return redirect(url_for('budget'))

        # --- 1. RECALCULATE TOP ROW ---
        actual_spent = float(budget_data["total_spent"].replace(',', ''))
        remaining = max(new_budget - actual_spent, 0)
        spent_pct = min(round((actual_spent / new_budget) * 100), 100) if new_budget > 0 else 100
        
        from datetime import datetime
        import calendar
        now = datetime.now()
        days_left = max(calendar.monthrange(now.year, now.month)[1] - now.day, 1)
        safe_daily = remaining / days_left
        
        trajectory_status = "On Track"
        trajectory_color = "#10b981"
        if actual_spent > (new_budget * (now.day / calendar.monthrange(now.year, now.month)[1])):
             trajectory_status = "Running Hot"
             trajectory_color = "#ef4444"

        # Update the dictionary
        budget_data["monthly_allowance"] = f"{new_budget:,.0f}"
        budget_data["remaining"] = f"{remaining:,.0f}"
        budget_data["spent_pct"] = spent_pct
        budget_data["safe_daily"] = f"{safe_daily:,.0f}"
        budget_data["trajectory_status"] = trajectory_status
        budget_data["trajectory_color"] = trajectory_color

        # --- 2. RECALCULATE CATEGORIES PROPORTIONALLY ---
        old_budget = sum(c["budget"] for c in budget_data["categories"])
        scale_factor = new_budget / old_budget if old_budget > 0 else 1

        for cat in budget_data["categories"]:
            cat["budget"] = cat["budget"] * scale_factor
            cat["spent_pct"] = min((cat["spent"] / cat["budget"]) * 100, 100) if cat["budget"] > 0 else 100
            cat["over"] = bool(cat["spent"] > cat["budget"])

        # Save it all back!
        with open("dashboard_processed.json", "w") as f:
            json.dump(full_data, f, indent=4)
            
        flash("Budget updated successfully! AI has recalibrated your metrics.", "success")
        
    except Exception as e:
        print(f"Error updating budget: {e}")
        flash("Failed to update budget.", "error")

    return redirect(url_for('budget'))

from datetime import datetime, timedelta, timezone
@app.route('/connect-bank')
def connect_bank():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    
    # --- 1. GET DYNAMIC VUA (Mobile Number) ---
    user_email = session.get('user_email')
    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT mobilenumber FROM users WHERE email=?", (user_email,))
    user_row = cursor.fetchone()
    conn.close()

    if not user_row:
        flash("User details not found.", "error")
        return redirect(url_for('dashboard'))
        
    mobile_number = user_row[0]
    dynamic_vua = str(mobile_number)

    # --- 2. GET DYNAMIC DATES (Last 6 Months) ---
    now = datetime.now(timezone.utc)
    six_months_ago = now - timedelta(days=180)
    
    # Format to ISO-8601 required by Setu (e.g., 2023-01-01T00:00:00Z)
    dynamic_to = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    dynamic_from = six_months_ago.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ⚠️ SANDBOX OVERRIDE: 
    # If the dynamic dates (2026) return empty data from Setu, 
    # uncomment these two lines to force the 2023 mock data:
    # dynamic_to = "2023-04-01T00:00:00Z"
    # dynamic_from = "2023-01-01T00:00:00Z"
    session['setu_date_from'] = dynamic_from
    session['setu_date_to'] = dynamic_to

    url_consent = "https://fiu-sandbox.setu.co/v2/consents"
    
    # We use your exact tested payload
    payload_consent = {
        "consentMode": "STORE",
        "fetchType": "PERIODIC",
        "frequency": { "unit": "HOUR", "value": 10 },
        "consentTypes": ["TRANSACTIONS", "PROFILE", "SUMMARY"],
        "vua": dynamic_vua,
        "dataRange": {
            "from": dynamic_from,
            "to": dynamic_to
        },
        "consentDuration": { "unit": "MONTH", "value": "12" },
        "purpose": {
            "code": "102",
            "text": "Customer spending and budget analysis",
            "category": { "type": "PERSONAL_FINANCE" },
            "refUri": "https://api.rebit.org.in/aa/purpose/102.xml"
        },
        "fiTypes": ["DEPOSIT", "MUTUAL_FUNDS", "EQUITIES"],
        # CRITICAL: This is where Setu sends the user AFTER they approve!
        "redirectUrl": "http://127.0.0.1:5000/setu-callback" 
    }

    try:
        resp = requests.post(url_consent, json=payload_consent, headers=SETU_HEADERS)
        if resp.status_code == 201:
            data = resp.json()
            session['pending_consent_id'] = data['id'] # Save ID in session
            return redirect(data['url']) # Send user to Setu
        else:
            return f"Consent Failed: {resp.text}", 400
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/setu-callback')
def setu_callback():
    """Setu redirects the user here after they approve the consent."""
    consent_id = session.get('pending_consent_id')

    # Handle missing consent ID gracefully
    if not consent_id:
        flash("No pending bank connection found. Please try again.", "warning")
        return redirect(url_for('dashboard'))
    

    # 1. Verify Consent is Active
    url_consent_status = f"https://fiu-sandbox.setu.co/v2/consents/{consent_id}"
    status_resp = requests.get(url_consent_status, headers=SETU_HEADERS)
    
    if status_resp.json().get("status") != "ACTIVE":
        flash("Bank connection was not approved. Please try again.", "error")
        return redirect(url_for('dashboard'))
    
    dynamic_from = session.get('setu_date_from', "2023-01-01T00:00:00Z")
    dynamic_to = session.get('setu_date_to', "2023-04-01T00:00:00Z")
    
    # ⚠️ SANDBOX OVERRIDE: Ensure this matches what you used in /connect-bank
    # dynamic_to = "2023-04-01T00:00:00Z"
    # dynamic_from = "2023-01-01T00:00:00Z"
    
    # 2. Create Data Session
    url_session = "https://fiu-sandbox.setu.co/v2/sessions"
    payload_session = {
        "consentId": consent_id, 
        "dataRange": {
            "from": dynamic_from,
            "to": dynamic_to
        },
        "format": "json"
    }
    
    sess_resp = requests.post(url_session, json=payload_session, headers=SETU_HEADERS)
    if sess_resp.status_code != 201:
        return f"Session Failed: {sess_resp.text}", 400
        
    session_id = sess_resp.json()['id']

    # 3. Give Setu a split second to prepare the data, then Fetch it!
    time.sleep(2) 
    url_fetch = f"https://fiu-sandbox.setu.co/v2/sessions/{session_id}"
    fetch_resp = requests.get(url_fetch, headers=SETU_HEADERS)
    
    if fetch_resp.status_code == 200:

        ### ye hai static data ko acchese categories me dekhane ke liye
        # import shutil
        # if os.path.exists("bank_data_synthetic.json"):
        #     shutil.copy("bank_data_synthetic.json", "bank_data.json")
        #     print("Loaded Golden Path Data: bank_data_synthetic.json")
        # else:
        #     # Fallback just in case
        #     with open("bank_data.json", "w") as f:
        #         json.dump(fetch_resp.json(), f, indent=4)

        bank_data = fetch_resp.json()
        
        # Save the JSON file securely to your project folder
        with open("bank_data.json", "w") as f:
            json.dump(bank_data, f, indent=4)

        # --- NEW: Run the AI Pipeline! ---
        print("Running AI Pipeline...")
        process_and_cache_data("bank_data.json")

        # 1. Update the active session so the UI unlocks instantly
        session['is_bank_linked'] = True
        
        # 2. PERMANENTLY save it in the Database!
        user_email = session.get('user_email')
        if user_email:
            conn = sqlite3.connect('finance.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_bank_linked = 1 WHERE email = ?", (user_email,))
            conn.commit()
            conn.close()
        
        flash("Bank account linked successfully!", "success")
        # Redirect the user back to their dashboard!
        return redirect(url_for('dashboard'))
    else:
        return f"Failed to fetch data: {fetch_resp.text}", 400

@app.route('/api/chat', methods=['POST'])
def api_chat():
    if 'user_name' not in session:
        return {"error": "Unauthorized"}, 401
        
    data = request.json
    user_message = data.get("message", "")
    history = data.get("history", [])
    
    # Check if bank is linked!
    if not session.get('is_bank_linked', False):
         return {
             "reply": "Bhai, you haven't linked your bank account yet! I need your data to give you proper advice. Go to the dashboard and link it first.", 
             "history": history
         }

    # Call Gemini
    gemini_key = os.getenv("GEMINI_API_KEY")
    result = get_chat_reply(user_message, history, gemini_key)
    
    return result

@app.route('/security')
def security():

    if 'user_name' not in session:
        return redirect(url_for('login'))
    
    if not session.get('is_bank_linked', False):
        flash("Please link your bank account first to view Security Alerts.", "warning")
        return redirect(url_for('dashboard'))
    
    anomaly_data = []
    try:
        with open("dashboard_processed.json", "r") as f:
            full_data = json.load(f)
            # Fetch the anomalies we saved earlier in dashboard_data
            anomaly_data = full_data.get("dashboard_data", {}).get("recent_anomalies", [])
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    return render_template('security.html', user=session['user_name'], anomalies=anomaly_data)

if __name__ == '__main__':
    print("🚀 FLASK APP RUNNING ON http://127.0.0.1:5000")
    app.run(debug=True,use_reloader=False)