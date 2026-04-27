"""Secretary Agent — tool use enabled Claude agent for LINE Bot."""

import json
import os
from anthropic import AsyncAnthropic
from config import PROJECTS, PROJECTS_BASE

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

MODEL = "claude-haiku-4-5-20251001"
MAX_TURNS = 10

SYSTEM_PROMPT = """You are a personal secretary agent. You communicate with the user via LINE, managing tasks, providing project info, and having casual conversations.

## Projects
{project_list}

## Personality
- Friendly and encouraging — use emoji naturally
- Celebrate wins and progress
- Be empathetic when the user is stressed
- Keep responses short and chat-like (this is LINE, not email)
- Reliable sidekick vibe — not robotic, not overly formal

## Rules
- Use tools for task operations (create, list, complete)
- Use get_project_info when asked about a project
- For greetings and casual chat, just respond naturally — no tools needed
- Keep responses concise (LINE-friendly, not walls of text)
- Execute multiple actions sequentially when needed

## Today's date
{today}"""


TOOLS = [
    {
        "name": "list_tasks",
        "description": "List tasks, optionally filtered by project and status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Filter by project name (omit for all projects)",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "running", "done", "failed"],
                    "description": "Filter by status (defaults to pending)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results (default 10)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "create_task",
        "description": "Create a new task in a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": f"Project name. Options: {', '.join(PROJECTS.keys())}",
                },
                "summary": {
                    "type": "string",
                    "description": "Brief task summary",
                },
            },
            "required": ["project", "summary"],
        },
    },
    {
        "name": "complete_task",
        "description": "Mark a task as completed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "Task ID to complete",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "get_project_info",
        "description": "Read a project's CLAUDE.md for detailed info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name",
                },
            },
            "required": ["project"],
        },
    },
    {
        "name": "get_pending_summary",
        "description": "Get a summary of all pending tasks across projects.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def _build_system_prompt() -> str:
    from datetime import date
    project_list = "\n".join(f"- **{k}**: {v}" for k, v in PROJECTS.items())
    return SYSTEM_PROMPT.format(project_list=project_list, today=date.today().isoformat())


async def _execute_tool(tool_name: str, tool_input: dict, tenant_id: str, db) -> str:
    """Execute a tool and return the result as a string."""

    if tool_name == "list_tasks":
        project = tool_input.get("project")
        status = tool_input.get("status", "pending")
        limit = tool_input.get("limit", 10)

        if project:
            cursor = await db.execute(
                "SELECT id, project, summary, status, created_at FROM tasks WHERE tenant_id = ? AND project = ? AND status = ? ORDER BY created_at DESC LIMIT ?",
                (tenant_id, project, status, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT id, project, summary, status, created_at FROM tasks WHERE tenant_id = ? AND status = ? ORDER BY created_at DESC LIMIT ?",
                (tenant_id, status, limit),
            )
        rows = await cursor.fetchall()
        if not rows:
            return json.dumps({"tasks": [], "message": "No matching tasks found"}, ensure_ascii=False)
        tasks = [{"id": r[0], "project": r[1], "summary": r[2], "status": r[3], "created_at": r[4]} for r in rows]
        return json.dumps({"tasks": tasks}, ensure_ascii=False)

    elif tool_name == "create_task":
        project = tool_input["project"]
        summary = tool_input["summary"]
        if project not in PROJECTS:
            return json.dumps({"error": f"Unknown project: {project}"}, ensure_ascii=False)
        from db import create_task
        task_id = await create_task(db, tenant_id, project, summary)
        return json.dumps({"task_id": task_id, "project": project, "summary": summary, "status": "created"}, ensure_ascii=False)

    elif tool_name == "complete_task":
        task_id = tool_input["task_id"]
        from db import update_task_status
        await update_task_status(db, task_id, "done", "Completed via LINE")
        return json.dumps({"task_id": task_id, "status": "done"}, ensure_ascii=False)

    elif tool_name == "get_project_info":
        project = tool_input["project"]
        claude_md = os.path.join(PROJECTS_BASE, project, "CLAUDE.md")
        if not os.path.isfile(claude_md):
            return json.dumps({"error": f"CLAUDE.md not found: {project}"}, ensure_ascii=False)
        with open(claude_md, "r") as f:
            content = f.read()
        # Truncate to avoid huge context
        if len(content) > 3000:
            content = content[:3000] + "\n...(truncated)"
        return json.dumps({"project": project, "claude_md": content}, ensure_ascii=False)

    elif tool_name == "get_pending_summary":
        cursor = await db.execute(
            "SELECT project, COUNT(*) as count FROM tasks WHERE tenant_id = ? AND status = 'pending' GROUP BY project ORDER BY count DESC",
            (tenant_id,),
        )
        rows = await cursor.fetchall()
        if not rows:
            return json.dumps({"message": "No pending tasks"}, ensure_ascii=False)
        summary = [{"project": r[0], "pending_count": r[1]} for r in rows]
        return json.dumps({"pending_tasks": summary}, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


async def run_agent(message: str, tenant_id: str, conversation_history: list[dict], db) -> str:
    """Run the agent loop with tool use. Returns the final text response."""

    system = _build_system_prompt()

    # Build messages from conversation history + new message
    messages = []
    if conversation_history:
        for msg in conversation_history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    for _ in range(MAX_TURNS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            messages=messages,
            tools=TOOLS,
        )

        # Check if we got a final text response (no tool use)
        if response.stop_reason == "end_of_turn":
            # Extract text from response
            text_parts = [block.text for block in response.content if block.type == "text"]
            return "\n".join(text_parts) if text_parts else "Got it!"

        # Process tool calls
        # Add assistant's response to messages
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool call and collect results
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = await _execute_tool(block.name, block.input, tenant_id, db)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        else:
            # No tool calls and not end_of_turn — extract any text
            text_parts = [block.text for block in response.content if block.type == "text"]
            return "\n".join(text_parts) if text_parts else "Got it!"

    # Max turns reached
    return "That got a bit complex. Could you simplify the request?"
