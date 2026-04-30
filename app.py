from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import json
import os
from pathlib import Path

app = FastAPI(title="HealthAI - Medical Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are HealthAI, an advanced medical assistant AI. You help users understand potential conditions based on their symptoms, but you always remind them that you are NOT a substitute for professional medical advice.

When a user provides symptoms and health information, you should:

1. ANALYSIS: Carefully analyze all provided symptoms, duration, severity, age, gender, and medical history.
2. POSSIBLE CONDITIONS: List 2-4 possible conditions ranked by likelihood.
3. SEVERITY ASSESSMENT: Rate severity as MILD/MODERATE/SEVERE.
4. RED FLAGS: Mention alarming symptoms requiring immediate attention.
5. SELF-CARE TIPS: Provide safe, general home care advice if appropriate.
6. DOCTOR CONSULTATION: Always advise seeing a doctor.

End with: "This is for informational purposes only and does not constitute medical advice. Please consult a qualified healthcare professional for diagnosis and treatment."""


def get_groq_api_key() -> str:
    env_key = os.getenv("GROQ_API_KEY", "").strip()
    if env_key:
        return env_key

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def is_valid_groq_key(key: str) -> bool:
    return bool(key) and key.startswith("gsk_")


def build_patient_context(info: dict) -> str:
    parts = []
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


class ChatRequest(BaseModel):
    messages: list
    patient_info: dict = {}


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/test-stream")
def test_stream():
    def gen():
        for i in range(3):
            yield f"data: {json.dumps({'msg': f'test {i}'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/chat")
async def chat(request: ChatRequest):
    groq_api_key = get_groq_api_key()
    if not is_valid_groq_key(groq_api_key):
        return JSONResponse({"error": "GROQ_API_KEY missing or invalid"}, status_code=401)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    patient_context = build_patient_context(request.patient_info)

    for index, message in enumerate(request.messages):
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "user" and index == 0 and patient_context:
            content += patient_context
        messages.append({"role": role, "content": content})

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": messages,
                    "max_tokens": 1500,
                    "temperature": 0.3,
                    "stream": False,
                },
            )

        if response.status_code >= 400:
            try:
                details = response.json()
            except Exception:
                details = {"error": response.text}
            return JSONResponse({"error": f"Groq error {response.status_code}: {details}"}, status_code=502)

        payload = response.json()
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return JSONResponse({"error": "Groq returned an empty response"}, status_code=502)

        return JSONResponse({"content": content})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081, reload=False)
