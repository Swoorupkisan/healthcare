# HealthAI — Intelligent Medical Assistant

A modern AI-powered healthcare chatbot built with **Python (FastAPI)** + **Groq API (LLaMA 3 70B)** featuring a sleek dark-themed UI.

---

## 🚀 Quick Start

### 1. Install dependencies (FastAPI local run)

```bash
cd healthcare_chatbot
pip install -r requirements-fastapi.txt
```

### 2. Set your Groq API Key

Get your free API key from https://console.groq.com

**Option A — Environment variable (recommended):**
```bash
export GROQ_API_KEY=your_key_here
```

**Option B — Edit `app.py` directly:**
```python
GROQ_API_KEY = "your_key_here"   # line 12
```

### 3. Run the server

```bash
python app.py
# OR
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 4. Open in browser

```
http://localhost:8000
```

---

## ✨ Features

| Feature | Description |
|---|---|
| 🧠 **AI Diagnosis** | LLaMA 3 70B analyzes symptoms and suggests possible conditions |
| 👤 **Patient Profile** | Age, gender, weight, existing conditions, medications, allergies |
| 🏷️ **Quick Symptoms** | One-click symptom chips for fast input |
| 🎙️ **Voice Input** | Speech-to-text for hands-free symptom entry |
| 📊 **Severity Rating** | Mild / Moderate / Severe self-assessment |
| 🚨 **Emergency Banner** | Auto-detects severe conditions, shows emergency call button |
| 💬 **Streaming** | Real-time streaming responses |
| 📱 **Responsive** | Works on mobile and desktop |

---

## 📁 Project Structure

```
healthcare_chatbot/
├── app.py          # FastAPI backend
├── index.html      # Frontend UI (served by FastAPI)
├── requirements.txt
└── README.md
```

---

## ⚠️ Medical Disclaimer

This application is for **informational purposes only** and does **not** constitute medical advice, diagnosis, or treatment. Always consult a qualified healthcare professional for medical decisions.

**Emergency numbers:**
- India: **102** (Ambulance) / **112** (Emergency)
- US: **911**
- UK: **999**

---

## Streamlit Deployment

This repository now includes [streamlit_app.py](streamlit_app.py) for direct Streamlit deployment.

`requirements.txt` is intentionally kept Streamlit-focused for cloud compatibility.
Use `requirements-fastapi.txt` when running `app.py` locally.

### Local Run (Streamlit)

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### Streamlit Cloud Steps

1. Push this repository to GitHub.
2. In Streamlit Cloud, create a new app from this repo.
3. Set **Main file path** to `streamlit_app.py`.
4. Add secret in Streamlit Cloud:

```toml
GROQ_API_KEY = "gsk_your_real_key_here"
```

5. Deploy.
