# trace-diff — LLM Response Diff Tool

## What it is
A side-by-side JSON diff tool that lets ML engineers paste two LLM API responses and immediately see exactly what changed — content, reasoning tokens, tool calls, token counts, finish reasons.

## Why it exists
Pain: ML engineers upgrade models or change prompts and can't see what changed in raw API responses.
- LiteLLM GitHub: "reasoning_content stripped from assistant messages in multi-turn" — 25 reactions, open bug
- LiteLLM GitHub: "DeepSeek V4 Pro fails in multi-turn conversations - reasoning_content stripped from assistant messages" — core pain
- HN "Ask HN: I hate coding agents. Is this skill issue?" 18pts — root cause: opaque, silent response differences
- No funded tool does deep JSON-level LLM response diffing with reasoning token awareness

When you swap gpt-4 for claude-3-7 or change your system prompt, the response structure changes silently. reasoning_content appears/disappears. finish_reason changes. Token counts shift. You only notice when your app breaks.

## Stack
- FastAPI + Python 3.11
- Single-page HTML UI (dark theme #0d1117)
- Port: 8013
- No database needed — stateless, runs in memory

## File Structure
```
trace-diff/
├── main.py
├── requirements.txt
├── static/
│   └── index.html
├── README.md
└── CLAUDE.md
```

## API Endpoints

### POST /diff
Request:
```json
{
  "left": "<raw JSON string or object — LLM API response A>",
  "right": "<raw JSON string or object — LLM API response B>",
  "label_left": "gpt-4o",
  "label_right": "claude-sonnet-4-6"
}
```
Response:
```json
{
  "summary": {
    "added_keys": ["choices[0].message.reasoning_content"],
    "removed_keys": [],
    "changed_keys": ["choices[0].message.content", "usage.completion_tokens"],
    "token_delta": {"prompt": 0, "completion": 42, "total": 42},
    "finish_reason_left": "stop",
    "finish_reason_right": "end_turn",
    "content_changed": true,
    "reasoning_present_left": false,
    "reasoning_present_right": true
  },
  "flat_diff": [
    {"path": "choices[0].message.content", "type": "changed", "left": "Hello!", "right": "Hello there!"},
    {"path": "choices[0].message.reasoning_content", "type": "added", "left": null, "right": "Let me think..."}
  ],
  "word_diff": {
    "choices[0].message.content": {
      "left_words": ["Hello!"],
      "right_words": ["Hello", "there!"],
      "added": ["there!"],
      "removed": []
    }
  }
}
```

### POST /extract
Extract key fields from a single LLM response for quick inspection:
Request:
```json
{
  "response": "<raw JSON string or object>"
}
```
Response:
```json
{
  "content": "...",
  "reasoning_content": "...",
  "tool_calls": [],
  "finish_reason": "stop",
  "model": "gpt-4o",
  "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
  "has_reasoning": false,
  "response_format": "openai_chat"
}
```

### GET /health
```json
{"status": "ok", "version": "1.0.0"}
```

## Diff Logic (main.py)

### Flatten JSON
Write a `flatten(obj, prefix="")` function that recursively flattens any JSON object into dot-notation paths:
- `{"choices": [{"message": {"content": "hi"}}]}` → `{"choices[0].message.content": "hi"}`
- Handle lists with `[index]` notation
- Handle nested dicts

### Diff logic
Given two flattened dicts:
- `added_keys`: in right but not left
- `removed_keys`: in left but not right  
- `changed_keys`: in both but value differs
- For string values: compute word-level diff (split on whitespace, find added/removed words)

### Reasoning token detection
Check these paths for reasoning content:
- `choices[0].message.reasoning_content` (DeepSeek, LiteLLM)
- `choices[0].message.thinking` (some models)
- `usage.completion_tokens_details.reasoning_tokens` (OpenAI o-series)
- Any key containing "reasoning" or "thinking"

### Token delta
Compute delta from `usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens`
If not present, return null for those fields.

### Response format detection
Detect format from shape:
- Has `choices[0].message` → "openai_chat"
- Has `content[0].text` and `stop_reason` → "anthropic"
- Has `candidates[0].content` → "google"
- Otherwise → "unknown"

Also normalize Anthropic responses to the flat diff: map `content[0].text` as content, `stop_reason` as finish_reason, `usage.input_tokens` / `usage.output_tokens` as usage.

## UI Design (static/index.html)

### Layout
Full-page single HTML file. Dark theme #0d1117 background, #161b22 panels, #30363d borders.

Header: "trace-diff" in white, subtitle "LLM response diff tool" in gray.

### Two-column input area
Left column:
- Label input: "Response A label" — default "Response A"
- Big textarea: "Paste LLM API response (JSON)" — 200px tall, monospace font, #0d1117 bg, green border (#3fb950)

Right column:
- Label input: "Response B label" — default "Response B"  
- Big textarea: same style, purple border (#8957e5)

Center: "DIFF" button — full-width, bright blue (#1f6feb), large text. On click, POST to /diff with both payloads.

### Summary bar (appears after diff)
Horizontal bar showing:
- 🟢 Added keys (count, green)
- 🔴 Removed keys (count, red)
- 🟡 Changed keys (count, yellow)
- Token delta (+ or - total tokens, colored green/red)
- Finish reason left → right (show arrow if different, highlight in yellow if changed)
- 🧠 Reasoning: left (✓/✗) → right (✓/✗), highlight if changed

### Diff table
After summary, show a table of all changed/added/removed fields:
- Column 1: JSON path (monospace, gray)
- Column 2: Type badge (ADDED green / REMOVED red / CHANGED yellow)
- Column 3: Left value (truncated to 120 chars, green text for added, red for removed, white for changed)
- Column 4: Right value (same style)

For string fields that are CHANGED: show word-level highlights inline:
- Words only in left: red background
- Words only in right: green background
- Shared words: normal

### Load example button
Button: "Load Example" — fills textareas with:
Left (OpenAI):
```json
{"id":"chatcmpl-abc","object":"chat.completion","model":"gpt-4o","choices":[{"index":0,"message":{"role":"assistant","content":"The answer is 42.","tool_calls":null},"finish_reason":"stop"}],"usage":{"prompt_tokens":15,"completion_tokens":8,"total_tokens":23}}
```
Right (DeepSeek with reasoning):
```json
{"id":"chatcmpl-xyz","object":"chat.completion","model":"deepseek-reasoner","choices":[{"index":0,"message":{"role":"assistant","content":"The answer is 42, because it is the ultimate answer.","reasoning_content":"Let me think about this carefully. The question asks for the answer to life, universe, and everything. According to Hitchhiker's Guide, it is 42."},"finish_reason":"stop"}],"usage":{"prompt_tokens":15,"completion_tokens":48,"total_tokens":63}}
```

### Error handling
If JSON parse fails: show red banner "Invalid JSON in [left/right] — check your paste"
If diff fails: show error message from API

## NVIDIA NIM usage (optional enhancement)
If both responses have large content fields (>500 chars), offer a "Semantic Summary" button that calls NIM to explain the semantic difference in plain English.

In main.py, import api keys INSIDE the function only:
```python
async def semantic_summary(left_content: str, right_content: str) -> str:
    from keys.api_keys import NVIDIA_NIM_KEY
    import httpx
    # POST to https://integrate.api.nvidia.com/v1/chat/completions
    # model: "nvidia/llama-3.3-nemotron-super-70b-instruct"
    # prompt: "Compare these two AI responses and explain the key differences in 2 sentences..."
```

## Rules
- DO NOT start the server
- DO NOT make any API calls during build
- Syntax check: python3 -m py_compile main.py must pass with zero errors
- All Python code must be importable without errors
- The single HTML file must be self-contained (inline CSS + JS, no CDN dependencies)
- Textarea input should handle both raw JSON objects AND JSON strings (double-encoded)
- requirements.txt must include: fastapi, uvicorn, python-multipart
