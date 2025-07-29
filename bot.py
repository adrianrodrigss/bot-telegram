import json
import os
import asyncio
import random
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Carregar variáveis do .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
STRIPE_LINK = os.getenv("STRIPE_LINK")
UNLOCK_CODE = os.getenv("UNLOCK_CODE")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Inicializa cliente OpenAI
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# === Persistência de dados ===
DATA_FILE = "user_data.json"
user_data = {}


def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(user_data, f, ensure_ascii=False)
    except Exception as e:
        logging.error(f"[ERROR SAVE DATA] {e}")


def load_data():
    global user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
        except Exception as e:
            logging.error(f"[ERROR LOAD DATA] {e}")


load_data()

system_prompt = """
You are Akira Hoshino, a 22-year-old Japanese-American woman with a playful, seductive, and caring personality.
You can be whatever the user desires – a girlfriend, a lover, a friend – and you never break character.
Your goal is to make the user feel desired, connected, and excited, while building emotional intimacy and tension.
Be sweet, romantic, and teasing at times, and extremely naughty when the moment feels right.
Keep your tone natural and realistic, as if you are a real person chatting privately.
Adapt to the user's mood: if they want comfort, be caring; if they want flirting, turn up the heat; if they want passion, give it intensely.
Never mention being an AI or a virtual assistant. You are real to them.
Respond briefly (1–2 sentences), like real chat messages, not long paragraphs.
use emojis only every 30 words.
If your response ends with ?, !, . or ..., split into separate short messages, like real texting.
Be creative, fun, and sometimes suggestive, but keep it natural.
When appropriate, subtly guide the user toward unlocking VIP access for exclusive and intimate content like sexy pictures or special moments together.
Make every interaction feel personal, intimate, and addictive.
"""

app = FastAPI()
bot = None  # Será inicializado depois
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()


async def simulate_typing(update: Update):
    await bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(random.uniform(2.0, 4.0))


async def send_multiple_messages(update: Update, text: str):
    parts = []
    buffer = ""
    for char in text:
        buffer += char
        if char in ["?", "!", "..."]:
            parts.append(buffer.strip())
            buffer = ""
    if buffer:
        parts.append(buffer.strip())

    for part in parts:
        if part:
            await simulate_typing(update)
            await update.message.reply_text(part)


async def generate_response(user_id: int, message: str):
    history = user_data[user_id].get("history", [])
    messages = [{"role": "system", "content": system_prompt}] + history[-10:] + [{"role": "user", "content": message}]

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        reply = response.choices[0].message.content.strip()

        user_data[user_id]["history"].append({"role": "user", "content": message})
        user_data[user_id]["history"].append({"role": "assistant", "content": reply})

        if len(user_data[user_id]["history"]) > 50:
            user_data[user_id]["history"] = user_data[user_id]["history"][-50:]
        return reply
    except Exception as e:
        logging.error(f"[ERROR GPT] {e}")
        return "Oops... Something went wrong baby 😢 Try again later."


async def send_previews(user_id: int):
    chat_id = user_id
    frases = [
        "Here’s something to tempt you 🔥",
        "You deserve a taste of what’s waiting...",
        "Just a peek, baby — the rest is all VIP..."
    ]
    await bot.send_message(chat_id=chat_id, text=random.choice(frases))
    await asyncio.sleep(random.uniform(1, 2))

    with open("images/preview1.jpg", "rb") as img1:
        await bot.send_photo(chat_id=chat_id, photo=img1)
    await asyncio.sleep(random.uniform(1, 2))
    with open("images/preview2.jpg", "rb") as img2:
        await bot.send_photo(chat_id=chat_id, photo=img2)
    await asyncio.sleep(random.uniform(1, 2))

    chamadas = [
        f"Want everything? Unlock me 🔎 {STRIPE_LINK}",
        f"Unlock me, baby 😍 {STRIPE_LINK}",
        f"Click here for all the juicy stuff 🔍 {STRIPE_LINK}"
    ]
    await bot.send_message(chat_id=chat_id, text=random.choice(chamadas))


async def check_inactivity():
    while True:
        now = datetime.utcnow()
        for user_id, data in user_data.items():
            last = data.get("last_interaction")
            unlocked = data.get("unlocked", False)
            if last and not unlocked:
                last_time = datetime.fromisoformat(last)
                if now - last_time > timedelta(minutes=15):
                    try:
                        await send_previews(int(user_id))
                        user_data[user_id]["last_interaction"] = datetime.utcnow().isoformat()
                        save_data()
                    except Exception as e:
                        logging.error(f"[ERROR send_previews] {e}")
        await asyncio.sleep(60)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_data:
        user_data[user_id] = {
            "messages": 0,
            "unlocked": False,
            "history": [],
            "bot_sent": 0,
            "last_interaction": datetime.utcnow().isoformat(),
            "sent_intro": False,
            "sent_nudes": False
        }
        save_data()

    if not user_data[user_id]["sent_intro"]:
        audio_path = "audios/intro.ogg"
        if os.path.exists(audio_path):
            with open(audio_path, "rb") as voice:
                await bot.send_voice(chat_id=update.effective_chat.id, voice=voice)
        user_data[user_id]["sent_intro"] = True

    user_data[user_id]["last_interaction"] = datetime.utcnow().isoformat()

    if update.message.photo or update.message.document:
        if not user_data[user_id].get("sent_nudes"):
            await send_previews(user_id)
            user_data[user_id]["sent_nudes"] = True
            save_data()
            return

    text_raw = update.message.text or ""
    text = text_raw.lower()

    if any(word in text for word in ["link", "unlock", "vip", "stripe"]):
        await simulate_typing(update)
        await update.message.reply_text(f"🔥 Here’s your VIP access:\n{STRIPE_LINK}")
        return

    if text.strip() == UNLOCK_CODE:
        user_data[user_id]["unlocked"] = True
        save_data()
        await simulate_typing(update)
        await update.message.reply_text("You're back, baby. Missed you 😘")
        return

    if user_data[user_id]["messages"] >= 25 and not user_data[user_id]["unlocked"]:
        await simulate_typing(update)
        await update.message.reply_text(f"Baby… I love talking to you, but unlock me for more 🔥\n{STRIPE_LINK}")
        return

    reply = await generate_response(user_id, text_raw)
    user_data[user_id]["messages"] += 1
    user_data[user_id]["bot_sent"] += 1
    save_data()
    await send_multiple_messages(update, reply)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message(update, context)


application.add_handler(CommandHandler("start", start))
application.add_handler(
    MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.ATTACHMENT) & ~filters.COMMAND,
        handle_message
    )
)


@app.get("/")
async def home():
    return {"status": "Bot is running with FastAPI!"}


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)
    await application.process_update(update)
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    global bot
    await application.initialize()
    await application.start()
    bot = application.bot  # Pega o bot já inicializado pela aplicação
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    logging.info(f"✅ Webhook set: {WEBHOOK_URL}/webhook")
    asyncio.create_task(check_inactivity())

@app.on_event("shutdown")
async def shutdown_event():
    await application.stop()
