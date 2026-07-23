import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI()


class DiffRequest(BaseModel):
    left: Union[str, Dict[str, Any]]
    right: Union[str, Dict[str, Any]]
    label_left: str = "Response A"
    label_right: str = "Response B"


class ExtractRequest(BaseModel):
    response: Union[str, Dict[str, Any]]


def parse_json_input(data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(data, dict):
        return data
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        try:
            return json.loads(json.loads(data))
        except (json.JSONDecodeError, TypeError):
            raise ValueError("Invalid JSON input")


def flatten(obj: Any, prefix: str = "") -> Dict[str, Any]:
    """Recursively flatten nested JSON into dot-notation paths."""
    result = {}

    if isinstance(obj, dict):
        for key, value in obj.items():
            new_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, (dict, list)):
                result.update(flatten(value, new_key))
            else:
                result[new_key] = value
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            new_key = f"{prefix}[{idx}]"
            if isinstance(item, (dict, list)):
                result.update(flatten(item, new_key))
            else:
                result[new_key] = item
    else:
        result[prefix] = obj

    return result


def get_finish_reason(flat: Dict[str, Any]) -> Optional[str]:
    """Extract finish_reason from flattened response."""
    if "choices[0].finish_reason" in flat:
        return flat["choices[0].finish_reason"]
    if "stop_reason" in flat:
        return flat["stop_reason"]
    return None


def has_reasoning(flat: Dict[str, Any]) -> bool:
    """Check if response contains reasoning content."""
    reasoning_keys = [
        "choices[0].message.reasoning_content",
        "choices[0].message.thinking",
        "usage.completion_tokens_details.reasoning_tokens",
    ]
    for key in reasoning_keys:
        if key in flat and flat[key]:
            return True
    for key in flat:
        if "reasoning" in key.lower() or "thinking" in key.lower():
            if flat[key]:
                return True
    return False


def detect_format(flat: Dict[str, Any]) -> str:
    """Detect response format from structure."""
    if "choices[0].message" in flat or "choices[0].message.content" in flat:
        return "openai_chat"
    if "content[0].text" in flat and "stop_reason" in flat:
        return "anthropic"
    if "candidates[0].content" in flat:
        return "google"
    return "unknown"


def normalize_response(obj: Dict[str, Any], format: str) -> Dict[str, Any]:
    """Normalize response to a common format if needed."""
    if format == "anthropic":
        normalized = {}
        for key, value in obj.items():
            if key == "content" and isinstance(value, list) and value:
                if isinstance(value[0], dict) and "text" in value[0]:
                    normalized["choices[0].message.content"] = value[0]["text"]
            elif key == "stop_reason":
                normalized["choices[0].finish_reason"] = value
            elif key == "usage":
                if isinstance(value, dict):
                    if "input_tokens" in value:
                        normalized["usage.prompt_tokens"] = value["input_tokens"]
                    if "output_tokens" in value:
                        normalized["usage.completion_tokens"] = value["output_tokens"]
                    if "input_tokens" in value and "output_tokens" in value:
                        normalized["usage.total_tokens"] = (
                            value["input_tokens"] + value["output_tokens"]
                        )
            else:
                normalized[key] = value
        return normalized
    return obj


def word_diff(left_text: str, right_text: str) -> Dict[str, Any]:
    """Compute word-level diff for string values."""
    if not isinstance(left_text, str) or not isinstance(right_text, str):
        return {"left_words": [], "right_words": [], "added": [], "removed": []}

    left_words = left_text.split()
    right_words = right_text.split()

    left_set = set(left_words)
    right_set = set(right_words)

    added = [w for w in right_words if w not in left_set]
    removed = [w for w in left_words if w not in right_set]

    return {
        "left_words": left_words,
        "right_words": right_words,
        "added": added,
        "removed": removed,
    }


def compute_token_delta(
    left_flat: Dict[str, Any], right_flat: Dict[str, Any]
) -> Dict[str, Optional[int]]:
    """Compute token count deltas."""
    left_prompt = left_flat.get("usage.prompt_tokens")
    left_completion = left_flat.get("usage.completion_tokens")
    left_total = left_flat.get("usage.total_tokens")

    right_prompt = right_flat.get("usage.prompt_tokens")
    right_completion = right_flat.get("usage.completion_tokens")
    right_total = right_flat.get("usage.total_tokens")

    return {
        "prompt": (
            right_prompt - left_prompt if right_prompt is not None else None
        )
        if left_prompt is not None
        else None,
        "completion": (
            right_completion - left_completion
            if right_completion is not None
            else None
        )
        if left_completion is not None
        else None,
        "total": (right_total - left_total if right_total is not None else None)
        if left_total is not None
        else None,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/extract")
async def extract(req: ExtractRequest):
    try:
        obj = parse_json_input(req.response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    flat = flatten(obj)
    fmt = detect_format(flat)

    content = flat.get("choices[0].message.content") or flat.get("content[0].text")
    reasoning = flat.get("choices[0].message.reasoning_content") or flat.get(
        "choices[0].message.thinking"
    )
    tool_calls = flat.get("choices[0].message.tool_calls")
    finish_reason = get_finish_reason(flat)
    model = flat.get("model")

    prompt_tokens = flat.get("usage.prompt_tokens")
    completion_tokens = flat.get("usage.completion_tokens")
    total_tokens = flat.get("usage.total_tokens")

    return {
        "content": content,
        "reasoning_content": reasoning,
        "tool_calls": tool_calls or [],
        "finish_reason": finish_reason,
        "model": model,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
        "has_reasoning": has_reasoning(flat),
        "response_format": fmt,
    }


@app.post("/diff")
async def diff(req: DiffRequest):
    try:
        left_obj = parse_json_input(req.left)
        right_obj = parse_json_input(req.right)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    left_fmt = detect_format(flatten(left_obj))
    right_fmt = detect_format(flatten(right_obj))

    left_obj = normalize_response(left_obj, left_fmt)
    right_obj = normalize_response(right_obj, right_fmt)

    left_flat = flatten(left_obj)
    right_flat = flatten(right_obj)

    left_keys = set(left_flat.keys())
    right_keys = set(right_flat.keys())

    added_keys = sorted(right_keys - left_keys)
    removed_keys = sorted(left_keys - right_keys)
    changed_keys = sorted(
        [k for k in left_keys & right_keys if left_flat[k] != right_flat[k]]
    )

    flat_diff = []
    for key in added_keys:
        flat_diff.append(
            {
                "path": key,
                "type": "added",
                "left": None,
                "right": right_flat[key],
            }
        )
    for key in removed_keys:
        flat_diff.append(
            {
                "path": key,
                "type": "removed",
                "left": left_flat[key],
                "right": None,
            }
        )
    for key in changed_keys:
        flat_diff.append(
            {
                "path": key,
                "type": "changed",
                "left": left_flat[key],
                "right": right_flat[key],
            }
        )

    word_diffs = {}
    for key in changed_keys:
        if isinstance(left_flat[key], str) and isinstance(right_flat[key], str):
            word_diffs[key] = word_diff(left_flat[key], right_flat[key])

    token_delta = compute_token_delta(left_flat, right_flat)
    left_finish_reason = get_finish_reason(left_flat)
    right_finish_reason = get_finish_reason(right_flat)
    left_has_reasoning = has_reasoning(left_flat)
    right_has_reasoning = has_reasoning(right_flat)

    return {
        "summary": {
            "added_keys": added_keys,
            "removed_keys": removed_keys,
            "changed_keys": changed_keys,
            "token_delta": token_delta,
            "finish_reason_left": left_finish_reason,
            "finish_reason_right": right_finish_reason,
            "content_changed": any(
                k.endswith(".content") for k in changed_keys
            ),
            "reasoning_present_left": left_has_reasoning,
            "reasoning_present_right": right_has_reasoning,
        },
        "flat_diff": flat_diff,
        "word_diff": word_diffs,
    }


app.mount("/", StaticFiles(directory="static", html=True), name="static")
