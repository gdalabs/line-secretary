import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from db import get_db, init_db, log_message, save_conversation, get_conversation_history
from line_client import verify_signature, reply_message, push_message
from agent import run_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Secretary Hub", lifespan=lifespan)


@app.get("/")
async def health():
    return {"status": "ok", "name": "secretary-hub"}


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    body_text = body.decode("utf-8")
    signature = request.headers.get("x-line-signature", "")

    if not verify_signature(body_text, signature):
        return Response("Invalid signature", status_code=401)

    data = json.loads(body_text)

    for event in data.get("events", []):
        if event.get("type") != "message" or event.get("message", {}).get("type") != "text":
            continue

        text = event["message"]["text"]
        group_id = event["source"].get("groupId") or event["source"].get("roomId")
        user_id = event["source"].get("userId")
        tenant_id = group_id or user_id or "unknown"
        reply_to = group_id or user_id  # Reply to where the message came from
        reply_token = event.get("replyToken")

        # Process in background to return 200 immediately
        asyncio.create_task(
            process_message(tenant_id, user_id, reply_to, text, reply_token)
        )

    return Response("OK", status_code=200)


async def process_message(tenant_id: str, user_id: str | None, reply_to: str | None, text: str, reply_token: str | None):
    db = await get_db()
    try:
        await log_message(db, tenant_id, user_id, "in", text)
        await save_conversation(db, tenant_id, "user", text)

        # Run agent with conversation context
        history = await get_conversation_history(db, tenant_id)
        reply = await run_agent(text, tenant_id, history, db)

        await log_message(db, tenant_id, user_id, "out", reply)
        await save_conversation(db, tenant_id, "assistant", reply)
        if reply_to:
            await push_message(reply_to, reply)

    except Exception as e:
        error_msg = f"⚠️ エラーが発生しました: {str(e)[:200]}"
        if reply_to:
            await push_message(reply_to, error_msg)
    finally:
        await db.close()


