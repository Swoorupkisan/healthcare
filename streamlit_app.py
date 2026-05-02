import json
import os
from datetime import datetime
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
    session_key = st.session_state.get("temporary_groq_key", "").strip()
    if session_key:
        return session_key

    try:
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except Exception:
        pass
    return os.getenv("GROQ_API_KEY", "")


def detect_emergency_symptoms(text: str) -> List[str]:
    emergency_terms = {
        "chest pain": "Chest pain",
        "shortness of breath": "Shortness of breath",
        "difficulty breathing": "Difficulty breathing",
        "severe bleeding": "Severe bleeding",
        "unconscious": "Unconsciousness",
        "stroke": "Stroke-like symptoms",
        "seizure": "Seizure",
        "suicidal": "Self-harm risk",
        "suicide": "Self-harm risk",
        "poison": "Possible poisoning",
        "overdose": "Possible overdose",
    }
    lowered = text.lower()
    return [label for term, label in emergency_terms.items() if term in lowered]


def build_patient_context(info: Dict[str, str]) -> str:
    parts: List[str] = []
    if info.get("age"):
        parts.append(f"Age: {info['age']}")
    if info.get("gender"):
        parts.append(f"Gender: {info['gender']}")
    if info.get("weight"):
        parts.append(f"Weight: {info['weight']} kg")
    if info.get("duration"):
        parts.append(f"Symptom duration: {info['duration']}")
    if info.get("severity"):
        parts.append(f"Self-rated severity: {info['severity']}")
    if info.get("existing_conditions"):
        parts.append(f"Existing conditions: {info['existing_conditions']}")
    if info.get("medications"):
        parts.append(f"Current medications: {info['medications']}")
    if info.get("allergies"):
        parts.append(f"Allergies: {info['allergies']}")
    return f"\n\n[Patient Profile: {', '.join(parts)}]" if parts else ""


def format_chat_report(messages: List[Dict[str, str]], patient_info: Dict[str, str]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "HealthAI Chat Report",
        f"Generated: {generated_at}",
        "",
        "Patient Profile",
    ]

    profile_fields = [
        ("age", "Age"),
        ("gender", "Gender"),
        ("weight", "Weight"),
        ("duration", "Symptom duration"),
        ("severity", "Severity"),
        ("existing_conditions", "Existing conditions"),
        ("medications", "Current medications"),
        ("allergies", "Allergies"),
    ]
    for key, label in profile_fields:
        value = patient_info.get(key) or "Not provided"
        lines.append(f"- {label}: {value}")

    lines.extend(["", "Conversation"])
    for msg in messages:
        role = "User" if msg["role"] == "user" else "HealthAI"
        lines.extend(["", f"{role}:", msg["content"]])

    lines.extend(
        [
            "",
            "Disclaimer: This report is for informational purposes only and does not constitute medical advice. Please consult a qualified healthcare professional for diagnosis and treatment.",
        ]
    )
    return "\n".join(lines)


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


st.set_page_config(page_title="HealthAI", layout="centered")
st.title("HealthAI - Medical Assistant")
st.caption("Informational support only. Always consult a qualified healthcare professional.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_symptoms" not in st.session_state:
    st.session_state.selected_symptoms = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = ""
if "temporary_groq_key" not in st.session_state:
    st.session_state.temporary_groq_key = ""

with st.sidebar:
    st.subheader("Patient Profile")
    age = st.text_input("Age")
    gender = st.selectbox("Gender", ["", "Female", "Male", "Other"])
    weight = st.text_input("Weight (kg)")
    duration = st.selectbox(
        "Symptom Duration",
        ["", "Less than 24 hours", "1-3 days", "4-7 days", "More than 1 week", "More than 1 month"],
    )
    severity = st.slider("Severity", min_value=1, max_value=10, value=5)
    existing_conditions = st.text_area("Existing Conditions")
    medications = st.text_area("Current Medications")
    allergies = st.text_area("Allergies")

    st.divider()
    st.subheader("Settings")
    st.session_state.temporary_groq_key = st.text_input(
        "Temporary Groq API Key",
        value=st.session_state.temporary_groq_key,
        type="password",
        help="Optional. Overrides the Render/Streamlit secret only for this browser session.",
    )

    if st.button("Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

patient_info = {
    "age": age.strip(),
    "gender": gender.strip(),
    "weight": weight.strip(),
    "duration": duration.strip(),
    "severity": f"{severity}/10",
    "existing_conditions": existing_conditions.strip(),
    "medications": medications.strip(),
    "allergies": allergies.strip(),
}

st.subheader("Quick Symptoms")
symptom_options = [
    "Fever",
    "Cough",
    "Headache",
    "Sore throat",
    "Stomach pain",
    "Nausea",
    "Fatigue",
    "Chest pain",
    "Shortness of breath",
]
symptom_cols = st.columns(3)
for index, symptom in enumerate(symptom_options):
    with symptom_cols[index % 3]:
        if st.button(symptom, use_container_width=True):
            if symptom not in st.session_state.selected_symptoms:
                st.session_state.selected_symptoms.append(symptom)

if st.session_state.selected_symptoms:
    selected_text = ", ".join(st.session_state.selected_symptoms)
    st.info(f"Selected symptoms: {selected_text}")
    action_cols = st.columns([1, 1])
    with action_cols[0]:
        if st.button("Use Symptoms", use_container_width=True):
            st.session_state.pending_prompt = f"I have these symptoms: {selected_text}. Please help me understand what could be happening."
    with action_cols[1]:
        if st.button("Clear Symptoms", use_container_width=True):
            st.session_state.selected_symptoms = []
            st.session_state.pending_prompt = ""
            st.rerun()

report = format_chat_report(st.session_state.messages, patient_info)
st.download_button(
    "Download Chat Report",
    data=report,
    file_name="healthai-chat-report.txt",
    mime="text/plain",
    disabled=not st.session_state.messages,
)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Describe your symptoms...")
if not prompt and st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = ""

if prompt:
    api_key = get_groq_key()
    if not api_key.startswith("gsk_"):
        st.error("GROQ_API_KEY is missing or invalid. Add it in Render/Streamlit secrets or use the temporary key field.")
        st.stop()

    emergency_matches = detect_emergency_symptoms(prompt)
    if emergency_matches:
        st.error(
            "Emergency warning: "
            + ", ".join(emergency_matches)
            + " can require urgent care. If symptoms are severe, call local emergency services now."
        )

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
