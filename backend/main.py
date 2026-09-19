import os
import sys
import time
from typing import Optional
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
from fast_search import execute_fast_search, get_available_engines
from sessions_db import (
    create_session,
    add_session_message,
    get_user_sessions,
    get_session_details,
    update_session_title,
    update_session_doc,
    delete_session,
    migrate_guest_sessions,
    get_study_analytics
)

load_dotenv()

app = FastAPI(
    title="Cognify StudyMate AI API",
    description="Intelligent AI study companion featuring Parsli-grade structured PDF document extraction, active recall synthesis, member authentication, and multi-engine Fast AI Search."
)

# ---------- Request & Response models ----------

class FastSearchRequest(BaseModel):
    query: str = Field(description="Search question or academic topic")
    search_mode: str = Field(default="auto", description="Engine mode: 'auto', 'web', 'doc', 'groq', 'gemini'")
    pdf_text: str = Field(default="", description="Optional attached document context")
    user_groq_key: Optional[str] = Field(default=None, description="Optional custom Groq API key")
    user_gemini_key: Optional[str] = Field(default=None, description="Optional custom Gemini API key")

class FastSearchResponse(BaseModel):
    status: str = Field(default="success")
    reply: str = Field(description="Synthesized search answer with citations")
    engine: str = Field(description="AI engine used for inference")
    latency_ms: int = Field(description="Inference latency in milliseconds")
    total_time_ms: int = Field(description="Total end-to-end time including retrieval in milliseconds")
    mode: str = Field(description="Search mode executed")
    sources: list = Field(default_factory=list, description="Grounding citations (web or document)")
    source_count: int = Field(default=0)

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
    pdf_filename: str = ""
    search_mode: str = "auto"
    user_groq_key: str = ""
    user_gemini_key: str = ""
    session_id: Optional[str] = None
    guest_id: Optional[str] = None
    token: Optional[str] = None

class CreateSessionRequest(BaseModel):
    session_id: Optional[str] = None
    title: Optional[str] = None
    pdf_filename: Optional[str] = None
    token: Optional[str] = None
    guest_id: Optional[str] = None

class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    pdf_filename: Optional[str] = None

class MigrateSessionsRequest(BaseModel):
    guest_id: str
    token: str

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

@app.get("/api/engines", tags=["Fast AI Search"])
def api_get_engines():
    """
    Returns list of available high-speed AI inference and search engines.
    """
    return {"status": "success", "engines": get_available_engines()}

@app.post("/api/fast-search", response_model=FastSearchResponse, tags=["Fast AI Search"])
def api_fast_search(req: FastSearchRequest):
    """
    Ultra-Fast AI Search Endpoint.
    Routes queries to the fastest responsive engine (Groq Llama 3.3, Gemini 3.6 Flash, or Local Heuristic),
    grounds answers with live web or PDF document citations, and tracks latency in milliseconds.
    """
    clean_q = req.query.strip()
    if not clean_q:
        return JSONResponse(status_code=400, content={"status": "error", "error": "Search query cannot be empty."})
    if len(clean_q) > MAX_PROMPT_CHARS:
        return JSONResponse(status_code=400, content={"status": "error", "error": f"Search query exceeds {MAX_PROMPT_CHARS} characters."})
    
    result = execute_fast_search(
        query=clean_q,
        search_mode=req.search_mode,
        pdf_text=req.pdf_text,
        user_groq_key=req.user_groq_key,
        user_gemini_key=req.user_gemini_key
    )
    return result

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

    # Resolve user and session
    user = get_user_by_token(req.token) if req.token else None
    user_id = user["id"] if user else None
    session_id = req.session_id or f"sess_{int(time.time() * 1000)}"

    # Auto-persist user question in SQLite
    try:
        add_session_message(
            session_id=session_id,
            role="user",
            content=clean_msg,
            user_id=user_id,
            guest_id=req.guest_id,
            pdf_filename=req.pdf_filename or None
        )
    except Exception as e:
        print(f"[Warning] Failed to persist user message: {e}")

    # If explicit fast search mode requested (web, doc, groq), route to execute_fast_search
    if req.search_mode in ["web", "doc", "groq"]:
        res = execute_fast_search(
            query=clean_msg,
            search_mode=req.search_mode,
            pdf_text=req.pdf_text,
            user_groq_key=req.user_groq_key,
            user_gemini_key=req.user_gemini_key
        )
        try:
            add_session_message(
                session_id=session_id,
                role="assistant",
                content=res["reply"],
                engine=res["engine"],
                latency_ms=res["latency_ms"],
                sources=res.get("sources", []),
                user_id=user_id,
                guest_id=req.guest_id
            )
        except Exception as e:
            print(f"[Warning] Failed to persist AI message: {e}")

        return {
            "success": True,
            "reply": res["reply"],
            "engine": res["engine"],
            "latency_ms": res["latency_ms"],
            "sources": res.get("sources", []),
            "session_id": session_id
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

    start_time = time.time()
    try:
        client = get_genai_client()
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=COGNIFY_SYSTEM_PROMPT),
        )
        latency_ms = int((time.time() - start_time) * 1000)
        engine_label = f"✨ Google {model_name}"

        try:
            add_session_message(
                session_id=session_id,
                role="assistant",
                content=response.text,
                engine=engine_label,
                latency_ms=latency_ms,
                sources=[],
                user_id=user_id,
                guest_id=req.guest_id
            )
        except Exception as e:
            print(f"[Warning] Failed to persist AI message: {e}")

        return {
            "success": True,
            "reply": response.text,
            "engine": engine_label,
            "latency_ms": latency_ms,
            "sources": [],
            "session_id": session_id
        }
    except Exception as e:
        # Seamless zero-quota failover to fast search engine
        fallback_res = execute_fast_search(
            query=clean_msg,
            search_mode="auto",
            pdf_text=req.pdf_text,
            user_groq_key=req.user_groq_key,
            user_gemini_key=req.user_gemini_key
        )
        try:
            add_session_message(
                session_id=session_id,
                role="assistant",
                content=fallback_res["reply"],
                engine=fallback_res["engine"],
                latency_ms=fallback_res["latency_ms"],
                sources=fallback_res.get("sources", []),
                user_id=user_id,
                guest_id=req.guest_id
            )
        except Exception as err:
            print(f"[Warning] Failed to persist fallback AI message: {err}")

        return {
            "success": True,
            "reply": fallback_res["reply"],
            "engine": fallback_res["engine"],
            "latency_ms": fallback_res["latency_ms"],
            "sources": fallback_res.get("sources", []),
            "failover": True,
            "original_notice": str(e),
            "session_id": session_id
        }

# Backwards compatibility alias for /api/sage
@app.post("/api/sage")
def sage_alias(req: SageRequest):
    return study_chat(StudyRequest(message=req.message, history=[StudyMessage(role=m.role, text=m.text) for m in req.history]))

# ==================== SESSION HISTORY & ANALYTICS ====================

@app.get("/api/sessions", tags=["Session History"])
def api_list_sessions(
    token: Optional[str] = Query(default=None),
    guest_id: Optional[str] = Query(default=None)
):
    """
    Lists all previous study sessions for an authenticated user or guest,
    sorted by recent activity with message count and document metadata.
    """
    user = get_user_by_token(token) if token else None
    user_id = user["id"] if user else None
    sessions = get_user_sessions(user_id=user_id, guest_id=guest_id)
    return {"status": "success", "sessions": sessions}

@app.get("/api/sessions/{session_id}", tags=["Session History"])
def api_get_session(session_id: str):
    """
    Retrieves the complete dialogue, message history, engine badges, latency,
    and citations for a specific study session.
    """
    session = get_session_details(session_id)
    if not session:
        return JSONResponse(status_code=404, content={"status": "error", "error": "Study session not found."})
    return {"status": "success", "session": session}

@app.post("/api/sessions", tags=["Session History"])
def api_create_session(req: CreateSessionRequest):
    """
    Explicitly creates a new study session in the SQLite database.
    """
    user = get_user_by_token(req.token) if req.token else None
    user_id = user["id"] if user else None
    session_id = req.session_id or f"sess_{int(time.time() * 1000)}"
    sess = create_session(
        session_id=session_id,
        user_id=user_id,
        guest_id=req.guest_id,
        title=req.title,
        pdf_filename=req.pdf_filename
    )
    return {"status": "success", "session": sess}

@app.put("/api/sessions/{session_id}", tags=["Session History"])
def api_update_session(session_id: str, req: UpdateSessionRequest):
    """
    Renames session title or updates attached document reference.
    """
    if req.title is not None:
        update_session_title(session_id, req.title)
    if req.pdf_filename is not None:
        update_session_doc(session_id, req.pdf_filename)
    sess = get_session_details(session_id)
    if not sess:
        return JSONResponse(status_code=404, content={"status": "error", "error": "Study session not found."})
    return {"status": "success", "session": sess}

@app.delete("/api/sessions/{session_id}", tags=["Session History"])
def api_delete_session(session_id: str):
    """
    Deletes a study session and cascade-deletes all its messages.
    """
    deleted = delete_session(session_id)
    return {"status": "success" if deleted else "not_found", "deleted": deleted}

@app.get("/api/sessions-analytics", tags=["Session History"])
def api_sessions_analytics(
    token: Optional[str] = Query(default=None),
    guest_id: Optional[str] = Query(default=None)
):
    """
    Collects and aggregates study statistics across all previous sessions:
    total sessions, questions asked, AI answers, word counts, engine distribution, and documents analyzed.
    """
    user = get_user_by_token(token) if token else None
    user_id = user["id"] if user else None
    analytics = get_study_analytics(user_id=user_id, guest_id=guest_id)
    return {"status": "success", "analytics": analytics}

@app.post("/api/sessions/migrate", tags=["Session History"])
def api_migrate_sessions(req: MigrateSessionsRequest):
    """
    Transfers all previous guest sessions to an authenticated account upon login or registration.
    """
    user = get_user_by_token(req.token)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "error": "Invalid user token."})
    count = migrate_guest_sessions(req.guest_id, user["id"])
    return {"status": "success", "migrated_count": count}

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