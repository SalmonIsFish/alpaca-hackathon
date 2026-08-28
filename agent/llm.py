"""Featherless LLM call for the 'propose' step of the pipeline.

Featherless is OpenAI-compatible (base URL https://api.featherless.ai/v1, confirmed against
their docs). The model is only ever shown a pre-filtered, code-verified shortlist -- it picks
an index and writes a rationale, it never invents strikes/premiums/OTM numbers itself. This is
deliberate: it's the one place hallucinated financial data could otherwise reach a gate.

Not unit tested (network + nondeterministic output) -- verify manually against a stub
shortlist once FEATHERLESS_API_KEY is set: check both the happy path and that a malformed or
out-of-range response is correctly caught as LLM_INVALID_RESPONSE, not a crash.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

FEATHERLESS_CHAT_URL = "https://api.featherless.ai/v1/chat/completions"

_SYSTEM_PROMPT = """You are the proposal step of an autonomous options-trading agent. You will \
be given a shortlist of pre-vetted cash-secured-put candidates (already filtered by Shariah \
compliance and deterministic option-selection rules) plus the current account snapshot. \
Choose the single best candidate by index, or decline to trade if none look attractive. \
Respond with ONLY a JSON object, no other text: either \
{"selected_index": <int>, "rationale": "<1-3 sentences>"} or \
{"no_trade": true, "rationale": "<1-3 sentences>"}. \
Do not invent or restate numeric fields beyond what was given to you."""


def build_prompt(candidates: list[dict], account_snapshot: dict) -> str:
    return json.dumps(
        {"candidates": candidates, "account": account_snapshot},
        indent=2,
        default=str,
    )


def call_featherless(prompt: str, *, api_key: str, model: str) -> str:
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        FEATHERLESS_CHAT_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    return payload["choices"][0]["message"]["content"]


def propose_trade(candidates: list[dict], account_snapshot: dict, settings) -> dict:
    if not candidates:
        return {"status": "OK", "no_trade": True, "rationale": "no candidates to consider"}

    prompt = build_prompt(candidates, account_snapshot)
    try:
        raw = call_featherless(
            prompt, api_key=settings.featherless_api_key, model=settings.featherless_model
        )
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError) as exc:
        return {"status": "LLM_CALL_FAILED", "error": str(exc)}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "LLM_INVALID_RESPONSE", "raw": raw}

    if parsed.get("no_trade") is True:
        return {"status": "OK", "no_trade": True, "rationale": parsed.get("rationale", "")}

    index = parsed.get("selected_index")
    if not isinstance(index, int) or not (0 <= index < len(candidates)):
        return {"status": "LLM_INVALID_RESPONSE", "raw": raw}

    return {
        "status": "OK",
        "no_trade": False,
        "selected_index": index,
        "rationale": parsed.get("rationale", ""),
    }
