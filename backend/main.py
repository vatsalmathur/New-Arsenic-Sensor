import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AquaSentry AI Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_knowledge_base():
    try:
        with open("knowledge.txt", "r", encoding="utf-8") as f:
            content = f.read()
            return f"You are the official AquaSentry AI Assistant. Use the following project summary to answer user questions accurately. If asked about something outside this scope, politely decline. Here is the project knowledge:\n\n{content}"
    except FileNotFoundError:
        return "You are a helpful AI assistant for AquaSentry. Answer questions about Arsenic and the AquaSentry robot."

SYSTEM_PROMPT = load_knowledge_base()

try:
    client = genai.Client()
except Exception as e:
    print(f"Warning: Failed to initialize Gemini client. Make sure GEMINI_API_KEY is set. Error: {e}")
    client = None

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

class KnowledgeRequest(BaseModel):
    text: str

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    global SYSTEM_PROMPT
    if not client:
        raise HTTPException(status_code=500, detail="Gemini client not initialized. Check API key.")
    
    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash',  # Upgraded model
            contents=request.message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3,
            )
        )
        return ChatResponse(reply=response.text)
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/knowledge")
async def update_knowledge(request: KnowledgeRequest):
    global SYSTEM_PROMPT
    try:
        with open("knowledge.txt", "w", encoding="utf-8") as f:
            f.write(request.text)
        # Reload the system prompt
        SYSTEM_PROMPT = load_knowledge_base()
        return {"status": "success", "message": "Knowledge base updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/knowledge")
async def get_knowledge():
    try:
        with open("knowledge.txt", "r", encoding="utf-8") as f:
            return {"text": f.read()}
    except FileNotFoundError:
        return {"text": ""}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
