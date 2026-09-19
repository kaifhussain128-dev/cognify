import io
import re
import json
from datetime import datetime
from pypdf import PdfReader

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Backward-compatible helper: extracts raw text from PDF bytes.
    """
    try:
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        extracted_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
        return extracted_text.strip()
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")

def extract_pdf_pages_and_metadata(file_bytes: bytes, filename: str = "") -> dict:
    """
    Parses PDF bytes into per-page structured records and metadata.
    """
    pdf_file = io.BytesIO(file_bytes)
    reader = PdfReader(pdf_file)
    
    pages = []
    raw_text_parts = []
    total_words = 0
    total_chars = 0

    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        words = len(text.split())
        chars = len(text)
        total_words += words
        total_chars += chars
        if text:
            raw_text_parts.append(text)
        pages.append({
            "page_number": i,
            "word_count": words,
            "char_count": chars,
            "text": text
        })

    raw_text = "\n\n".join(raw_text_parts)

    meta = reader.metadata or {}
    clean_meta = {}
    for k, v in meta.items():
        clean_key = k.lstrip("/").lower()
        if isinstance(v, str) and v.strip():
            clean_meta[clean_key] = v.strip()

    return {
        "pages": pages,
        "raw_text": raw_text,
        "total_words": total_words,
        "total_chars": total_chars,
        "metadata": clean_meta
    }

def parse_with_parsli_heuristics(pages: list, raw_text: str, filename: str, metadata: dict) -> dict:
    """
    Fast rule-based heuristic extraction mimicking Parsli structure without consuming AI quota.
    """
    # 1. Document Title
    title = metadata.get("title", "").strip()
    if not title or len(title) < 3:
        # Check first page lines
        if pages and pages[0]["text"]:
            first_lines = [l.strip() for l in pages[0]["text"].splitlines() if l.strip()]
            for line in first_lines[:5]:
                if 4 <= len(line) <= 100 and not re.match(r'^(page\s+\d+|chapter\s+\d+|\d+\.)', line, re.IGNORECASE):
                    title = line
                    break
        if not title:
            base_name = filename.rsplit(".", 1)[0] if filename else "Study Document"
            title = re.sub(r'[-_]+', ' ', base_name).strip().title()

    # 2. Section Headings
    sections = []
    heading_patterns = [
        re.compile(r'^(?:(?:[0-9]+\.)+[0-9]*|[A-Z]\.|\bChapter\s+[0-9]+|\bSection\s+[0-9]+|\bModule\s+[0-9]+)\s+([A-Z].{2,80})$', re.MULTILINE),
        re.compile(r'^[A-Z\s]{4,60}$', re.MULTILINE)
    ]
    
    seen_headings = set()
    for p in pages:
        p_num = p["page_number"]
        lines = p["text"].splitlines()
        for idx, line in enumerate(lines):
            trimmed = line.strip()
            if not trimmed or trimmed in seen_headings or len(trimmed) > 80 or len(trimmed) < 4:
                continue
            matched = False
            for pat in heading_patterns:
                m = pat.match(trimmed)
                if m:
                    heading_text = m.group(1) if m.groups() else trimmed
                    seen_headings.add(trimmed)
                    preview = " ".join(lines[idx+1:idx+4]).strip()[:180]
                    sections.append({
                        "heading": heading_text.title() if heading_text.isupper() else heading_text,
                        "page": p_num,
                        "preview": preview or "Content overview for this section."
                    })
                    matched = True
                    break
            if len(sections) >= 8:
                break
        if len(sections) >= 8:
            break

    if not sections:
        sections.append({
            "heading": "1. Overview & Fundamentals",
            "page": 1,
            "preview": raw_text[:200] + "..." if len(raw_text) > 200 else raw_text
        })

    # 3. Key Concepts & Definitions
    key_concepts = []
    def_regex = re.compile(r'(?:\*|-|•)?\s*(?:\*\*)?([A-Za-z0-9\s\-]{3,35})(?:\*\*)?\s*(?::|—|-|\bis\s+defined\s+as\b|\brefers\s+to\b)\s*([^.\n]+(?:\.[^.\n]+)?)', re.IGNORECASE)
    seen_terms = set()

    for match in def_regex.finditer(raw_text):
        term = re.sub(r'\s+', ' ', match.group(1)).strip()
        defn = re.sub(r'\s+', ' ', match.group(2)).strip()
        term_clean = term.lower()
        if term_clean in seen_terms or len(term) < 3 or len(defn) < 8 or len(term.split()) > 5:
            continue
        seen_terms.add(term_clean)
        key_concepts.append({
            "term": term.title(),
            "definition": defn[:220].rstrip(".;") + ".",
            "importance": "high" if len(key_concepts) < 3 else "medium"
        })
        if len(key_concepts) >= 6:
            break

    if not key_concepts:
        # Fallback terms from title and sections
        words = re.findall(r'\b[A-Z][a-z]{3,}\b', raw_text)
        common_words = [w for w in words if w.lower() not in {"this", "that", "with", "from", "have", "they", "will", "page", "chapter"}]
        for w in dict.fromkeys(common_words)[:4]:
            key_concepts.append({
                "term": w,
                "definition": f"Core academic concept identified within {title}.",
                "importance": "medium"
            })

    # 4. Executive Summary
    summary_sentences = []
    paras = [p.strip() for p in raw_text.split("\n\n") if len(p.strip()) > 60]
    if paras:
        summary_sentences.append(paras[0][:300])
        if len(paras) > 1 and len(paras[-1]) > 50:
            summary_sentences.append(paras[-1][:200])
    summary = " ".join(summary_sentences).strip()
    if not summary:
        summary = f"Structured document synthesis for '{title}'. Contains {len(pages)} pages and {len(key_concepts)} core identified concepts."

    # 5. Suggested Active Recall Questions
    suggested_questions = []
    for kc in key_concepts[:3]:
        suggested_questions.append(f"What is the definition and operational significance of {kc['term']}?")
    for s in sections[:2]:
        suggested_questions.append(f"What are the primary insights presented in '{s['heading']}'?")

    return {
        "title": title,
        "summary": summary,
        "key_concepts": key_concepts,
        "sections": sections,
        "suggested_questions": suggested_questions,
        "raw_text": raw_text
    }

def parse_with_parsli_ai(raw_text: str, genai_client, model_name: str = "gemini-3-flash-preview") -> dict | None:
    """
    AI-powered extraction utilizing Gemini JSON mode to extract typed Parsli schemas.
    """
    if not genai_client or not raw_text.strip():
        return None

    # Limit prompt slice to prevent exceeding context or latency budgets
    sample_text = raw_text[:24000]

    prompt = f"""You are an advanced document data extraction API engine like Parsli (parsli.co).
Analyze the following document text and extract structured data in strict JSON conforming to this schema:
{{
  "title": "Clean, authoritative document title",
  "summary": "2-3 sentence high-yield executive summary of the document",
  "key_concepts": [
    {{
      "term": "Concept or Term Name",
      "definition": "Concise, precise explanation or definition (1-2 sentences)",
      "importance": "high" or "medium"
    }}
  ],
  "sections": [
    {{
      "heading": "Section or Topic Heading",
      "preview": "Brief 1-2 sentence preview of the topic"
    }}
  ],
  "suggested_questions": [
    "Active recall practice question 1 based on text",
    "Active recall practice question 2 based on text"
  ]
}}

Document Text:
{sample_text}
"""

    try:
        from google.genai import types
        response = genai_client.models.generate_content(
            model=model_name,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        if response.text:
            data = json.loads(response.text)
            # Ensure required keys exist
            if "title" in data and "key_concepts" in data:
                data["raw_text"] = raw_text
                return data
    except Exception:
        # Silently fall back to heuristic extraction on 429 quota or parsing errors
        return None

    return None

def extract_pdf_structured(
    file_bytes: bytes,
    filename: str = "",
    mode: str = "auto",
    genai_client = None,
    model_name: str = "gemini-3-flash-preview"
) -> dict:
    """
    Main entry point: extracts structured Parsli-style document data from PDF bytes.
    Modes:
      - 'fast': Rules and regex heuristics (instant, 0 API quota).
      - 'ai': Gemini AI structured parser.
      - 'auto': Attempts Gemini AI, falling back to fast heuristics if unavailable or quota exhausted.
    """
    base = extract_pdf_pages_and_metadata(file_bytes, filename)
    raw_text = base["raw_text"]
    pages = base["pages"]
    metadata = base["metadata"]

    if not raw_text.strip():
        raise ValueError("Could not extract any readable text from this PDF. The document may be empty or an image scan.")

    used_ai = False
    extracted_data = None

    if mode in ("ai", "auto") and genai_client:
        extracted_data = parse_with_parsli_ai(raw_text, genai_client, model_name)
        if extracted_data:
            used_ai = True

    if not extracted_data:
        extracted_data = parse_with_parsli_heuristics(pages, raw_text, filename, metadata)

    return {
        "status": "success",
        "engine": "cognify-parsli-ai-v1" if used_ai else "cognify-parsli-fast-v1",
        "mode": "ai" if used_ai else "fast",
        "processed_at": datetime.utcnow().isoformat() + "Z",
        "document": {
            "filename": filename or "document.pdf",
            "page_count": len(pages),
            "total_words": base["total_words"],
            "total_characters": base["total_chars"],
            "metadata": metadata
        },
        "extracted_data": extracted_data,
        "pages": pages,
        # Backward compatibility key:
        "extracted_text": raw_text
    }