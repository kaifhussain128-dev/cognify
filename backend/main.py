import os
import sys
from fastapi import FastAPI, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdf_processor import extract_text_from_pdf, extract_pdf_structured
from auth import register_user, login_user, get_user_by_token, logout_user, google_auth_user

load_dotenv()

app = FastAPI(
    title="Cognify StudyMate AI API",
    description="Intelligent AI study companion featuring Parsli-grade structured PDF document extraction, active recall synthesis, and member authentication."
)

# ---------- Request & Response models ----------

class DocumentMetadataSchema(BaseModel):
    filename: str = Field(description="Original filename of the PDF")
    page_count: int = Field(description="Total number of rendered pages")
    total_words: int = Field(description="Total word count across all pages")
    total_characters: int = Field(description="Total character count")
    metadata: dict = Field(default_factory=dict, description="Embedded PDF metadata (author, title, producer, etc.)")

class KeyConceptItem(BaseModel):
    term: str = Field(description="Extracted academic concept or terminology")
    definition: str = Field(description="High-yield definition or operational significance")
    importance: str = Field(default="medium", description="'high' or 'medium' priority for study review")

class SectionItem(BaseModel):
    heading: str = Field(description="Detected section or chapter heading")
    page: int = Field(default=1, description="Page number where section appears")
    preview: str = Field(default="", description="Snippet or preview of section content")

class ExtractedDataSchema(BaseModel):
    title: str = Field(description="Extracted or deduced document title")
    summary: str = Field(description="Executive summary of the document")
    key_concepts: list[KeyConceptItem] = Field(default_factory=list, description="Key concepts and definitions")
    sections: list[SectionItem] = Field(default_factory=list, description="Section-by-section breakdown")
    suggested_questions: list[str] = Field(default_factory=list, description="Suggested active recall practice questions")
    raw_text: str = Field(description="Full extracted text content for study analysis")

class PageItem(BaseModel):
    page_number: int
    word_count: int
    char_count: int
    text: str

class ParsliExtractionResponse(BaseModel):
    status: str = Field(default="success")
    engine: str = Field(description="Extraction engine used (e.g. cognify-parsli-ai-v1, cognify-parsli-fast-v1)")
    mode: str = Field(description="'ai' or 'fast'")
    processed_at: str = Field(description="ISO timestamp of extraction completion")
    document: DocumentMetadataSchema
    extracted_data: ExtractedDataSchema
    pages: list[PageItem] = Field(default_factory=list)
    extracted_text: str = Field(default="", description="Backward-compatible text string")

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

class GoogleAuthRequest(BaseModel):
    name: str = ""
    email: str

class LogoutRequest(BaseModel):
    token: str = ""

class StudyMessage(BaseModel):
    role: str          # "user" | "assistant"
    text: str

class StudyRequest(BaseModel):
    message: str
    history: list[StudyMessage] = []
    pdf_text: str = ""

# Keep Sage models for backwards compatibility
class SageMessage(BaseModel):
    role: str
    text: str

class SageRequest(BaseModel):
    message: str
    history: list[SageMessage] = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

@app.get("/")
def serve_ui():
    frontend_index = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(frontend_index):
        return {"error": f"Frontend not found at {frontend_index}"}
    return FileResponse(frontend_index)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Cognify StudyMate AI"}

# ==================== AUTHENTICATION ====================

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

@app.post("/auth/google")
def auth_google(req: GoogleAuthRequest):
    try:
        result = google_auth_user(req.name, req.email)
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

# ==================== COGNIFY STUDY COPILOT ====================

def get_genai_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=api_key)

COGNIFY_SYSTEM_PROMPT = """You are Cognify, an intelligent, attentive, and calm AI Study Copilot. \
Your goal is to help students, researchers, and curious minds master difficult subjects, retain concepts deeply, \
and study with quiet clarity.

CORE COMPETENCIES:
1. Concept Breakdown: Explain complex, technical, or abstract ideas using clear language, structured steps, and intuitive analogies.
2. Document Understanding: When a document or notes are provided in context, synthesize main arguments, cite specific sections, and answer questions with high fidelity to the text.
3. Active Recall & Quizzing: Generate targeted practice questions, flashcard sets, or Socratic questions to test comprehension and memory.
4. Methodical Problem Solving: Walk step-by-step through math, logic, code, or essay construction.

STYLE:
- Clean Markdown formatting: use bold keywords, bulleted lists, code blocks, or LaTeX math when relevant.
- Tone: warm, encouraging, intellectually rigorous, and unhurried. No gimmicks, no fluff."""

MAX_PROMPT_CHARS = 4000

@app.post("/api/study")
def study_chat(req: StudyRequest):
    clean_msg = req.message.strip()
    if not clean_msg:
        return {"success": False, "error": "Your question cannot be empty. Please enter a question or topic to study."}
    
    if len(clean_msg) > MAX_PROMPT_CHARS:
        return {
            "success": False,
            "error": f"Text written in search bar is too long ({len(clean_msg):,} / {MAX_PROMPT_CHARS:,} characters). Please condense your question or attach large passages as a PDF document using the paperclip button."
        }

    contents = []
    
    # Document context injection
    doc_prefix = ""
    if req.pdf_text and req.pdf_text.strip():
        doc_prefix = f"[ATTACHED DOCUMENT CONTENT]:\n{req.pdf_text.strip()}\n\n---\n"

    for m in req.history[-12:]:
        role = "model" if m.role == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m.text}]})
    
    user_message = doc_prefix + clean_msg if doc_prefix and not contents else clean_msg
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    try:
        client = get_genai_client()
        model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=COGNIFY_SYSTEM_PROMPT),
        )
        return {"success": True, "reply": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Backwards compatibility alias for /api/sage
@app.post("/api/sage")
def sage_alias(req: SageRequest):
    return study_chat(StudyRequest(message=req.message, history=[StudyMessage(role=m.role, text=m.text) for m in req.history]))

# ==================== LEGACY STUDY ENDPOINTS ====================

chat_history = []

@app.post("/clear-chat")
def clear_chat():
    global chat_history
    chat_history = []
    return {"message": "Memory cleared."}

@app.post("/ask-ai")
def ask_ai(request: ChatRequest):
    global chat_history
    prompt = request.question.strip()
    if not prompt:
        return {"provider": "Cognify AI", "error": "Your question cannot be empty."}
    if len(prompt) > MAX_PROMPT_CHARS:
        return {
            "provider": "Cognify AI",
            "error": f"Text written in search bar is too long ({len(prompt):,} / {MAX_PROMPT_CHARS:,} characters). Please condense your question or attach large passages as a PDF document using the paperclip button."
        }
    if request.pdf_text:
        prompt = f"Based on the following document:\n\n{request.pdf_text}\n\nUser Question: {request.question}"
    chat_history.append({"role": "user", "parts": [{"text": prompt}]})
    try:
        client = get_genai_client()
        model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
        response = client.models.generate_content(model=model_name, contents=chat_history)
        chat_history.append({"role": "model", "parts": [{"text": response.text}]})
        return {"provider": "Cognify AI", "response": response.text}
    except Exception as e:
        if chat_history:
            chat_history.pop()
        return {"provider": "Cognify AI", "error": "API error or quota exhausted.", "details": str(e)}

@app.post("/api/extract-pdf", response_model=ParsliExtractionResponse, tags=["Document Extraction"])
async def api_extract_pdf(
    file: UploadFile = File(..., description="PDF document file to extract"),
    mode: str = Query("auto", pattern="^(auto|ai|fast)$", description="Extraction engine mode: 'auto' (AI with instant fallback), 'ai' (Gemini structured extraction), or 'fast' (local heuristic parsing)")
):
    """
    Parsli-compatible PDF Structured Extraction API.
    Converts any PDF into typed, structured JSON containing:
    - Document metadata (pages, word/char counts, embedded metadata)
    - Executive summary & detected title
    - Key academic concepts with high-yield definitions and importance tiers
    - Section-by-section breakdown with headings and page anchors
    - Suggested active recall practice questions
    - Page-by-page text breakdown
    - Full backward-compatible raw text
    """
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": "Invalid file format. Only PDF documents are supported."}
        )
    try:
        file_bytes = await file.read()
        if len(file_bytes) == 0:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": "Uploaded PDF file is empty."}
            )
        result = extract_pdf_structured(file_bytes, filename=file.filename, mode=mode)
        return result
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": f"Failed to extract structured data from PDF: {str(e)}"}
        )

@app.post("/upload-pdf", tags=["Document Extraction"])
async def upload_pdf(file: UploadFile = File(...)):
    """
    Enhanced PDF upload endpoint returning both legacy fields ('extracted_text', 'filename')
    and complete Parsli structured document schema ('document', 'extracted_data', 'pages', 'engine').
    """
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(status_code=400, content={"error": "Only PDF files are supported."})
    try:
        file_bytes = await file.read()
        if len(file_bytes) == 0:
            return JSONResponse(status_code=400, content={"error": "Uploaded PDF file is empty."})
        result = extract_pdf_structured(file_bytes, filename=file.filename, mode="auto")
        extracted_text = result.get("extracted_text", "")
        if not extracted_text:
            return JSONResponse(status_code=422, content={"error": "Could not extract any text from this PDF."})
        return {
            "message": "PDF processed successfully!",
            "filename": file.filename,
            "extracted_text": extracted_text,
            **result
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})