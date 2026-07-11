"""
LINE Bot Webhook + Claude AI (with memory per user)
----------------------------------------------------
Requirements:
    pip install flask line-bot-sdk==3.11.0 anthropic gunicorn
"""

import os
import json
from flask import Flask, request, abort
import anthropic
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
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SESSIONS_DIR = "sessions"
MAX_HISTORY = 20  # เก็บบทสนทนาล่าสุด 20 ข้อความต่อ user
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

os.makedirs(SESSIONS_DIR, exist_ok=True)


def load_history(user_id: str) -> list:
    path = os.path.join(SESSIONS_DIR, f"{user_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def save_history(user_id: str, history: list):
    path = os.path.join(SESSIONS_DIR, f"{user_id}.json")
    with open(path, "w") as f:
        json.dump(history[-MAX_HISTORY:], f, ensure_ascii=False)


def ask_claude(user_id: str, message: str) -> str:
    history = load_history(user_id)
    history.append({"role": "user", "content": message})

    try:
        response = claude.messages.create(
            model="claude-opus-4-8",
            max_tokens=1024,
            system="คุณเป็น AI Assistant ที่ฉลาดและเป็นมิตร ตอบเป็นภาษาไทยถ้าผู้ใช้พูดภาษาไทย",
            messages=history,
        )
        reply = response.content[0].text
        history.append({"role": "assistant", "content": reply})
        save_history(user_id, history)
        return reply
    except Exception as e:
        return f"เกิดข้อผิดพลาดค่ะ: {str(e)}"


def reply_line(reply_token: str, text: str):
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
    app.run(port=5000, debug=True)
