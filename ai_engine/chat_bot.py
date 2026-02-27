import json
import os

_SYSTEM_PROMPT = """
You are FinVanta — a witty, sharp, and genuinely caring Indian financial advisor chatbot.
You are embedded inside a personal finance dashboard and you have REAL access to the user's
bank data, spending patterns, budgets, and credit card info.

YOUR PERSONALITY:
- Friendly but brutally honest. You are not a yes-man.
- Use Hinglish (Hindi + English mix) occasionally to sound like a trusted desi mentor.
  Examples: "Bhai,", "yaar,", "seedha baat", "iska matlab", "soch ke dekh"
- Keep responses concise (3-5 sentences max).
- Use ₹ for all Indian Rupee amounts with Indian comma formatting (e.g. ₹1,20,000).
- No corporate jargon. Speak directly like a friend who happens to be a CA.

DECISION LOGIC — When user asks "Can I buy / afford X?":
1. Check their 'remaining_budget' and 'safe_daily' limit from the CONTEXT.
2. If the item costs more than their remaining budget -> ❌ "Bhai, zero chance. Wait till next month."
3. If the item costs more than 5x their safe_daily limit -> ⚠️ "Yaar, you can, but it's going to make the rest of the month very tight."
4. If it's well within budget -> ✅ "Go for it!"

IMPORTANT:
- NEVER make up numbers. Only use figures provided in the FINANCIAL CONTEXT block.
- Do NOT repeat the context data back verbatim. Synthesise it naturally.
- Format beautifully with short paragraphs.
"""

def _build_context() -> str:
    """Reads the lightweight JSON file and feeds it to Gemini."""
    try:
        if not os.path.exists("dashboard_processed.json"):
            return "{ 'status': 'No bank connected yet.' }"
            
        with open("dashboard_processed.json", "r") as f:
            data = json.load(f)
            
        # Extract only what the bot needs to know to keep the prompt fast
        dash = data.get("dashboard_data", {})
        budget = data.get("budget_data", {})
        cc = data.get("cc_data", {})
        
        context = {
            "net_worth": dash.get("net_worth"),
            "monthly_budget_allowance": budget.get("monthly_allowance"),
            "amount_spent_this_month": budget.get("total_spent"),
            "remaining_budget": budget.get("remaining"),
            "safe_daily_spend_limit": budget.get("safe_daily"),
            "budget_trajectory": budget.get("trajectory_status"),
            "credit_card_debt": cc.get("total_debt"),
            "credit_score": cc.get("credit_score")
        }
        return json.dumps(context, indent=2)
    except Exception as e:
        return f"{{ 'error': 'Could not load context: {e}' }}"

class FinanceBot:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.context_snapshot = _build_context()
        self._model = None

        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                # Using the fast 2.5 flash model!
                self._model = genai.GenerativeModel(
                    model_name="gemini-2.5-flash",
                    system_instruction=_SYSTEM_PROMPT,
                )
            except Exception as exc:
                print(f"[FinanceBot] Gemini init failed: {exc}")

    def chat(self, user_message: str, history: list) -> tuple[str, list]:
        if not self._model:
            return "Setu-AI is offline (API key missing).", history

        try:
            # If new conversation, inject the financial context secretly
            if not history:
                grounding_message = (
                    "Here is the user's current financial snapshot. Use this as ground truth:\n"
                    f"```json\n{self.context_snapshot}\n```\n\n"
                    f"User's first question: {user_message}"
                )
                history.append({"role": "user", "parts": [grounding_message]})
            else:
                history.append({"role": "user", "parts": [user_message]})

            chat_session = self._model.start_chat(history=history[:-1])
            response = chat_session.send_message(history[-1]["parts"][0])
            reply_text = response.text.strip()

            history.append({"role": "model", "parts": [reply_text]})
            
            # Keep history bounded (last 10 messages)
            if len(history) > 10:
                history = history[:1] + history[-9:]

            return reply_text, history

        except Exception as exc:
            print(f"[FinanceBot] Error: {exc}")
            return "Bhai, server thoda busy hai. Give me a second and try again!", history

def get_chat_reply(user_message: str, history: list, api_key: str) -> dict:
    """Wrapper to be called by Flask."""
    bot = FinanceBot(api_key)
    reply, updated_history = bot.chat(user_message, history)
    return {
        "reply": reply,
        "history": updated_history
    }