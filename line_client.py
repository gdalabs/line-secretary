import hashlib
import hmac
import base64
import httpx
from config import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN

LINE_API = "https://api.line.me/v2/bot/message"


def verify_signature(body: str, signature: str) -> bool:
    hash = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(hash).decode("utf-8")
    return hmac.compare_digest(signature, expected)


async def reply_message(reply_token: str, text: str) -> bool:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{LINE_API}/reply",
            headers={"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"},
            json={
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": text}],
            },
        )
        return resp.is_success


async def push_message(user_id: str, text: str):
    # Split long messages (LINE limit: 5000 chars)
    chunks = [text[i : i + 5000] for i in range(0, len(text), 5000)]
    async with httpx.AsyncClient() as client:
        for chunk in chunks:
            await client.post(
                f"{LINE_API}/push",
                headers={"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"},
                json={
                    "to": user_id,
                    "messages": [{"type": "text", "text": chunk}],
                },
            )
