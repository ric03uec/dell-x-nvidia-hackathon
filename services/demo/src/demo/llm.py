"""The decision step, on the box's own model via LiteLLM.

This is the part of the loop that is genuinely a model call: the agent has the
evidence, and asks Qwen3.6-27B which destinations warrant a deny rule and how
severe each is.

Two things learned the hard way against this deployment:

  * Qwen3.6 runs with a reasoning parser, so the reply arrives split — the
    thinking lands in `reasoning_content` and the answer in `content`. A small
    max_tokens is spent entirely on reasoning and returns an EMPTY content with
    finish_reason "stop", which looks like the model refused rather than like a
    truncation. Ask for enough tokens, and read `content`.
  * Nothing here may block the demo. If inference is slow, down, or replies
    with prose, the caller falls back to the deterministic ranking. A demo that
    stalls on a model call is worse than one that says it fell back.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LITELLM = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000")
MODEL = os.environ.get("LITELLM_MODEL", "Qwen3.6-27B-FP8")
ENV_FILE = Path("/home/dell/vllm/env/litellm.env")

SYSTEM = (
    "You are a network security analyst for an egress firewall. You are given "
    "destinations observed leaving a corporate network, with upload volumes and "
    "whether the destination has prior history. Decide which ones to block.\n"
    "Reply with ONLY a JSON array, no prose and no markdown fence. Each element: "
    '{"destination": str, "severity": "critical"|"high"|"medium"|"low", '
    '"block": true|false, "reason": str}. '
    "Block only destinations that look like data exfiltration. Never block a "
    "destination that has prior history and normal volume."
)


@dataclass
class Decision:
    destination: str
    severity: str
    block: bool
    reason: str
    source: str = "llm"


def _api_key() -> str:
    key = os.environ.get("LITELLM_MASTER_KEY", "")
    if key:
        return key
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("LITELLM_MASTER_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    """Tolerate a fence or a stray sentence around the array."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON array in model reply: {text[:200]!r}")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, list):
        raise ValueError("model reply was not a list")
    return parsed


def decide(
    candidates: list[dict[str, Any]], timeout: float = 90.0, max_tokens: int = 1200
) -> tuple[list[Decision], str]:
    """Ask the model which destinations to block.

    Returns (decisions, source) where source is "llm" or "fallback:<reason>",
    so the demo can say out loud which one it used rather than implying a model
    made a call it did not.
    """
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(candidates, indent=2)},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        # Thinking OFF. With it on, Qwen3.6 spent the entire 1200-token budget
        # reasoning and returned EMPTY content after 75s — indistinguishable
        # from a refusal. The decision here is a short classification, not a
        # puzzle, so the reasoning trace buys nothing and costs the demo a
        # minute of dead air.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    request = urllib.request.Request(
        f"{LITELLM}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_api_key()}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = json.load(response)
        content = (body["choices"][0]["message"].get("content") or "").strip()
        if not content:
            # Reasoning consumed the whole budget — see the module docstring.
            return _fallback(candidates, "empty content (reasoning used the token budget)")
        rows = _extract_json_array(content)
    except (urllib.error.URLError, OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        return _fallback(candidates, f"{type(exc).__name__}: {exc}"[:120])

    decisions = [
        Decision(
            destination=str(r.get("destination", "")),
            severity=str(r.get("severity", "medium")),
            block=bool(r.get("block")),
            reason=str(r.get("reason", ""))[:300],
        )
        for r in rows
        if r.get("destination")
    ]
    return (decisions, "llm") if decisions else _fallback(candidates, "model returned no rows")


def _fallback(candidates: list[dict[str, Any]], why: str) -> tuple[list[Decision], str]:
    """Deterministic ranking, used when the model cannot be relied on."""
    decisions = [
        Decision(
            destination=str(c["destination"]),
            severity="critical" if int(c.get("bytes_up", 0)) > 20_000_000 else "high",
            block=not c.get("has_history", False) and int(c.get("bytes_up", 0)) > 1_000_000,
            reason=(
                f"{int(c.get('bytes_up', 0)):,} bytes uploaded"
                + ("" if c.get("has_history") else ", no prior history")
            ),
            source="fallback",
        )
        for c in candidates
    ]
    return decisions, f"fallback:{why}"
