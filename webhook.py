"""
LINE Bot Webhook + Claude Code (with memory per user)
------------------------------------------------------
Requirements:
    pip install flask line-bot-sdk

Setup:
    1. สร้าง LINE Bot ที่ https://developers.line.biz
    2. ใส่ CHANNEL_ACCESS_TOKEN และ CHANNEL_SECRET ด้านล่าง
    3. รัน: python webhook.py
    4. รัน ngrok: ngrok http 5000
    5. เอา ngrok URL ไปใส่ใน LINE Developers → Webhook URL
"""

import os
import json
import subprocess
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# ─── CONFIG ──────────────────────────────────────────────────────────────────
# รองรับทั้ง local (hardcode) และ Render (env variable)
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
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

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

    cmd = [
        "claude",
        "--print",
        "--output-format", "json",
    ]

    # ถ้ามี session เดิม → ให้จำบทสนทนาต่อ
    if session_id:
        cmd += ["--resume", session_id]

    cmd.append(message)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return f"[Error]: {result.stderr.strip() or 'Claude Code ไม่ตอบกลับค่ะ'}"

    try:
        data = json.loads(result.stdout)
        # บันทึก session ID ใหม่ทุกครั้ง
        new_session_id = data.get("session_id")
        if new_session_id:
            save_session_id(user_id, new_session_id)
        return data.get("result", "").strip()
    except json.JSONDecodeError:
        return result.stdout.strip()


@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_msg = event.message.text

    # คำสั่งพิเศษ: พิมพ์ "ลืมทุกอย่าง" เพื่อ reset memory
    if user_msg.strip() == "ลืมทุกอย่าง":
        path = os.path.join(SESSIONS_DIR, f"{user_id}.json")
        if os.path.exists(path):
            os.remove(path)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="ลืมแล้วค่ะ เริ่มใหม่ได้เลย!")
        )
        return

    reply = ask_claude(user_id, user_msg)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )


if __name__ == "__main__":
    print("LINE Bot กำลังรันที่ port 5000 ค่ะ...")
    print(f"Sessions จะถูกเก็บที่โฟลเดอร์: {os.path.abspath(SESSIONS_DIR)}/")
    app.run(port=5000, debug=True)
