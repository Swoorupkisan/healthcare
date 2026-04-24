import json
import os
from typing import Dict, List

import httpx
import streamlit as st

MODEL = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are HealthAI, an advanced medical assistant AI. You help users understand potential conditions based on their symptoms, but you always remind them that you are NOT a substitute for professional medical advice.

When a user provides symptoms and health information, you should:

1. **ANALYSIS**: Carefully analyze all provided symptoms, duration, severity, age, gender, and medical history.
2. **POSSIBLE CONDITIONS**: List 2-4 possible conditions ranked by likelihood, with brief explanations for each.
3. **SEVERITY ASSESSMENT**: Rate severity as MILD, MODERATE, or SEVERE.
4. **RED FLAGS**: Mention alarming symptoms that require immediate ER visit.
5. **SELF-CARE TIPS**: Provide safe, general home care advice if appropriate.
6. **DOCTOR CONSULTATION**: Always advise seeing a doctor.

Always end with: "This is for informational purposes only and does not constitute medical advice. Please consult a qualified healthcare professional for diagnosis and treatment."
"""


def get_groq_key() -> str:
    try:
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except Exception:
        pass
    return os.getenv("GROQ_API_KEY", "")


def build_patient_context(info: Dict[str, str]) -> str:
    parts: List[str] = []
    if info.get("age"):
        parts.append(f"Age: {info['age']}")
    if info.get("gender"):
        parts.append(f"Gender: {info['gender']}")
    if info.get("weight"):
        parts.append(f"Weight: {info['weight']} kg")
    if info.get("existing_conditions"):
        parts.append(f"Existing conditions: {info['existing_conditions']}")
    if info.get("medications"):
        parts.append(f"Current medications: {info['medications']}")
    if info.get("allergies"):
        parts.append(f"Allergies: {info['allergies']}")
    return f"\n\n[Patient Profile: {', '.join(parts)}]" if parts else ""


def stream_groq_reply(messages: List[Dict[str, str]], api_key: str):
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 1500,
        "temperature": 0.3,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.stream("POST", GROQ_API_URL, headers=headers, json=payload, timeout=30.0) as response:
        if response.status_code >= 400:
            try:
                details = response.json()
            except Exception:
                details = {"error": response.text}
            raise RuntimeError(f"Groq API error {response.status_code}: {details}")

        for line in response.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"].get("content", "")
                if delta:
                    yield delta
            except Exception:
                continue


st.set_page_config(page_title="HealthAI", page_icon="⚕️", layout="centered")
st.title("HealthAI - Medical Assistant")
st.caption("Informational support only. Always consult a qualified healthcare professional.")

with st.sidebar:
    st.subheader("Patient Profile")
    age = st.text_input("Age")
    gender = st.selectbox("Gender", ["", "Female", "Male", "Other"])
    weight = st.text_input("Weight (kg)")
    existing_conditions = st.text_area("Existing Conditions")
    medications = st.text_area("Current Medications")
    allergies = st.text_area("Allergies")

patient_info = {
    "age": age.strip(),
    "gender": gender.strip(),
    "weight": weight.strip(),
    "existing_conditions": existing_conditions.strip(),
    "medications": medications.strip(),
    "allergies": allergies.strip(),
}

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Describe your symptoms...")
if prompt:
    api_key = get_groq_key()
    if not api_key.startswith("gsk_"):
        st.error("GROQ_API_KEY is missing or invalid. Add it in Streamlit Secrets.")
        st.stop()

    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.messages.append({"role": "user", "content": prompt})

    request_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    patient_context = build_patient_context(patient_info)

    for idx, msg in enumerate(st.session_state.messages):
        content = msg["content"]
        if msg["role"] == "user" and idx == 0 and patient_context:
            content += patient_context
        request_messages.append({"role": msg["role"], "content": content})

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full = ""
        try:
            for token in stream_groq_reply(request_messages, api_key):
                full += token
                placeholder.markdown(full)
        except Exception as exc:
            full = f"Error: {exc}"
            placeholder.error(full)

    st.session_state.messages.append({"role": "assistant", "content": full})
