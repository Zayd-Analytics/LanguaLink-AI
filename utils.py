# utils.py
import os
import json
import re
from dotenv import load_dotenv
load_dotenv()  # be safe if app didn't load .env early

import google.generativeai as genai
from langdetect import detect, DetectorFactory
from deep_translator import GoogleTranslator

DetectorFactory.seed = 0

# Try to configure Gemini; if missing, leave gemini_model = None
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
gemini_model = None
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        gemini_model = genai.GenerativeModel("gemini-pro")
    except Exception:
        gemini_model = None

# Map UI language names to deep-translator codes (common ones)
LANG_NAME_TO_CODE = {
    "spanish": "es",
    "french": "fr",
    "hindi": "hi",
    "arabic": "ar",
    "english": "en",
    "german": "de",
    "urdu": "ur",
    "japanese": "ja",
    "chinese (simplified)": "zh-CN",
    "portuguese": "pt",
    "russian": "ru",
}

LANG_CODE_TO_NAME = {v: k.capitalize() for k, v in LANG_NAME_TO_CODE.items()}


# ---------- Language detection ----------
def detect_language(text, return_name=False):
    try:
        code = detect(text)
    except Exception:
        code = "unknown"
    # normalize codes
    name = LANG_CODE_TO_NAME.get(code, code)
    return (code, name) if return_name else code


# ---------- Translation (using deep-translator) ----------
def translate_text(text, target_lang_name="English"):
    """
    target_lang_name is the UI name (e.g., 'Hindi', 'Spanish').
    We convert to a language code for the translator.
    Returns (translated_text, pronunciation_placeholder).
    """
    target_code = LANG_NAME_TO_CODE.get(target_lang_name.strip().lower(), target_lang_name)
    try:
        translated = GoogleTranslator(source="auto", target=target_code).translate(text)
    except Exception:
        # fallback: try Gemini (if available) to do a translation
        if gemini_model:
            try:
                prompt = f"Translate the following text to {target_lang_name}:\n\n{text}\n\nRespond with the translation only."
                resp = gemini_model.generate_content(prompt)
                # try to clean the response
                t = resp.text.strip()
                t = re.sub(r"^```(?:\w+)?|```$", "", t).strip()
                return t, "N/A"
            except Exception:
                pass
        # last fallback: return original text
        translated = text
    return translated, "N/A"


# ---------- Grammar notes (use Gemini if available, else heuristic) ----------
def get_grammar_notes(user_text, target_lang="English"):
    if gemini_model:
        try:
            prompt = (
                f"You are a helpful language tutor. The user wrote: \"{user_text}\".\n"
                f"Explain grammar points, mistakes, or improvements in short bullet points in {target_lang}.\n"
                "Keep it simple and learner-friendly (1-3 short bullets)."
            )
            resp = gemini_model.generate_content(prompt)
            text = resp.text.strip()
            text = re.sub(r"^```(?:\w+)?|```$", "", text).strip()
            return text
        except Exception:
            pass

    # simple heuristic fallback
    tips = []
    if user_text and user_text[0].islower():
        tips.append("Start sentences with a capital letter.")
    if user_text and not user_text.strip().endswith((".", "?", "!")):
        tips.append("Consider ending with punctuation (., ?, !).")
    if len(user_text.split()) < 3:
        tips.append("Short phrase — practice expanding it.")
    return " ".join(tips) if tips else "Looks fine for now."


# ---------- Quiz generator (Gemini -> JSON) ----------
def generate_quiz(target_lang="Spanish", level="Beginner", n_questions=3):
    """
    Try Gemini to produce a JSON list. If it fails, build a fallback quiz using deep-translator.
    Each item: {question, options, answer_index}
    """
    if gemini_model:
        try:
            prompt = (
                f"Generate {n_questions} multiple-choice questions for learners of {target_lang} "
                f"(level: {level}). Each question should ask to translate a short English phrase into {target_lang}. "
                "Return a JSON array only, like:\n"
                "[{\"question\":\"Translate 'Hello' into Spanish\",\"options\":[\"Hola\",\"Adiós\",\"Gracias\"],\"answer_index\":0}]"

            )
            resp = gemini_model.generate_content(prompt)
            text = resp.text.strip()
            text = re.sub(r"^```(?:json)?|```$", "", text).strip()
            quiz = json.loads(text)
            # validate quiz shape
            if isinstance(quiz, list) and all("question" in q and "options" in q and "answer_index" in q for q in quiz):
                return quiz
        except Exception:
            pass

    # fallback: dynamic generation using deep-translator
    common_phrases = ["Hello", "Thank you", "Where is the bathroom?", "Good morning", "See you later", "Please"]
    quiz = []
    import random
    random.shuffle(common_phrases)
    for phrase in common_phrases[:n_questions]:
        correct, _ = translate_text(phrase, target_lang)
        # distractors: translate other phrases
        distractors = []
        pool = [p for p in common_phrases if p != phrase]
        random.shuffle(pool)
        for alt in pool[:3]:
            alt_tr, _ = translate_text(alt, target_lang)
            if alt_tr != correct:
                distractors.append(alt_tr)
        # ensure at least 3 options
        options = [correct] + distractors
        # dedupe and ensure length 3 (pad if needed)
        options = list(dict.fromkeys(options))  # preserve order, remove duplicates
        while len(options) < 3:
            options.append("—")
        random.shuffle(options)
        answer_index = options.index(correct) if correct in options else 0
        quiz.append({
            "question": f"Translate \"{phrase}\" into {target_lang}",
            "options": options,
            "answer_index": answer_index
        })
    return quiz


# ---------- Analytics (unchanged) ----------
def analyze_conversation(history, target_lang="English"):
    total_messages = len(history)
    total_words = sum(len(item.get("text","").split()) for item in history)
    languages = {}
    target_count = 0
    for item in history:
        lang = item.get("source_lang", "unknown")
        languages[lang] = languages.get(lang, 0) + 1
        if isinstance(lang, str) and target_lang.lower() in lang.lower():
            target_count += 1
    percent_in_target = (target_count / total_messages * 100) if total_messages else 0
    return {
        "total_messages": total_messages,
        "total_words": total_words,
        "languages_used": languages,
        "percent_in_target": percent_in_target
    }
