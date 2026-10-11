"""Optional LLM explanation layer. Disabled by default.

The model may only rephrase calculated summaries. It must not recompute
emissions or invent factors. The local rule-based advisor always remains available.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

from src.models import Recommendation


def llm_enabled() -> bool:
    flag = (os.environ.get("ECOTRACE_LLM_ENABLED") or "").strip().lower()
    key = (os.environ.get("ECOTRACE_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    return flag in {"1", "true", "yes"} and bool(key)


def explain_with_llm(
    summary: dict[str, Any],
    recommendations: list[Recommendation],
) -> tuple[Optional[str], str]:
    """Return (text, status). Never raises into the UI."""
    if not llm_enabled():
        return None, "LLM disabled. Using the local rule-based advisor."
    key = (os.environ.get("ECOTRACE_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    base = (os.environ.get("ECOTRACE_LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("ECOTRACE_LLM_MODEL") or "gpt-4o-mini"
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You explain screening LCA results. Use only the JSON provided. "
                    "Do not invent emission factors, percentages, costs, certifications, "
                    "or ISO/CBAM claims. Do not recalculate the footprint. "
                    "If data are missing, say so."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "summary": summary,
                        "recommendations": [r.model_dump() for r in recommendations],
                    },
                    default=str,
                ),
            },
        ],
    }
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = body["choices"][0]["message"]["content"]
        return text, "LLM explanation generated from calculated summaries only."
    except urllib.error.URLError:
        return None, "LLM request failed. Local advisor results are shown instead."
    except (KeyError, IndexError, TimeoutError, json.JSONDecodeError):
        return None, "LLM returned invalid content. Local advisor results are shown instead."
