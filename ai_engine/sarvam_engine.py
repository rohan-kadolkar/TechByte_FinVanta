"""
ai_engine/sarvam_engine.py
────────────────────────────────────────────────────────────────
FinDost — Multilingual (English / Hindi / Marathi / Kannada)
voice + text AI powered by Sarvam AI APIs.

Pipeline:
  Voice: Audio → Saaras v3 (STT) → Sarvam LLM → Bulbul v3 (TTS) → Base64 Audio
  Text:  Text  → Sarvam LLM → Text response only

Language Detection: Strictly mirrors user's input language.
────────────────────────────────────────────────────────────────
"""

import json
import requests

# ─────────────────────────────────────────────────────────────
# SARVAM API ENDPOINTS
# ─────────────────────────────────────────────────────────────
SARVAM_BASE   = "https://api.sarvam.ai"
STT_ENDPOINT  = f"{SARVAM_BASE}/speech-to-text-translate"
CHAT_ENDPOINT = f"{SARVAM_BASE}/v1/chat/completions"
TTS_ENDPOINT  = f"{SARVAM_BASE}/text-to-speech"

STT_MODEL     = "saaras:v3"
CHAT_MODEL    = "sarvam-m"
TTS_MODEL     = "bulbul:v3"

# ─────────────────────────────────────────────────────────────
# ROUTE → JSON KEY MAPPING
# ─────────────────────────────────────────────────────────────
ROUTE_CONTEXT_MAP = {
    "/dashboard":    "dashboard_data",
    "/finance":      "finance_data",
    "/budget":       "budget_data",
    "/credit-cards": "cc_data",
}

# ─────────────────────────────────────────────────────────────
# LANGUAGE → TTS BCP-47 CODE
# ─────────────────────────────────────────────────────────────
LANG_TO_TTS_CODE = {
    "hindi":    "hi-IN",
    "english":  "en-IN",
    "marathi":  "mr-IN",
    "kannada":  "kn-IN",
    "hinglish": "hi-IN",
}

# STT language_code → normalised name (for TTS lookup)
STT_CODE_TO_LANG = {
    "hi-IN": "hindi",
    "en-IN": "english",
    "mr-IN": "marathi",
    "kn-IN": "kannada",
    "en-US": "english",
}

# ─────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────
FINDOST_SYSTEM_PROMPT = """You are FinDost, a witty, warm, and genuinely helpful Indian financial expert embedded in a personal finance dashboard.

══ RULE 1 — LANGUAGE MIRROR (CRITICAL, NON-NEGOTIABLE) ══
Detect the exact language the user is writing or speaking in. Your reply MUST be in that EXACT same language.
- User writes in English  → reply ONLY in English
- User writes in Hindi    → reply ONLY in Hindi (Devanagari)
- User writes in Marathi  → reply ONLY in Marathi (Devanagari)
- User writes in Kannada  → reply ONLY in Kannada (ಕನ್ನಡ script)
- Hindi + English mix     → reply in same Hinglish mix
NEVER default to Hindi. NEVER switch languages. Mirror exactly.
On your very first line, write: LANG:<english|hindi|marathi|kannada|hinglish>
Then write your answer from the next line onward. The LANG tag will be stripped before showing to the user.

══ RULE 2 — CONTEXT-AWARE ══
Use the financial data in [PAGE CONTEXT] to give specific, number-backed answers.
Use Indian number formatting: Lakhs (₹1,00,000) and Crores (₹1,00,00,000).

══ RULE 3 — INDIAN TERMINOLOGY ══
Use: SIP, EMI, FD, RD, CIBIL score, GST, Nifty, Sensex, UPI where relevant.

══ RULE 4 — CONCISE ══
3 sentences max for simple queries. Direct. No jargon.

══ RULE 5 — PERSONA ══
Friendly desi mentor. Witty but never preachy. Like a CA friend over chai.

[PAGE CONTEXT] is below. Always ground your answer in it."""


# ─────────────────────────────────────────────────────────────
# MAIN ENGINE
# ─────────────────────────────────────────────────────────────

class FinDostEngine:
    """
    Dual-mode (voice + text) multilingual financial AI engine.

    Parameters
    ──────────
    api_key        : str  — Sarvam AI API key
    data_file_path : str  — Path to dashboard_processed.json
    tts_voice      : str  — "Ritu" (female) or "Shubh" (male)
    """

    def __init__(
        self,
        api_key: str,
        data_file_path: str = "dashboard_processed.json",
        tts_voice: str = "Ritu",
    ):
        self.api_key = api_key
        self.data_file_path = data_file_path
        self.tts_voice = tts_voice
        self._headers = {
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
        }

    # ──────────────────────────────────────────────
    # PUBLIC: Voice pipeline
    # ──────────────────────────────────────────────

    def process_voice(self, audio_bytes: bytes, current_path: str) -> dict:
        """Audio → STT → LLM → TTS. Returns audio_base64 + texts."""
        transcript, stt_lang_code, err = self._transcribe(audio_bytes)
        if err:
            return self._err(err)
        if not transcript.strip():
            return self._err("Kuch sunai nahi diya. Phir se boliye!")

        context = self._get_context(current_path)
        ai_text, detected_lang, err = self._chat(transcript, context)
        if err:
            return self._err(err)

        # Resolve TTS language: prefer LLM-detected lang, fallback to STT lang code
        tts_lang = LANG_TO_TTS_CODE.get(
            detected_lang,
            STT_CODE_TO_LANG.get(stt_lang_code, "hi-IN")
        )
        # Convert name back to BCP-47 if needed
        if tts_lang in LANG_TO_TTS_CODE:
            tts_lang = LANG_TO_TTS_CODE[tts_lang]

        audio_b64, err = self._synthesize(ai_text, tts_lang)
        if err:
            # Text still returned even if TTS fails
            return {"user_text": transcript, "ai_response": ai_text, "audio_base64": "", "error": f"TTS: {err}"}

        return {"user_text": transcript, "ai_response": ai_text, "audio_base64": audio_b64, "error": ""}

    # ──────────────────────────────────────────────
    # PUBLIC: Text pipeline
    # ──────────────────────────────────────────────

    def process_text(self, user_text: str, current_path: str) -> dict:
        """Text → LLM → text response only (no TTS)."""
        if not user_text.strip():
            return self._err("Please type something!")

        context = self._get_context(current_path)
        ai_text, _, err = self._chat(user_text, context)
        if err:
            return self._err(err)

        return {"user_text": user_text, "ai_response": ai_text, "audio_base64": "", "error": ""}

    # ──────────────────────────────────────────────
    # PUBLIC: Context loader (also used externally)
    # ──────────────────────────────────────────────

    def get_section_context(self, route_name: str) -> str:
        return self._get_context(route_name)

    # ──────────────────────────────────────────────
    # PRIVATE: Context
    # ──────────────────────────────────────────────

    def _get_context(self, route_name: str) -> str:
        clean = route_name.rstrip("/").lower() or "/dashboard"
        key = ROUTE_CONTEXT_MAP.get(clean, "dashboard_data")
        try:
            with open(self.data_file_path, "r", encoding="utf-8") as f:
                master = json.load(f)
            return json.dumps(master.get(key, {}), ensure_ascii=False, separators=(",", ":"))
        except FileNotFoundError:
            return json.dumps({"info": "Financial data not yet loaded. Ask user to link their bank."})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ──────────────────────────────────────────────
    # PRIVATE: STT — Saaras v3
    # ──────────────────────────────────────────────

    def _transcribe(self, audio_bytes: bytes) -> tuple:
        """Returns (transcript, language_code, error_str)"""
        try:
            files   = {"file": ("audio.webm", audio_bytes, "audio/webm")}
            data    = {"model": STT_MODEL, "with_disfluencies": "false"}
            headers = {"api-subscription-key": self.api_key}

            resp = requests.post(STT_ENDPOINT, headers=headers, files=files, data=data, timeout=30)
            if resp.status_code != 200:
                return "", "", f"STT error {resp.status_code}: {resp.text[:200]}"

            result      = resp.json()
            transcript  = result.get("transcript", "").strip()
            lang_code   = result.get("language_code", "hi-IN")
            return transcript, lang_code, ""

        except requests.exceptions.Timeout:
            return "", "", "STT timed out. Please try again."
        except Exception as e:
            return "", "", f"STT exception: {e}"

    # ──────────────────────────────────────────────
    # PRIVATE: LLM — Sarvam-m
    # ──────────────────────────────────────────────

    def _chat(self, user_text: str, context_json: str) -> tuple:
        """Returns (ai_response_text, detected_language_name, error_str)"""
        try:
            system_msg = FINDOST_SYSTEM_PROMPT + f"\n\n{context_json}"

            payload = {
                "model": CHAT_MODEL,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": user_text},
                ],
                "max_tokens": 350,
                "temperature": 0.65,
            }

            resp = requests.post(CHAT_ENDPOINT, headers=self._headers, json=payload, timeout=45)
            if resp.status_code != 200:
                return "", "", f"LLM error {resp.status_code}: {resp.text[:200]}"

            raw = (
                resp.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
            )

            # Parse LANG tag from first line
            detected_lang = "hindi"
            lines = raw.split("\n", 1)
            if lines[0].upper().startswith("LANG:"):
                detected_lang = lines[0].split(":", 1)[1].strip().lower()
                ai_text = lines[1].strip() if len(lines) > 1 else ""
            else:
                ai_text = raw

            return ai_text, detected_lang, ""

        except requests.exceptions.Timeout:
            return "", "", "AI response timed out."
        except Exception as e:
            return "", "", f"LLM exception: {e}"

    # ──────────────────────────────────────────────
    # PRIVATE: TTS — Bulbul v3
    # ──────────────────────────────────────────────

    def _synthesize(self, text: str, target_lang_code: str = "hi-IN") -> tuple:
        """Returns (base64_wav_string, error_str)"""
        try:
            payload = {
                "inputs": [text[:490]],
                "target_language_code": target_lang_code,
                "speaker": self.tts_voice,
                "model": TTS_MODEL,
                "enable_preprocessing": True,
            }
            resp = requests.post(TTS_ENDPOINT, headers=self._headers, json=payload, timeout=30)
            if resp.status_code != 200:
                return "", f"TTS error {resp.status_code}: {resp.text[:200]}"

            audios = resp.json().get("audios", [])
            return (audios[0], "") if audios else ("", "TTS returned empty audio list.")

        except requests.exceptions.Timeout:
            return "", "TTS timed out."
        except Exception as e:
            return "", f"TTS exception: {e}"

    # ──────────────────────────────────────────────
    # PRIVATE: Error shape
    # ──────────────────────────────────────────────

    @staticmethod
    def _err(msg: str) -> dict:
        return {"user_text": "", "ai_response": msg, "audio_base64": "", "error": msg}