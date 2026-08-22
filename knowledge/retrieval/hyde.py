"""HyDE (Hypothetical Document Embeddings) generation.

Deterministic template fallback by default; optional real LLM call via
LiteLLM when ``LITELLM_BASE_URL`` is configured, with automatic fallback to the
template on any failure. The hypothetical text is a *probe* only and must never
be cited as evidence.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("researchos.knowledge.hyde")

# Config switch, default OFF (matching docs/06). Can be overridden via the
# HYDE_ENABLED env var or a ``hyde_enabled`` setting on KnowledgeSettings.
HYDE_ENABLED = False

HYDE_MODEL = os.environ.get("HYDE_MODEL", "gpt-4o-mini")


def is_hyde_enabled(settings: Any) -> bool:
    raw = os.environ.get("HYDE_ENABLED")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return bool(getattr(settings, "hyde_enabled", False)) or bool(HYDE_ENABLED)


def _template_hyde(query: str, models: list[str] | None = None) -> str:
    """Deterministic pseudo-review paragraph stitching the query keywords."""
    m = "、".join(models) if models else "该产品"
    return (
        f"用户在使用 {m} 时反馈：{query}。"
        "整体体验一般，装配过程略繁琐，个别工况下出现噪音与轻微异响，"
        "扭矩表现符合预期，长期稳定性待观察，存在改进空间。"
    )


def _llm_hyde(query: str, settings: Any, models: list[str] | None = None) -> str | None:
    if not getattr(settings, "litellm_base_url", None):
        return None
    import httpx

    url = settings.litellm_base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if settings.litellm_master_key:
        headers["Authorization"] = f"Bearer {settings.litellm_master_key}"
    prompt = (
        "根据用户问题写一段假设的产品使用评测（非真实证据）。\n"
        f"产品型号：{('、'.join(models) if models else '未指定')}\n"
        f"问题：{query}\n"
        "要求：口语、含具体体验细节、可含痛点；不要编造精确实验室规格数字。"
    )
    payload = {
        "model": HYDE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 220,
        "temperature": 0.7,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.warning("HyDE LLM HTTP %s: %s", resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        choices = data.get("choices") or []
        content = choices[0].get("message", {}).get("content") if choices else None
        if not content or not str(content).strip():
            return None
        return str(content).strip()
    except Exception as exc:  # noqa: BLE001 — fall back to template
        logger.warning("HyDE LLM unavailable: %s", exc)
        return None


def _generate(
    query: str,
    *,
    models: list[str] | None = None,
    settings: Any = None,
    use_llm: bool | None = None,
) -> tuple[str, bool]:
    """Return (hypothetical_document, used_llm)."""
    if settings is None:
        from knowledge.settings import get_settings

        settings = get_settings()
    if use_llm is None:
        use_llm = bool(getattr(settings, "litellm_base_url", None))
    if use_llm:
        doc = _llm_hyde(query, settings, models=models)
        if doc:
            return doc, True
    return _template_hyde(query, models=models), False


def generate_hypothetical_document(
    query: str,
    *,
    models: list[str] | None = None,
    settings: Any = None,
    use_llm: bool | None = None,
) -> str:
    """Generate a hypothetical document; returns the text only."""
    text, _ = _generate(query, models=models, settings=settings, use_llm=use_llm)
    return text
