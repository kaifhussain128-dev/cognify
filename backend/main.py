import os
import sys
from fastapi import FastAPI, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import errors

# Ensure backend directory is in python search path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdf_processor import extract_text_from_pdf
from auth import register_user, login_user, get_user_by_token, logout_user

load_dotenv()

app = FastAPI(title="Cognify — StudyMate AI API")

class ChatRequest(BaseModel):
    question: str
    provider: str = "antigravity"
    pdf_text: str = ""

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class LogoutRequest(BaseModel):
    token: str = ""

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint serving the frontend StudyMate AI UI
@app.get("/")
def serve_ui():
    frontend_index = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "index.html")
    return FileResponse(frontend_index)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Cognify StudyMate AI"}

# ==================== AUTHENTICATION ENDPOINTS ====================

@app.post("/auth/register")
def auth_register(req: RegisterRequest):
    try:
        result = register_user(req.name, req.email, req.password)
        return {"success": True, **result}
    except ValueError as e:
        return {"success": False, "error": str(e)}

@app.post("/auth/login")
def auth_login(req: LoginRequest):
    try:
        result = login_user(req.email, req.password)
        return {"success": True, **result}
    except ValueError as e:
        return {"success": False, "error": str(e)}

@app.get("/auth/me")
def auth_me(token: str = Query(None)):
    user = get_user_by_token(token)
    if not user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": user}

@app.post("/auth/logout")
def auth_logout(req: LogoutRequest):
    logout_user(req.token)
    return {"success": True, "message": "Logged out successfully."}

def get_genai_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set. Please configure GEMINI_API_KEY in your environment variables (e.g. Render Dashboard or .env).")
    return genai.Client(api_key=api_key)

# Global list to store the ongoing conversation
chat_history = []

@app.post("/clear-chat")
def clear_chat():
    global chat_history
    chat_history = []
    return {"message": "Memory cleared."}

@app.post("/ask-ai")
def ask_ai(request: ChatRequest): 
    global chat_history
    
    prompt = request.question
    if request.pdf_text:
        prompt = f"Based on the following document:\n\n{request.pdf_text}\n\nUser Question: {request.question}"

    # 1. Append the user's new message to the memory log
    chat_history.append({"role": "user", "parts": [{"text": prompt}]})

    try:
        client = get_genai_client()
        model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
        # 2. Pass the ENTIRE chat_history list to the model so it has context
        response = client.models.generate_content(
            model=model_name, 
            contents=chat_history
        )
        
        # 3. Append the AI's response to the memory log
        chat_history.append({"role": "model", "parts": [{"text": response.text}]})
        
        return {
            "provider": "Cognify AI",
            "response": response.text
        }
    except Exception as e:
        # If the API fails, remove the failed user prompt to prevent memory corruption
        if chat_history:
            chat_history.pop()
        return {
            "provider": "Cognify AI",
            "error": "API error or quota exhausted. Please try again later.",
            "details": str(e)
        }
    
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        return {"error": "Only PDF files are supported."}

    try:
        file_bytes = await file.read()
        pdf_text = extract_text_from_pdf(file_bytes)

        if not pdf_text:
            return {"error": "Could not extract any text from this PDF."}

        return {
            "message": "PDF processed successfully!",
            "filename": file.filename,
            "extracted_text": pdf_text
        }
    except Exception as e:
        return {"error": str(e)}