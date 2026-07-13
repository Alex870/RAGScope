from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import Counter
from typing import Any

from fastapi import HTTPException


def llm_chat_completion(provider: Any, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    return llm_chat_completion_result(provider, messages, temperature)["content"]


def llm_chat_completion_result(provider: Any, messages: list[dict[str, str]], temperature: float = 0.2) -> dict[str, Any]:
    """Call an OpenAI-compatible endpoint and gracefully retry if the context window is exceeded."""
    base_url = str(provider.base_url or "").strip().rstrip("/")
    model = str(provider.model or "").strip()
    if not base_url:
        raise HTTPException(status_code=400, detail="LLM base URL is required.")
    if not model:
        raise HTTPException(status_code=400, detail="LLM model is required.")
    url = f"{base_url}/chat/completions"
    current_messages = messages
    base_payload = {
        "model": model,
        "messages": current_messages,
        "temperature": temperature,
        "max_tokens": 1400,
    }
    headers = {"Content-Type": "application/json"}
    api_key = str(provider.api_key or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    context_retry = False
    detected_context_window: int | None = None
    while True:
        attempts = [
            {**base_payload, "response_format": {"type": "json_object"}},
            {
                **base_payload,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "rag_audit_json",
                        "schema": {"type": "object", "additionalProperties": True},
                    },
                },
            },
            {**base_payload, "response_format": {"type": "text"}},
            base_payload,
        ]
        last_error = ""
        retry_with_smaller_context = False
        for payload in attempts:
            try:
                body = openai_compatible_chat_request(url, payload, headers)
                choices = body.get("choices") or []
                first_choice = choices[0] if choices else {}
                content = first_choice.get("message", {}).get("content", "") if first_choice else ""
                if content:
                    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
                    return {
                        "content": str(content),
                        "finish_reason": first_choice.get("finish_reason"),
                        "usage": usage,
                        "context_retry": context_retry,
                        "context_window": detected_context_window,
                    }
                last_error = "LLM returned no content."
            except urllib.error.HTTPError as exc:
                last_error = exc.read().decode("utf-8", errors="replace")
                context_window = parse_context_window_error(last_error)
                if context_window and not context_retry:
                    detected_context_window = context_window
                    context_retry = True
                    retry_with_smaller_context = True
                    current_messages = shrink_messages_for_context(current_messages, context_window)
                    base_payload = {
                        **base_payload,
                        "messages": current_messages,
                        "max_tokens": min(700, max(256, context_window // 8)),
                    }
                    break
                if "response_format" not in last_error and "json_schema" not in last_error and "json_object" not in last_error:
                    break
            except Exception as exc:
                last_error = str(exc)
                break
        if retry_with_smaller_context:
            continue
        raise HTTPException(status_code=400, detail=f"LLM request failed: {last_error}")


def openai_compatible_chat_request(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}


def extract_context_length(model_info: Any) -> int | None:
    if not isinstance(model_info, dict):
        return None
    candidate_keys = {
        "context_length",
        "max_context_length",
        "n_ctx",
        "ctx_size",
        "context_window",
        "max_position_embeddings",
        "max_sequence_length",
    }

    def walk(value: Any) -> int | None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key).lower()
                if key_text in candidate_keys or ("context" in key_text and ("length" in key_text or "window" in key_text)):
                    parsed = coerce_positive_int(item)
                    if parsed:
                        return parsed
                found = walk(item)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = walk(item)
                if found:
                    return found
        return None

    return walk(model_info)


def coerce_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def llm_output_diagnostics(raw: str, parsed: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    finish_reason = result.get("finish_reason")
    usage = result.get("usage") or {}
    if finish_reason == "length":
        warnings.append("The LLM stopped because it reached the response token limit. The interpretation may be truncated or degraded.")
    if not parsed:
        warnings.append("The LLM did not return parseable JSON.")
    elif not parsed.get("summary") and not parsed.get("recommended_actions"):
        warnings.append("The LLM returned JSON, but it did not contain the expected audit interpretation fields.")
    if looks_degenerate(raw):
        warnings.append("The LLM output appears repetitive or corrupted. Try a lower temperature, a larger context window, the Limit setting, or a different model.")
    if result.get("context_retry"):
        warnings.append("The first LLM request exceeded the model context window, so the app retried with a smaller prompt.")
    return {
        "warnings": warnings,
        "finish_reason": finish_reason,
        "usage": usage,
        "context_retry": result.get("context_retry", False),
        "context_window": result.get("context_window"),
    }


def looks_degenerate(text: str) -> bool:
    if not text:
        return False
    repeated_words = re.findall(r"([\w'\uAC00-\uD7AF]{3,})(?:\W+\1){8,}", text, flags=re.IGNORECASE)
    if repeated_words:
        return True
    compact = re.sub(r"\s+", "", text)
    for size in (4, 6, 8, 12):
        chunks = [compact[index : index + size] for index in range(0, min(len(compact), 2400), size)]
        if chunks:
            most_common = Counter(chunks).most_common(1)[0][1]
            if most_common >= 18:
                return True
    return False


def parse_context_window_error(text: str) -> int | None:
    match = re.search(r"n_ctx:\s*(\d+)", text, re.IGNORECASE) or re.search(
        r"maximum\s+context\s+length\s+is\s+(\d+)\s+tokens", text, re.IGNORECASE
    )
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def shrink_messages_for_context(messages: list[dict[str, str]], context_window: int) -> list[dict[str, str]]:
    total_budget = max(1800, context_window * 2)
    system_messages = [message for message in messages if message.get("role") == "system"]
    user_messages = [message for message in messages if message.get("role") != "system"]
    system_budget = min(900, total_budget // 4)
    remaining_budget = total_budget - system_budget
    compact: list[dict[str, str]] = []
    for message in system_messages[:1]:
        compact.append({**message, "content": short_backend(message.get("content", ""), system_budget)})
    per_user_budget = max(900, remaining_budget // max(1, len(user_messages)))
    for message in user_messages:
        compact.append({**message, "content": short_backend(message.get("content", ""), per_user_budget)})
    return compact


def shrink_for_llm(value: Any, max_string: int = 900, max_list: int = 12, depth: int = 0) -> Any:
    if depth > 6:
        return short_backend(value, 240)
    if isinstance(value, str):
        return short_backend(value, max_string)
    if isinstance(value, list):
        return [shrink_for_llm(item, max_string, max_list, depth + 1) for item in value[:max_list]]
    if isinstance(value, dict):
        return {str(key): shrink_for_llm(item, max_string, max_list, depth + 1) for key, item in list(value.items())[:40]}
    return value


def short_backend(value: Any, limit: int) -> str:
    text = str(value)
    return text if len(text) <= limit else f"{text[:limit - 1]}..."
