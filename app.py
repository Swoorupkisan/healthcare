from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import json
import os

app = FastAPI(title="HealthAI - Medical Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama3-70b-8192"

SYSTEM_PROMPT = """You are HealthAI, an advanced medical assistant AI. You help users understand potential conditions based on their symptoms, but you always remind them that you are NOT a substitute for professional medical advice.

When a user provides symptoms and health information, you should:

1. **ANALYSIS**: Carefully analyze all provided symptoms, duration, severity, age, gender, and medical history.

2. **POSSIBLE CONDITIONS**: List 2-4 possible conditions ranked by likelihood, with brief explanations for each.

3. **SEVERITY ASSESSMENT**: Rate the overall severity as:
   - 🟢 MILD - Monitor at home, lifestyle changes
   - 🟡 MODERATE - Schedule a doctor visit within days
   - 🔴 SEVERE - Seek immediate medical attention / Emergency

4. **RED FLAGS**: Mention any alarming symptoms that require immediate ER visit.

5. **SELF-CARE TIPS**: Provide safe, general home care advice if appropriate.

6. **DOCTOR CONSULTATION**: Always advise seeing a doctor. If severity is SEVERE, strongly urge calling emergency services (102 in India, 911 in US).

Format your response clearly with headers. Be empathetic, clear, and thorough. Use markdown formatting with bold headers.

IMPORTANT DISCLAIMER: Always end with: "⚕️ This is for informational purposes only and does not constitute medical advice. Please consult a qualified healthcare professional for diagnosis and treatment."
"""

class ChatRequest(BaseModel):
    messages: list
    patient_info: dict = {}

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/api/chat")
async def chat(request: ChatRequest):
    # Build context from patient info
    patient_context = ""
    if request.patient_info:
        info = request.patient_info
        parts = []
        if info.get("age"): parts.append(f"Age: {info['age']}")
        if info.get("gender"): parts.append(f"Gender: {info['gender']}")
        if info.get("weight"): parts.append(f"Weight: {info['weight']} kg")
        if info.get("existing_conditions"): parts.append(f"Existing conditions: {info['existing_conditions']}")
        if info.get("medications"): parts.append(f"Current medications: {info['medications']}")
        if info.get("allergies"): parts.append(f"Allergies: {info['allergies']}")
        if parts:
            patient_context = f"\n\n[Patient Profile: {', '.join(parts)}]"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    for msg in request.messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user" and patient_context and len(messages) == 1:
            content = content + patient_context
        messages.append({"role": role, "content": content})

    async def stream_response():
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": messages,
                    "max_tokens": 1500,
                    "temperature": 0.3,
                    "stream": True,
                },
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            yield f"data: [DONE]\n\n"
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield f"data: {json.dumps({'content': delta})}\n\n"
                        except Exception:
                            pass

    return StreamingResponse(stream_response(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
