"""Token-Prioritized, Non-Restricted Auto-Switching Multi-Provider LLM Router.

Order of providers by token capacity & priority:
1. Google Gemini (1M token context; vision + text)
2. Groq Cloud (131K token context; high token-per-minute Qwen models)
3. OpenRouter Free (64K-131K context; Qwen / DeepSeek / Gemma free endpoints)
4. Local Ollama (unlimited local macOS tokens; Qwen 32K context window)

Zero restricted architecture models are included in this router.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Type

from dotenv import load_dotenv

# Ensure environment variables are loaded fresh with override
load_dotenv(override=True)

logger = logging.getLogger(__name__)

# In-memory cooldown cache for exhausted models: model_key -> timestamp until which it is skipped
_EXHAUSTED_UNTIL: dict[str, float] = {}
COOLDOWN_SECONDS = 300.0  # 5 minutes cooldown on token exhaustion / 429 / 404

# Candidate model chains per provider (strictly non-restricted architectures)
GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
]

GROQ_MODELS = [
    "qwen/qwen3-32b",
    "qwen/qwen3.8-27b",
]

OPENROUTER_MODELS = [
    "qwen/qwen3-32b:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "google/gemma-3-27b-it:free",
]

DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


def is_model_cooling_down(model_key: str) -> bool:
    """Return True if model is currently within its 300-second cooldown period."""
    expiry = _EXHAUSTED_UNTIL.get(model_key, 0.0)
    if expiry > time.time():
        return True
    if model_key in _EXHAUSTED_UNTIL:
        del _EXHAUSTED_UNTIL[model_key]
    return False


def mark_model_exhausted(model_key: str, duration: float = COOLDOWN_SECONDS) -> None:
    """Mark a model as exhausted so future calls skip it in <50ms without failing."""
    until = time.time() + duration
    _EXHAUSTED_UNTIL[model_key] = until
    logger.warning("Model %s marked exhausted until %.1f (%ds cooldown)", model_key, until, int(duration))


def reset_cooldowns() -> None:
    """Reset all cooldowns (useful for unit tests and forced retries)."""
    _EXHAUSTED_UNTIL.clear()


def is_exhaustion_error(exc: Exception) -> bool:
    """Check if an exception is due to token exhaustion, rate limit, context length, or 404."""
    msg = str(exc).lower()
    exhaustion_keywords = (
        "429", "resource_exhausted", "quota", "rate limit", "rate_limit",
        "tokens per minute", "tpm", "requests per minute", "rpm",
        "context_length_exceeded", "maximum context length",
        "insufficient_quota", "overloaded", "capacity", "404", "not_found",
        "model_not_found", "timed out", "timeout"
    )
    if any(kw in msg for kw in exhaustion_keywords):
        return True
    code = getattr(exc, "status_code", getattr(exc, "code", None))
    if code in {404, 429, 503, 504}:
        return True
    return False


def build_unified_prompt(
    system_prompt: str,
    user_message: str,
    chat_history: list[dict] | None = None,
    lease_citations: list[dict] | None = None,
    statute_citations: list[dict] | None = None,
    ledger_audit: dict | None = None,
    search_query: str | None = None,
    attachment_metadata: list[dict] | None = None,
) -> str:
    """Assemble complete multi-turn conversation and retrieved evidence into a unified prompt."""
    history = (chat_history or [])[-12:]
    lines = [
        system_prompt,
        "\nRecent conversation for continuity (oldest first):",
        json.dumps(history, ensure_ascii=False),
        f"\nOriginal user question: {user_message}",
    ]
    if search_query:
        lines.append(f"Standalone retrieval query: {search_query}")
    if lease_citations is not None:
        lines.append(f"Retrieved lease citations: {json.dumps(lease_citations, ensure_ascii=False)}")
    if statute_citations is not None:
        lines.append(f"Retrieved statutory citations: {json.dumps(statute_citations, ensure_ascii=False)}")
    if ledger_audit is not None:
        lines.append(f"Deterministic SQL account/deposit context: {json.dumps(ledger_audit, ensure_ascii=False)}")
    if attachment_metadata:
        filenames = [item.get("filename", "image") for item in attachment_metadata]
        lines.append(f"Images attached to this turn: {json.dumps(filenames, ensure_ascii=False)}")
    return "\n".join(lines)


def build_openai_messages(
    system_prompt: str,
    user_message: str,
    chat_history: list[dict] | None = None,
    lease_citations: list[dict] | None = None,
    statute_citations: list[dict] | None = None,
    ledger_audit: dict | None = None,
    search_query: str | None = None,
    attachment_metadata: list[dict] | None = None,
) -> list[dict[str, str]]:
    """Build OpenAI-compatible message list containing system prompt, history, and assembled evidence."""
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Add prior history turns
    for turn in (chat_history or [])[-12:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        content = str(turn.get("content", ""))
        messages.append({"role": role, "content": content})

    # Assemble user turn content with complete evidence context
    user_content_parts = [user_message]
    context_parts = []
    if search_query:
        context_parts.append(f"Retrieval query: {search_query}")
    if lease_citations:
        context_parts.append(f"Retrieved lease citations: {json.dumps(lease_citations, ensure_ascii=False)}")
    if statute_citations:
        context_parts.append(f"Retrieved statutory citations: {json.dumps(statute_citations, ensure_ascii=False)}")
    if ledger_audit:
        context_parts.append(f"Deterministic SQL ledger audit: {json.dumps(ledger_audit, ensure_ascii=False)}")
    if attachment_metadata:
        filenames = [item.get("filename", "image") for item in attachment_metadata]
        context_parts.append(f"Attached files: {json.dumps(filenames, ensure_ascii=False)}")

    if context_parts:
        user_content_parts.append("\n\n[Grounded Lease & Ledger Context for this turn]:\n" + "\n".join(context_parts))

    messages.append({"role": "user", "content": "\n".join(user_content_parts)})
    return messages


async def _try_gemini_model(
    model_name: str,
    prompt: str,
    image_parts: list[Any] | None = None,
    response_schema: Any = None,
) -> str | None:
    """Attempt generation on a specific Gemini model."""
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=20000, retry_options=types.HttpRetryOptions(attempts=1)),
    )

    contents: Any = prompt
    if image_parts:
        contents = types.Content(role="user", parts=[types.Part.from_text(text=prompt), *image_parts])

    config_kwargs: dict[str, Any] = {"temperature": 0.1}
    if response_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema

    response = await client.aio.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return response.text


async def _try_openai_compatible_model(
    model_name: str,
    base_url: str,
    api_key: str,
    messages: list[dict[str, str]],
    extra_body: dict[str, Any] | None = None,
    response_json: bool = False,
) -> str | None:
    """Attempt generation on an OpenAI-compatible endpoint (Groq, OpenRouter, Ollama)."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=25.0)

    kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.1,
    }
    if extra_body:
        kwargs["extra_body"] = extra_body
    if response_json:
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    if response.choices and response.choices[0].message:
        return response.choices[0].message.content
    return None


async def generate_with_handoff(
    system_prompt: str,
    user_message: str,
    chat_history: list[dict] | None = None,
    lease_citations: list[dict] | None = None,
    statute_citations: list[dict] | None = None,
    ledger_audit: dict | None = None,
    search_query: str | None = None,
    attachments: list[dict] | None = None,
    response_json: bool = False,
    response_schema: Any = None,
) -> tuple[str | None, str | None, str | None]:
    """Token-prioritized multi-provider generation with seamless state & full context handoff.

    Returns:
        (reply_text, active_model_label, handoff_note)
    """
    load_dotenv(override=True)
    attachments = attachments or []
    image_parts: list[Any] = []
    attachment_metadata: list[dict] = []

    # Process image attachments (only Gemini uses raw bytes; downstream models get metadata notes)
    for att in attachments:
        mime = str(att.get("mime_type", ""))
        data = att.get("data")
        if mime in {"image/png", "image/jpeg", "image/webp"} and isinstance(data, bytes) and len(data) <= 10 * 1024 * 1024:
            try:
                from google.genai import types
                image_parts.append(types.Part.from_bytes(data=data, mime_type=mime))
            except Exception:
                pass
            attachment_metadata.append({
                "filename": str(att.get("filename", "image"))[:200],
                "mime_type": mime,
            })

    # Prepare assembled prompts
    full_text_prompt = build_unified_prompt(
        system_prompt=system_prompt,
        user_message=user_message,
        chat_history=chat_history,
        lease_citations=lease_citations,
        statute_citations=statute_citations,
        ledger_audit=ledger_audit,
        search_query=search_query,
        attachment_metadata=attachment_metadata,
    )

    openai_messages = build_openai_messages(
        system_prompt=system_prompt,
        user_message=user_message,
        chat_history=chat_history,
        lease_citations=lease_citations,
        statute_citations=statute_citations,
        ledger_audit=ledger_audit,
        search_query=search_query,
        attachment_metadata=attachment_metadata,
    )

    handoff_note: str | None = None
    had_images = bool(image_parts)

    # ─────────────────────────────────────────────────────────────────────────
    # TIER 1: Google Gemini (1M tokens context, multimodal vision)
    # ─────────────────────────────────────────────────────────────────────────
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        for model_name in GEMINI_MODELS:
            model_key = f"gemini:{model_name}"
            if is_model_cooling_down(model_key):
                logger.info("Skipping cooled-down %s (<50ms fast-path)", model_key)
                continue
            try:
                reply = await _try_gemini_model(
                    model_name=model_name,
                    prompt=full_text_prompt,
                    image_parts=image_parts if had_images else None,
                    response_schema=response_schema,
                )
                if reply and reply.strip():
                    logger.info("Generation succeeded on %s", model_key)
                    return reply.strip(), model_key, None
            except Exception as exc:
                logger.warning("Gemini model %s failed: %s", model_key, exc)
                if is_exhaustion_error(exc):
                    mark_model_exhausted(model_key)

    # If Gemini exhausted while images were attached, record handoff note for text models
    if had_images:
        handoff_note = (
            "Cloud vision model hit token limits. Image pixels were skipped during failover, "
            "but full conversation history, retrieved lease clauses, and ledger audit were preserved."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TIER 2: Groq Cloud (131K tokens, high TPM quota, non-restricted Qwen)
    # ─────────────────────────────────────────────────────────────────────────
    # Support both GROQ_API_KEY and OPENROUTER_API_KEY if user put gsk_ key in OPENROUTER_API_KEY
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        or_key = os.getenv("OPENROUTER_API_KEY", "")
        if or_key.startswith("gsk_"):
            groq_key = or_key

    if groq_key:
        for model_name in GROQ_MODELS:
            model_key = f"groq:{model_name}"
            if is_model_cooling_down(model_key):
                logger.info("Skipping cooled-down %s (<50ms fast-path)", model_key)
                continue
            try:
                reply = await _try_openai_compatible_model(
                    model_name=model_name,
                    base_url="https://api.groq.com/openai/v1",
                    api_key=groq_key,
                    messages=openai_messages,
                    response_json=response_json or (response_schema is not None),
                )
                if reply and reply.strip():
                    logger.info("Generation succeeded on %s with full context preservation", model_key)
                    return reply.strip(), model_key, handoff_note
            except Exception as exc:
                logger.warning("Groq model %s failed: %s", model_key, exc)
                if is_exhaustion_error(exc):
                    mark_model_exhausted(model_key)

    # ─────────────────────────────────────────────────────────────────────────
    # TIER 3: OpenRouter Free Endpoints (64K-131K context window)
    # ─────────────────────────────────────────────────────────────────────────
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key and not openrouter_key.startswith("gsk_"):
        for model_name in OPENROUTER_MODELS:
            model_key = f"openrouter:{model_name}"
            if is_model_cooling_down(model_key):
                logger.info("Skipping cooled-down %s (<50ms fast-path)", model_key)
                continue
            try:
                reply = await _try_openai_compatible_model(
                    model_name=model_name,
                    base_url="https://openrouter.ai/api/v1",
                    api_key=openrouter_key,
                    messages=openai_messages,
                    response_json=response_json or (response_schema is not None),
                )
                if reply and reply.strip():
                    logger.info("Generation succeeded on %s with full context preservation", model_key)
                    return reply.strip(), model_key, handoff_note
            except Exception as exc:
                logger.warning("OpenRouter model %s failed: %s", model_key, exc)
                if is_exhaustion_error(exc):
                    mark_model_exhausted(model_key)

    # ─────────────────────────────────────────────────────────────────────────
    # TIER 4: Local Ollama (Unlimited local tokens on macOS; 32K context window)
    # ─────────────────────────────────────────────────────────────────────────
    ollama_model = DEFAULT_OLLAMA_MODEL
    ollama_key = f"ollama:{ollama_model}"
    if not is_model_cooling_down(ollama_key):
        try:
            reply = await _try_openai_compatible_model(
                model_name=ollama_model,
                base_url="http://localhost:11434/v1",
                api_key="ollama",
                messages=openai_messages,
                extra_body={"options": {"num_ctx": 32768}},
                response_json=response_json or (response_schema is not None),
            )
            if reply and reply.strip():
                logger.info("Generation succeeded on local %s with unlimited tokens", ollama_key)
                return reply.strip(), ollama_key, handoff_note
        except Exception as exc:
            logger.info("Local Ollama endpoint unavailable (%s): %s", ollama_key, exc)
            if is_exhaustion_error(exc):
                mark_model_exhausted(ollama_key, duration=60.0)

    # All models failed or unavailable
    return None, None, handoff_note
