import aiosqlite
from config import DB_PATH, SCHEMA_PATH


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    with open(SCHEMA_PATH) as f:
        schema = f.read()
    db = await get_db()
    await db.executescript(schema)
    await db.close()


async def log_message(db: aiosqlite.Connection, tenant_id: str, user_id: str | None, direction: str, content: str):
    await db.execute(
        "INSERT INTO messages (tenant_id, user_id, direction, content) VALUES (?, ?, ?, ?)",
        (tenant_id, user_id, direction, content),
    )
    await db.commit()


async def save_conversation(db: aiosqlite.Connection, tenant_id: str, role: str, content: str):
    await db.execute(
        "INSERT INTO conversation (tenant_id, role, content) VALUES (?, ?, ?)",
        (tenant_id, role, content),
    )
    # Keep last 20 messages per tenant
    await db.execute(
        """DELETE FROM conversation WHERE id NOT IN (
            SELECT id FROM conversation WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 20
        ) AND tenant_id = ?""",
        (tenant_id, tenant_id),
    )
    await db.commit()


async def get_conversation_history(db: aiosqlite.Connection, tenant_id: str, limit: int = 10) -> list[dict]:
    cursor = await db.execute(
        "SELECT role, content FROM conversation WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
        (tenant_id, limit),
    )
    rows = await cursor.fetchall()
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]


async def create_task(db: aiosqlite.Connection, tenant_id: str, project: str, summary: str) -> int:
    cursor = await db.execute(
        "INSERT INTO tasks (tenant_id, project, summary) VALUES (?, ?, ?)",
        (tenant_id, project, summary),
    )
    await db.commit()
    return cursor.lastrowid


async def update_task_status(db: aiosqlite.Connection, task_id: int, status: str, result: str | None = None):
    if status == "running":
        await db.execute(
            "UPDATE tasks SET status = ?, started_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, task_id),
        )
    elif status in ("done", "failed"):
        await db.execute(
            "UPDATE tasks SET status = ?, result = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, result, task_id),
        )
    else:
        await db.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    await db.commit()


async def get_pending_confirmation(db: aiosqlite.Connection, tenant_id: str):
    cursor = await db.execute(
        "SELECT * FROM pending_confirmations WHERE tenant_id = ? AND status = 'waiting' ORDER BY created_at DESC LIMIT 1",
        (tenant_id,),
    )
    return await cursor.fetchone()


async def create_pending_confirmation(db: aiosqlite.Connection, tenant_id: str, user_id: str, original_message: str, options: str, task_summary: str):
    await db.execute(
        "INSERT INTO pending_confirmations (tenant_id, user_id, original_message, options, task_summary) VALUES (?, ?, ?, ?, ?)",
        (tenant_id, user_id, original_message, options, task_summary),
    )
    await db.commit()


async def resolve_pending_confirmation(db: aiosqlite.Connection, confirmation_id: int):
    await db.execute(
        "UPDATE pending_confirmations SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (confirmation_id,),
    )
    await db.commit()


async def expire_pending_confirmations(db: aiosqlite.Connection, tenant_id: str):
    await db.execute(
        "UPDATE pending_confirmations SET status = 'expired' WHERE tenant_id = ? AND status = 'waiting'",
        (tenant_id,),
    )
    await db.commit()
