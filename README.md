<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=180&section=header&text=TRACE-DIFF&fontSize=42&fontColor=fff&animation=twinkling&fontAlignY=32&desc=Swap%20models%2C%20compare%20API%20responses%20side-by-side&descAlignY=55&descSize=16"/>

[![Live Demo](https://img.shields.io/badge/▶_Live_Demo-Visit_Now-6366f1?style=for-the-badge&logoColor=white)](https://trace-diff.vercel.app)
[![GitHub Stars](https://img.shields.io/github/stars/trinathone/trace-diff?style=for-the-badge&color=f59e0b)](https://github.com/trinathone/trace-diff)
[![License](https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge)](LICENSE)

</div>

---

# trace-diff

Ever upgraded a model — say, swapped GPT-4 for Claude Sonnet — and then spent 30 minutes trying to figure out *exactly* what changed in the raw response? Did `reasoning_content` disappear? Did `finish_reason` go from `stop` to `end_turn`? Did your app break because token count format shifted?

That's what trace-diff fixes.

## The problem it solves

ML engineers and AI platform teams swap models constantly. When they do, the API response structure changes silently:
- `reasoning_content` appears or disappears (DeepSeek vs GPT-4o)
- `finish_reason` changes string values between providers
- Token usage fields move around
- Tool calls get added or dropped
- Anthropic, OpenAI, and Google responses have completely different JSON shapes

You only find out when your app breaks in prod. trace-diff shows you the diff *before* that happens.

## Real use cases

1. **Model upgrade check** — Paste your old GPT-4 response next to a new Claude Sonnet response. See every field that changed, added, or disappeared at a glance.

2. **Prompt regression test** — Before and after changing your system prompt, paste both responses to see if the content, reasoning, or token count shifted unexpectedly.

3. **Provider comparison** — Evaluating OpenAI vs Anthropic vs DeepSeek? See their response structure side-by-side — not just the content, but every metadata field.

4. **Debugging missing reasoning tokens** — When your o1 or DeepSeek reasoning content stops showing up, paste the raw API response to instantly see if `reasoning_content` or `completion_tokens_details.reasoning_tokens` is present.

## How it works

1. Paste two raw LLM API JSON responses into the left and right panels
2. Click DIFF
3. See a summary: how many fields were added, removed, or changed — plus token delta and reasoning presence
4. Drill into the field-level table to see exactly what changed, with word-level highlights for content fields

Works with OpenAI, Anthropic, Google (Gemini), DeepSeek, and any LiteLLM-proxied response.

## Quick start

```bash
pip install -r requirements.txt
uvicorn main:app --port 8013
# open http://localhost:8013
```

Or use the API directly:

```bash
curl -X POST http://localhost:8013/diff \
  -H "Content-Type: application/json" \
  -d '{
    "left": "{\"choices\":[{\"message\":{\"content\":\"Hello!\"},\"finish_reason\":\"stop\"}],\"usage\":{\"total_tokens\":20}}",
    "right": "{\"choices\":[{\"message\":{\"content\":\"Hello there!\",\"reasoning_content\":\"...thinking...\"},\"finish_reason\":\"stop\"}],\"usage\":{\"total_tokens\":45}}",
    "label_left": "gpt-4o",
    "label_right": "deepseek-reasoner"
  }'
```

## API

- `POST /diff` — compare two responses, returns summary + field-level diff + word diffs
- `POST /extract` — extract key fields (content, reasoning, finish_reason, usage) from one response
- `GET /health` — health check

## Pain it addresses

- LiteLLM GitHub: ["DeepSeek V4 Pro fails in multi-turn conversations - reasoning_content stripped from assistant messages"](https://github.com/BerriAI/litellm/issues) — 25 reactions, open
- LiteLLM GitHub: Security issue causing engineers to audit raw response payloads manually
- HN: "Ask HN: I hate coding agents. Is this skill issue?" — 18pts — root cause: opaque silent response changes
