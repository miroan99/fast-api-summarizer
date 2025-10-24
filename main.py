# =============================
# main.py  — Secure FastAPI Summarizer API (with API key, CORS allowlist, input limits, rate limiting)
# =============================
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, Header, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, conint, constr
import os
import logging
import io
import pdfplumber

from dotenv import load_dotenv

# Rate limiting via slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# --- Load environment variables (.env) ---
load_dotenv()

# OpenAI settings (works with OpenAI or LM Studio if base_url is provided)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")  # e.g. http://localhost:1234/v1 for LM Studio
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# App security settings
API_KEY = os.getenv("API_KEY")  # your own API key for clients calling this service
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]

# Check keys
if OPENAI_BASE_URL and not OPENAI_API_KEY:
    OPENAI_API_KEY = "lm-studio"   # dummy

# --- OpenAI client (SDK v1 style) ---
try:
    from openai import OpenAI

    client = (
        OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        if OPENAI_BASE_URL
        else OpenAI(api_key=OPENAI_API_KEY)
    )
except Exception:
    client = None

logging.basicConfig(level=logging.INFO)

def _summarize_with_model(text: str, max_words: int, language: Optional[str], tone: Optional[str]) -> str:
    if client is None:
        raise HTTPException(status_code=500, detail="OpenAI client not initialized. Check dependencies.")

    if not OPENAI_API_KEY and not OPENAI_BASE_URL:
        raise HTTPException(
            status_code=400,
            detail="Missing OPENAI_API_KEY. Set it in .env. If using LM Studio, set OPENAI_BASE_URL and a dummy key.",
        )

    # Sprogvalg: kun 'da' eller 'en'; ellers ingen tvang
    lang = (language or "").lower()
    lang_part = " Write the summary in Danish (da)." if lang.startswith("da") else (" Write the summary in English (en)." if lang.startswith("en") else "")
    tone_part = f" Tone: {tone}." if tone else ""

    system_msg = (
        f"You are a summarizer. Produce a faithful, concise summary.\n"
        f"Hard constraints:\n"
        f" • Maximum length: {max_words} words.\n"
        f" • Do NOT copy sentences; rephrase. Never quote more than 3 consecutive words from the input.\n"
        f" • Output ONLY the summary text (no intro, no headings).\n"
        f" • If the input is already short, still compress to the essentials."
    )
    user_msg = f"Summarize the following text in at most {max_words} words." + lang_part + tone_part + "\n\n" + text

    try:
        from typing import List, cast
        from openai.types.chat import (
            ChatCompletionMessageParam,
            ChatCompletionSystemMessageParam,
            ChatCompletionUserMessageParam,
        )

        messages: List[ChatCompletionMessageParam] = [
            cast(ChatCompletionSystemMessageParam, {"role": "system", "content": system_msg}),
            cast(ChatCompletionUserMessageParam, {"role": "user", "content": user_msg}),
        ]
        max_tokens_cap = max(64, int(max_words * 2.2))
        chat = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens_cap,
            presence_penalty=0.0,
            frequency_penalty=0.6,
        )
        summary_text = (chat.choices[0].message.content or "").strip()
        if not summary_text:
            raise HTTPException(status_code=500, detail="Model returned empty content.")
        return summary_text
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Model authentication failed. Check API key.")
    except PermissionDeniedError:
        raise HTTPException(status_code=403, detail="Model access denied. Check model permissions.")
    except Exception:
        logging.exception("Summarization failed")
        raise HTTPException(status_code=500, detail="Internal error")

# --- Create app
app = FastAPI(title="Summarizer API", version="0.2.0")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logging.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logging.info(f"Completed with status {response.status_code}")
    return response


# CORS: allow only whitelisted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["authorization", "content-type", "x-api-key"],
)

# Rate limiter (in-memory). For multi-worker/prod, back with Redis via `limits`.
limiter = Limiter(
    key_func=get_remote_address, default_limits=["30/minute"]
)  # default: 30 req/min per IP
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Handle rate limit errors with sanitized message
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429, content={"detail": "Rate limit exceeded. Please slow down."}
    )


# --------- Security: simple API key header ---------
# Clients must send:  X-API-Key: <your key>


def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# --------- Schemas with input limits ---------
class SummarizeRequest(BaseModel):
    text: constr(min_length=1, max_length=10_000) = Field(
        ..., description="Input text to summarize (max 10k chars)"
    )
    max_words: conint(ge=10, le=300) = Field(120, description="Max words in the summary (10-300)")
    language: Optional[str] = Field(
        None, description="Output language code, e.g. 'da' or 'en'. If omitted, auto-detect."
    )
    tone: Optional[str] = Field(
        None, description="Optional tone: 'neutral', 'formal', 'casual', etc."
    )


class SummarizeResponse(BaseModel):
    summary: str
    words: int
    model: str


@app.get("/health")
@limiter.limit("10/second")
async def health(request: Request):  # ← add request: Request
    return {"status": "ok"}


from openai import AuthenticationError, PermissionDeniedError


@app.post("/summarize", response_model=SummarizeResponse, dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
async def summarize(request: Request, payload: SummarizeRequest):
    summary_text = _summarize_with_model(
        text=payload.text,
        max_words=payload.max_words,
        language=payload.language,
        tone=payload.tone,
    )
    return SummarizeResponse(summary=summary_text, words=len(summary_text.split()), model=OPENAI_MODEL)

# ---- File upload endpoint: /summarize-file (.txt and .pdf) ----
@app.post(
    "/summarize-file",
    response_model=SummarizeResponse,
    dependencies=[Depends(require_api_key)],
)
@limiter.limit("5/minute")
async def summarize_file(
    request: Request,
    file: UploadFile = File(...),
    max_words: int = 120,
    language: Optional[str] = None,
    tone: Optional[str] = None,
):
    data = await file.read()
    fname = (file.filename or "").lower()
    ctype = (file.content_type or "").lower()

    if fname.endswith(".txt") or "text/plain" in ctype:
        text = data.decode("utf-8", errors="ignore")
    elif fname.endswith(".pdf") or "application/pdf" in ctype or ".pdf" in fname:
        try:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                pages = [(page.extract_text() or "") for page in pdf.pages]
            text = "\n".join(pages).strip()
        except Exception:
            logging.exception("PDF extraction failed")
            raise HTTPException(status_code=400, detail="Failed to extract text from PDF")
    else:
        raise HTTPException(status_code=415, detail="Unsupported file type. Use .txt or .pdf")

    if not text or text.strip() == "":
        raise HTTPException(status_code=400, detail="No extractable text in file")

    summary_text = _summarize_with_model(text=text, max_words=max_words, language=language, tone=tone)
    return SummarizeResponse(
        summary=summary_text,
        words=len(summary_text.split()),
        model=OPENAI_MODEL,
    )