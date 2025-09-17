# app.py
import streamlit as st
import os, json, uuid
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
load_dotenv()

from utils import (
    detect_language,
    translate_text,
    get_grammar_notes,
    analyze_conversation,
    generate_quiz,
)

# ---------- CONFIG ----------
st.set_page_config(page_title="LinguaLink 🌍", page_icon="🌐", layout="wide")

# Gemini API setup
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-pro")

# Ensure data directories
os.makedirs("data/conversations", exist_ok=True)
os.makedirs("data/analytics", exist_ok=True)

# ---------- SESSION STATE INITIALIZATION ----------
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex[:8]

if "step" not in st.session_state:
    st.session_state.step = 1

if "profile" not in st.session_state:
    st.session_state.profile = {
        "target_lang": "Spanish",
        "level": "Beginner",
        "goal_minutes": 15,
        "style": "Casual",
    }

if "history" not in st.session_state:
    st.session_state.history = []

# ---------- SIDEBAR: show guided steps ----------
st.sidebar.title("🧭 Guided Steps")
STEPS = [
    "1 — Set Goal & Language",
    "2 — Language Detection Test",
    "3 — Practice Conversation",
    "4 — Learning Mode (Quiz)",
    "5 — Analytics & Progress",
]
for i, name in enumerate(STEPS, start=1):
    if st.session_state.step > i:
        prefix = "✅"
    elif st.session_state.step == i:
        prefix = "➡️"
    else:
        prefix = "◻️"
    st.sidebar.write(f"{prefix} {name}")

# ---------- MAIN ----------
st.title("LinguaLink — Guided Learning Chatbot 🌍")
st.markdown("Follow the steps on the left. We'll guide you through every stage — you're not alone. 🤝")

# ---- STEP 1: Settings ----
if st.session_state.step == 1:
    st.header("Step 1 — Set goal & target language")
    languages = [
        "Spanish","French","Hindi","Arabic","English",
        "German","Urdu","Japanese","Chinese (Simplified)",
        "Portuguese","Russian",
    ]
    target_idx = languages.index(st.session_state.profile.get("target_lang")) if st.session_state.profile.get("target_lang") in languages else 0
    target = st.selectbox("Choose target language", languages, index=target_idx)
    level = st.selectbox("Your level", ["Beginner", "Intermediate", "Advanced"], index=["Beginner","Intermediate","Advanced"].index(st.session_state.profile.get("level","Beginner")))
    goal = st.number_input("Daily practice minutes", min_value=5, max_value=120, value=int(st.session_state.profile.get("goal_minutes",15)), step=5)
    style = st.radio("Conversation style", ["Casual", "Formal"], index=0)
    if st.button("Save settings"):
        st.session_state.profile.update({"target_lang": target, "level": level, "goal_minutes": goal, "style": style})
        st.success("Settings saved ✅")

# ---- STEP 2: Detection Test ----
elif st.session_state.step == 2:
    st.header("Step 2 — Language Detection Test")
    sample = st.text_area("Type/paste a short sentence in any language", height=120)
    if st.button("Detect language"):
        if not sample.strip():
            st.warning("Type something first bro 🙏")
        else:
            code, name = detect_language(sample, return_name=True)
            st.markdown(f"**Detected:** {name} (`{code}`)")
            translated, _ = translate_text(sample, st.session_state.profile["target_lang"])
            st.markdown(f"**Translation → {st.session_state.profile['target_lang']}:** {translated}")

# ---- STEP 3: Practice Conversation ----
elif st.session_state.step == 3:
    st.header("Step 3 — Practice Conversation")
    st.markdown("Chat below. Each bot reply includes Gemini-powered response + detected language, translation, and grammar hints.")

    # show history
    for m in st.session_state.history:
        if m["sender"] == "user":
            st.chat_message("user").write(m["text"])
        else:
            st.chat_message("assistant").write(m["text"])

    try:
        user_msg = st.chat_input("Type your message...")
    except Exception:
        user_msg = st.text_input("Type your message here and press Enter:")

    if user_msg:
        # language detection
        code, name = detect_language(user_msg, return_name=True)

        # translation
        translated, pron = translate_text(user_msg, st.session_state.profile["target_lang"])

        # grammar notes
        grammar = get_grammar_notes(user_msg, st.session_state.profile["target_lang"])

        # Gemini response (in target language style)
        prompt = f"""
        You are a helpful language learning assistant.
        The user wrote: "{user_msg}"
        Their target language is: {st.session_state.profile['target_lang']}
        Conversation style: {st.session_state.profile['style']}
        Level: {st.session_state.profile['level']}
        Reply naturally in the target language, keeping it simple and correct for their level.
        """
        try:
            gemini_reply = model.generate_content(prompt).text
        except Exception as e:
            gemini_reply = f"(Gemini API error: {e})"

        bot_text = (
            f"**Detected:** {name}\n\n"
            f"**Translation ({st.session_state.profile['target_lang']}):** {translated}\n\n"
            f"**Grammar notes:** {grammar}\n\n"
            f"**Pronunciation (approx):** {pron}\n\n"
            f"**Gemini Reply:** {gemini_reply}"
        )

        # append to history
        st.session_state.history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "sender": "user",
            "text": user_msg,
            "source_lang": name,
        })
        st.session_state.history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "sender": "assistant",
            "text": bot_text,
        })

        # save conversation
        fname = f"data/conversations/{st.session_state.session_id}_{datetime.utcnow().strftime('%Y%m%d')}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(st.session_state.history, f, ensure_ascii=False, indent=2)

        st.experimental_rerun()

# ---- STEP 4: Learning Mode (Quiz) ----
elif st.session_state.step == 4:
    st.header("Step 4 — Learning Mode (Quiz)")
    quiz = generate_quiz(st.session_state.profile["target_lang"], st.session_state.profile["level"])
    if "quiz_index" not in st.session_state:
        st.session_state.quiz_index = 0
        st.session_state.quiz_score = 0

    q = quiz[st.session_state.quiz_index]
    st.subheader(f"Q{st.session_state.quiz_index + 1}: {q['question']}")
    choice = st.radio("Choose the correct translation:", q["options"], key=f"q{st.session_state.quiz_index}")

    if st.button("Submit Answer"):
        correct_choice = q["options"][q["answer_index"]]
        if choice == correct_choice:
            st.success("Correct ✅")
            st.session_state.quiz_score += 1
        else:
            st.error(f"Wrong — correct: **{correct_choice}**")
        st.session_state.quiz_index += 1

        if st.session_state.quiz_index >= len(quiz):
            st.info(f"Quiz finished — score: {st.session_state.quiz_score}/{len(quiz)}")
            st.session_state.quiz_index = 0
            st.session_state.quiz_score = 0

# ---- STEP 5: Analytics & Progress ----
elif st.session_state.step == 5:
    st.header("Step 5 — Analytics & Progress")
    stats = analyze_conversation(st.session_state.history, target_lang=st.session_state.profile["target_lang"])
    st.metric("Total messages", stats.get("total_messages", 0))
    st.metric("Total words", stats.get("total_words", 0))
    st.write("Languages used:", stats.get("languages_used", {}))
    st.write("Messages in target language (%):", f"{stats.get('percent_in_target', 0):.1f}%")

    # save analytics snapshot
    afname = f"data/analytics/{st.session_state.session_id}_{datetime.utcnow().strftime('%Y%m%d')}.json"
    with open(afname, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

# ---------- NAVIGATION ----------
nav1, nav2 = st.columns([1, 1])
with nav1:
    if st.button("⬅️ Back") and st.session_state.step > 1:
        st.session_state.step -= 1
        st.rerun()
with nav2:
    if st.button("Next ➡️") and st.session_state.step < len(STEPS):
        st.session_state.step += 1
        st.rerun()

st.markdown("---")
st.caption("Tip: Use the Guided Steps to move sequentially. We'll save conversation logs and analytics automatically. 🙌")
