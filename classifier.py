import json
import os
from anthropic import AsyncAnthropic
from config import PROJECTS

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

SYSTEM_PROMPT = """You are a project classifier for a sole proprietor's task management system.
Given a LINE message, determine:
1. Which project it belongs to (or "none" if unclear)
2. Your confidence (0.0-1.0)
3. A brief task summary
4. The action type: "task" or "chat"

Available projects:
{project_list}

RULES:
- "chat" = ONLY for greetings ("おはよう"), simple questions about the bot itself, or completely unrelated casual talk
- "task" = ANY request, instruction, question about work, schedule, planning, or anything that could be acted on
- When in doubt, use "task" with low confidence — the user will be asked to choose a project
- If the user mentions something that sounds like work/action but you can't determine the project, set action to "task" with confidence 0.3 and project "none"
- Include a short friendly reply in Japanese

Reply with ONLY valid JSON (no markdown):
{{"project": "name", "confidence": 0.9, "summary": "brief task description", "action": "task", "reply": "optional chat reply"}}"""


def _build_prompt() -> str:
    project_list = "\n".join(f"- {k}: {v}" for k, v in PROJECTS.items())
    return SYSTEM_PROMPT.format(project_list=project_list)


async def classify(message: str, conversation_history: list[dict] | None = None) -> dict:
    prompt = _build_prompt()

    messages = []
    if conversation_history:
        for msg in conversation_history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=prompt,
        messages=messages,
    )

    output = response.content[0].text.strip()

    # Strip markdown code blocks if present
    if output.startswith("```"):
        lines = output.split("\n")
        output = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        # Try to extract JSON from mixed output
        import re
        match = re.search(r'\{[^{}]*\}', output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # Final fallback: treat as chat reply, never show raw JSON to user
        clean = output
        if clean.startswith("{"):
            clean = "メッセージを受け取りました。もう少し詳しく教えてください！"
        return {"action": "chat", "reply": clean[:500], "confidence": 0, "project": "", "summary": ""}
