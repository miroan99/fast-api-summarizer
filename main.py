# =============================
# main.py  — Secure FastAPI Summarizer API (with API key, CORS allowlist, input limits, rate limiting)
# =============================
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, conint, constr
import os
import logging

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

# --- Create app
app = FastAPI(title="Summarizer API", version="0.2.0")

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


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
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
async def summarize(
    request: Request, payload: SummarizeRequest
):  # ← add request: Request (first arg)
    if client is None:
        raise HTTPException(
            status_code=500, detail="OpenAI client not initialized. Check dependencies."
        )

    if not OPENAI_API_KEY and not OPENAI_BASE_URL:
        # For LM Studio, you still need some API key value (can be 'lm-studio')
        raise HTTPException(
            status_code=400,
            detail="Missing OPENAI_API_KEY. Set it in .env. If using LM Studio, set OPENAI_BASE_URL and a dummy key.",
        )

    # Build prompt with minimal metadata; avoid leaking secrets in errors
    lang_hint = (
        f" Danish (da)"
        if (payload.language or "").lower().startswith("da")
        else (" English (en)" if payload.language else "")
    )
    tone_hint = f" Tone: {payload.tone}." if payload.tone else ""

    system_msg = (
        "You are a helpful assistant that writes concise, faithful summaries. "
        "Respect factual accuracy and do not invent details."
    )
    user_msg = (
        f"Summarize the following text in at most {payload.max_words} words.{tone_hint}"
        + (f" Write the summary in{lang_hint}." if lang_hint else "")
        + ""
        + payload.text
    )

    try:
        from typing import List, cast
        from openai.types.chat import (
            ChatCompletionMessageParam,
            ChatCompletionSystemMessageParam,
            ChatCompletionUserMessageParam,
        )

        system_msg_text = system_msg
        user_msg_text = user_msg

        messages: List[ChatCompletionMessageParam] = [
            cast(ChatCompletionSystemMessageParam, cast(object, {"role": "system", "content": system_msg_text})),
            cast(ChatCompletionUserMessageParam, cast(object, {"role": "user", "content": user_msg_text})),
        ]

        chat = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.3,
        )

        summary_text = (chat.choices[0].message.content or "").strip()
        return SummarizeResponse(
            summary=summary_text, words=len(summary_text.split()), model=OPENAI_MODEL
        )

    except AuthenticationError:
        # Wrong/missing scopes or invalid key
        raise HTTPException(
            status_code=401, detail="Model authentication failed. Check API key scopes/project."
        )
    except PermissionDeniedError:
        raise HTTPException(
            status_code=403, detail="Model access denied. Check your project’s model permissions."
        )
    except Exception:
        logging.exception("Summarization failed")  # internal log only
        raise HTTPException(status_code=500, detail="Internal error")
