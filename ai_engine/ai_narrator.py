"""
ai_narrator.py
────────────────────────────────────────────────────────────────
Gen-Z Wealth Coach narrator powered by Gemini.

Features a Context-Aware Router that detects which tab the user 
is viewing (Dashboard, Finance, Budget, CC) and generates 3 
hyper-specific, punchy insights based on that tab's data.

Public API
──────────
    from ai_narrator import get_insights_for_tab
    
    # Returns a list of UI-ready dictionaries: [{"icon": ..., "color": ..., "text": ...}]
    insights = get_insights_for_tab("budget", budget_data_dict, api_key="YOUR_GEMINI_KEY")
────────────────────────────────────────────────────────────────
"""

import json

# ─────────────────────────────────────────────────────────────────────────────
# 1. THE BASE PERSONA
# ─────────────────────────────────────────────────────────────────────────────
BASE_PERSONA = """
You are NeuralFi's Gen-Z Wealth Coach — brutally honest, hype-free, and
genuinely rooting for the user's bag. You speak in short, punchy sentences.
No fluff. No corporate jargon. No emojis overload — one per bullet max.

YOUR TASK: Reply with EXACTLY 3 bullet points. No intro sentence. No sign-off.
Each bullet must start with a standard bullet point character "•".
Use the Indian Rupee symbol ₹ for all amounts and format with commas (e.g. ₹1,20,000).
NEVER mention "JSON", "data", "fields", or technical terms. Speak directly to the user.
"""

# ─────────────────────────────────────────────────────────────────────────────
# 2. TAB-SPECIFIC ROUTING PROMPTS
# ─────────────────────────────────────────────────────────────────────────────
PROMPTS = {
    "dashboard": BASE_PERSONA + """
You are looking at the user's high-level DASHBOARD.
You will receive their net_worth, recent cash_flow (income vs expenses), and budget overview.
• Bullet 1: Diagnose their Net Worth and Cash Flow gap. Are they stacking cash or bleeding it?
• Bullet 2: Look at their budget_pct. If it's high, warn them. If low, praise the discipline.
• Bullet 3: Give one hard-hitting, tactical piece of advice for the upcoming week based on this summary.
""",

    "finance": BASE_PERSONA + """
You are looking at the user's FINANCE (Investments) portfolio.
You will receive their total_portfolio_value, day_change, asset_allocation (Equities vs MFs), and top holdings.
• Bullet 1: Address their total portfolio value and day change. Hype the gains or contextualize the dips.
• Bullet 2: Critique their asset allocation. If they are 100% Equities, warn about volatility. If they have too much in low-growth, tell them to take some calculated risks.
• Bullet 3: Call out one of their top holdings by name and give a realistic, hype-free observation about holding it long-term.
""",

    "budget": BASE_PERSONA + """
You are looking at the user's AI BUDGET.
You will receive their total allowance, safe_daily spend limit, golden_ratio (needs/wants/savings), and top categories.
• Bullet 1: Look at the golden_ratio. If 'wants' is > 30%, roast them slightly. If 'savings' is > 20%, hype them up.
• Bullet 2: Call out their highest spending category by name. Tell them exactly how much they could save if they trimmed it by 20%.
• Bullet 3: Highlight their "safe_daily" limit. Make it real for them (e.g., "That's two coffees and a cab ride. Pace yourself.")
""",

    "cc": BASE_PERSONA + """
You are looking at the user's CREDIT CARDS & SHADOW DEBT.
You will receive their total_debt, credit_score, and any AI-detected shadow credit cards.
• Bullet 1: Address their credit score. If >750, call it a flex. If <700, tell them they are leaking money to interest rates.
• Bullet 2: If there is a "Shadow CC" or high total debt, call it out as a "ghost trap" stealing their future wealth.
• Bullet 3: Give exactly one aggressive, actionable step to pay down their balances this month.
"""
}


# ─────────────────────────────────────────────────────────────────────────────
# 3. UI FORMATTER & FALLBACK GENERATOR
# ─────────────────────────────────────────────────────────────────────────────
def _format_for_ui(text_bullets: str) -> list:
    """Converts the LLM's text string into the list of dicts the HTML expects."""
    lines = [line.strip().lstrip("•").strip() for line in text_bullets.split('\n') if line.strip()]
    
    # Ensure we only ever return exactly 3 UI cards
    insights = []
    styles = [
        {"icon": "fa-bullseye", "color": "blue"},
        {"icon": "fa-triangle-exclamation" if "!" in lines[0] or "warning" in lines[0].lower() else "fa-bolt", "color": "orange"},
        {"icon": "fa-arrow-trend-up", "color": "green"}
    ]
    
    for i, line in enumerate(lines[:3]):
        insights.append({
            "icon": styles[i % 3]["icon"],
            "color": styles[i % 3]["color"],
            "text": line
        })
    return insights

def _get_fallback_insights(mode: str) -> list:
    """Returns ultra-safe, UI-ready fallbacks if the API crashes or is missing."""
    fallbacks = {
        "dashboard": [
            {"icon": "fa-wallet", "color": "blue", "text": "AI cash-flow analysis is currently processing. Check back soon."},
            {"icon": "fa-magnifying-glass-chart", "color": "orange", "text": "Tracking your income vs expenses is step one to building a massive safety net."},
            {"icon": "fa-arrow-trend-up", "color": "green", "text": "Consistent tracking leads to consistent wealth. You're in the right place."}
        ],
        "finance": [
            {"icon": "fa-chart-pie", "color": "blue", "text": "A diversified portfolio is the ultimate cheat code against market volatility."},
            {"icon": "fa-scale-balanced", "color": "orange", "text": "Reviewing your asset allocation monthly ensures you never take on invisible risk."},
            {"icon": "fa-seedling", "color": "green", "text": "Time in the market beats timing the market. Keep stacking those assets."}
        ],
        "budget": [
            {"icon": "fa-scale-unbalanced", "color": "blue", "text": "Aim for the 50/30/20 rule: 50% Needs, 30% Wants, 20% Savings."},
            {"icon": "fa-scissors", "color": "orange", "text": "Trimming just 15% off your top spending category can double your investment capital."},
            {"icon": "fa-calendar-check", "color": "green", "text": "Sticking to your safe daily spend limit mathematically guarantees you end the month in the green."}
        ],
        "cc": [
            {"icon": "fa-credit-card", "color": "blue", "text": "Keeping utilization under 30% is the fastest way to hack your credit score."},
            {"icon": "fa-user-secret", "color": "orange", "text": "AI is scanning your bank statements for hidden credit card bills..."},
            {"icon": "fa-fire-flame-curved", "color": "green", "text": "Paying your statement balance in full is a guaranteed 20% return on your money."}
        ]
    }
    return fallbacks.get(mode, fallbacks["dashboard"])


# ─────────────────────────────────────────────────────────────────────────────
# 4. MAIN EXPORT: THE CONTEXT ROUTER
# ─────────────────────────────────────────────────────────────────────────────
def get_insights_for_tab(mode: str, tab_data: dict, api_key: str) -> list:
    """
    Calls Gemini using the specific prompt for the given tab.
    Returns a list of dictionaries ready to drop straight into the HTML template.
    """
    if not api_key:
        print(f"[ai_narrator] No API key provided for {mode}. Using fallback.")
        return _get_fallback_insights(mode)

    system_instruction = PROMPTS.get(mode, PROMPTS["dashboard"])
    user_message = (
        f"Here is the user's {mode.upper()} data. Generate the 3 bullet points now.\n\n"
        + json.dumps(tab_data, indent=2, ensure_ascii=False)
    )

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        # We use gemini-1.5-flash as it is lightning fast for small context text-generation
        gemini = genai.GenerativeModel(
            model_name="gemini-2.5-flash", 
            system_instruction=system_instruction
        )
        
        response = gemini.generate_content(user_message)
        raw_text = response.text.strip()
        
        # Format it into the UI dictionaries
        return _format_for_ui(raw_text)

    except ImportError:
        print("[ai_narrator] google-generativeai not installed. Using fallback.")
        return _get_fallback_insights(mode)
    except Exception as exc:
        print(f"[ai_narrator] Gemini call failed for {mode}: {exc}")
        return _get_fallback_insights(mode)