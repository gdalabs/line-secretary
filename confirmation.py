import json
from config import PROJECTS
from db import create_pending_confirmation, resolve_pending_confirmation, create_task


async def create_confirmation_options(db, tenant_id: str, user_id: str, message: str, classification: dict) -> str:
    best_project = classification.get("project", "")
    summary = classification.get("summary", message)

    # Top 3 candidates: best guess first, then others
    top = []
    if best_project and best_project in PROJECTS and best_project != "none":
        top.append(best_project)

    for project in PROJECTS:
        if project not in top and len(top) < 3:
            top.append(project)

    options = []
    for idx, project in enumerate(top, 1):
        options.append({"index": idx, "project": project, "label": project})

    # "Show all" option
    options.append({"index": len(options) + 1, "project": "__show_all__", "label": "一覧を見る"})
    # Skip option
    options.append({"index": len(options) + 1, "project": "__skip__", "label": "スキップ"})

    await create_pending_confirmation(
        db, tenant_id, user_id, message, json.dumps(options, ensure_ascii=False), summary
    )

    lines = [f"📋 「{summary}」\nどのPJに割り振りますか？"]
    for opt in options:
        lines.append(f"  {opt['index']}. {opt['label']}")

    return "\n".join(lines)


async def create_full_list_confirmation(db, tenant_id: str, user_id: str, original_message: str, summary: str) -> str:
    """Show all projects as numbered list."""
    options = []
    for idx, project in enumerate(PROJECTS.keys(), 1):
        options.append({"index": idx, "project": project, "label": project})

    options.append({"index": len(options) + 1, "project": "__skip__", "label": "スキップ"})

    await create_pending_confirmation(
        db, tenant_id, user_id, original_message, json.dumps(options, ensure_ascii=False), summary
    )

    lines = ["📋 全PJ一覧："]
    for opt in options:
        lines.append(f"  {opt['index']}. {opt['label']}")

    return "\n".join(lines)


async def handle_confirmation(db, pending, number: int) -> dict | None:
    options = json.loads(pending["options"])
    selected = next((o for o in options if o["index"] == number), None)

    if not selected:
        return None

    await resolve_pending_confirmation(db, pending["id"])

    if selected["project"] == "__skip__":
        return {"reply": "⏭ スキップしました", "dispatch": False}

    if selected["project"] == "__show_all__":
        return {"reply": "__show_all__", "dispatch": False, "show_all": True,
                "original_message": pending["original_message"], "summary": pending["task_summary"]}

    project = selected["project"]
    summary = pending["task_summary"]
    task_id = await create_task(db, pending["tenant_id"], project, summary)

    return {
        "reply": f"✓ {project} にタスク追加しました\n→ {summary}",
        "dispatch": True,
        "task_id": task_id,
        "project": project,
        "summary": summary,
    }
