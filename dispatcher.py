import asyncio
import os
from config import PROJECTS_BASE, TASK_TIMEOUT_SECONDS
from db import update_task_status


async def dispatch_task(task_id: int, project: str, summary: str, db) -> str | None:
    project_dir = os.path.join(PROJECTS_BASE, project)

    if not os.path.isdir(project_dir):
        await update_task_status(db, task_id, "failed", f"Project directory not found: {project_dir}")
        return None

    await update_task_status(db, task_id, "running")

    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "--print", summary,
            cwd=project_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=TASK_TIMEOUT_SECONDS,
        )

        result = stdout.decode()
        status = "done" if proc.returncode == 0 else "failed"

        if not result and stderr:
            result = stderr.decode()[:2000]

        await update_task_status(db, task_id, status, result[:5000])
        return result

    except asyncio.TimeoutError:
        proc.kill()
        await update_task_status(db, task_id, "failed", "Timeout: exceeded 5 minutes")
        return "⏱ タイムアウト（5分超過）"
    except Exception as e:
        await update_task_status(db, task_id, "failed", str(e)[:2000])
        return None
