"""
LINE Bot Webhook + Claude Code (with memory per user)
------------------------------------------------------
Requirements:
    pip install flask line-bot-sdk==3.11.0 gunicorn

Setup:
    1. สร้าง LINE Bot ที่ https://developers.line.biz
    2. ตั้งค่า env variables: LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET
    3. รัน: python webhook.py
"""

import os
import json
import subprocess
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ─── CONFIG ──────────────────────────────────────────────────────────────────
CHANNEL_ACCESS_TOKEN = os.environ.get(
    "LINE_CHANNEL_ACCESS_TOKEN",
    "ewWPRgQfuko8TeUAAFPF0C68WM7OUThhELWd9IUIlmmtmq4nBG9Quusf9ZKZx4WtT1IhD+pUzsU/CL69LTlygDqLLgCD1g8DMc9/xnYdH194LKYesJzEftbWhUhgtsAkDQb5ULqlEnm40ak7SHwZwdB04t89/1O/w1cDnyilFU="
)
CHANNEL_SECRET = os.environ.get(
    "LINE_CHANNEL_SECRET",
    "8e757a4bcd76a5de15edfe630bb8f860"
)
SESSIONS_DIR = "sessions"
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

os.makedirs(SESSIONS_DIR, exist_ok=True)


def get_session_id(user_id: str) -> str | None:
    """โหลด session ID ของ user (ถ้ามี)"""
    path = os.path.join(SESSIONS_DIR, f"{user_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f).get("session_id")
    return None


def save_session_id(user_id: str, session_id: str):
    """บันทึก session ID ของ user"""
    path = os.path.join(SESSIONS_DIR, f"{user_id}.json")
    with open(path, "w") as f:
        json.dump({"session_id": session_id}, f)


def ask_claude(user_id: str, message: str) -> str:
    """ส่งข้อความไปถาม Claude Code และคืนคำตอบกลับมา"""
    session_id = get_session_id(user_id)

    cmd = ["claude", "--print", "--output-format", "json"]

    if session_id:
        cmd += ["--resume", session_id]

    cmd.append(message)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return f"[Error]: {result.stderr.strip() or 'Claude Code ไม่ตอบกลับค่ะ'}"

    try:
        data = json.loads(result.stdout)
        new_session_id = data.get("session_id")
        if new_session_id:
            save_session_id(user_id, new_session_id)
        return data.get("result", "").strip()
    except json.JSONDecodeError:
        return result.stdout.strip()


def reply_line(reply_token: str, text: str):
    """ส่งข้อความกลับไปที่ LINE"""
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            )
        )


@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_msg = event.message.text

    # คำสั่งพิเศษ: พิมพ์ "ลืมทุกอย่าง" เพื่อ reset memory
    if user_msg.strip() == "ลืมทุกอย่าง":
        path = os.path.join(SESSIONS_DIR, f"{user_id}.json")
        if os.path.exists(path):
            os.remove(path)
        reply_line(event.reply_token, "ลืมแล้วค่ะ เริ่มใหม่ได้เลย!")
        return

    reply = ask_claude(user_id, user_msg)
    reply_line(event.reply_token, reply)


if __name__ == "__main__":
    print("LINE Bot กำลังรันที่ port 5000 ค่ะ...")
    print(f"Sessions จะถูกเก็บที่โฟลเดอร์: {os.path.abspath(SESSIONS_DIR)}/")
    app.run(port=5000, debug=True)
