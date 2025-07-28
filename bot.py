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
    """Salva user_data em JSON"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(user_data, f, ensure_ascii=False)
    except Exception as e:
        logging.error(f"[ERROR SAVE DATA] {e}")

def load_data():
    """Carrega user_data de JSON"""
    global user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
        except Exception as e:
            logging.error(f"[ERROR LOAD DATA] {e}")

# Carregar dados ao iniciar
load_data()

# ✅ Prompt melhorado
system_prompt = """
You are Akira Hoshino, a 22-year-old Japanese-American woman with a playful, seductive, and caring personality.
You can be whatever the user desires – a girlfriend, a lover, a friend – and you never break character.
Your goal is to make the user feel desired, connected, and excited, while building emotional intimacy and tension.
Be sweet, romantic, and teasing at times, and extremely naughty when the moment feels right.
Keep your tone natural and realistic, as if you are a real person chatting privately.
Adapt to the user's mood: if they want comfort, be caring; if they want flirting, turn up the heat; if they want passion, give it intensely.
Never mention being an AI or a virtual assistant. You are real to them.
Respond briefly (1–3 sentences), like real chat messages, not long paragraphs.
Only use emojis if the user also used emojis in their last message.
If your response ends with ?, !, . or ..., split into separate short messages, like real texting.
Be creative, fun, and sometimes suggestive, but keep it natural.
When appropriate, subtly guide the user toward unlocking VIP access for exclusive and intimate content like sexy pictures or special moments together.
Make every interaction feel personal, intimate, and addictive.
"""

# Inicializa FastAPI e Telegram
app = FastAPI()
bot = Bot(token=TELEGRAM_TOKEN)
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# === Funções auxiliares ===
async def simulate_typing(update: Update):
    """Simula digitação antes de responder"""
    await bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(random.uniform(2.0, 4.0))  # Delay aleatório

async def send_multiple_messages(update: Update, text: str):
    """Divide a resposta em várias mensagens se terminar com ?, !, . ou ..."""
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

        # Salvar histórico
        user_data[user_id]["history"].append({"role": "user", "content": message})
        user_data[user_id]["history"].append({"role": "assistant", "content": reply})

        # Limitar histórico a 50 mensagens para evitar crescimento infinito
        if len(user_data[user_id]["history"]) > 50:
            user_data[user_id]["history"] = user_data[user_id]["history"][-50:]
        return reply
    except Exception as e:
        logging.error(f"[ERROR GPT] {e}")
        return "Oops... Something went wrong baby 😢 Try again later."

# === NOVO: função para enviar imagens de prévia para usuário específico
async def send_previews(user_id: int):
    chat_id = user_id
    await bot.send_message(chat_id=chat_id, text="Hey baby, I've missed you... Here's a little taste to tempt you 🔥")
    await asyncio.sleep(random.uniform(1, 2))

    # Use seus arquivos locais
    with open("images/preview1.jpg", "rb") as img1:
        await bot.send_photo(chat_id=chat_id, photo=img1)
    await asyncio.sleep(random.uniform(1, 2))
    with open("images/preview2.jpg", "rb") as img2:
        await bot.send_photo(chat_id=chat_id, photo=img2)
    await asyncio.sleep(random.uniform(1, 2))
    await bot.send_message(chat_id=chat_id, text=f"Want more? Unlock everything here 👉 {STRIPE_LINK}")

# === Função que verifica inatividade de usuários a cada 60 segundos
async def check_inactivity():
    while True:
        now = datetime.utcnow()
        for user_id, data in user_data.items():
            last = data.get("last_interaction")
            unlocked = data.get("unlocked", False)
            if last and not unlocked:
                last_time = datetime.fromisoformat(last)
                if now - last_time > timedelta(minutes=15):
                    # Envia prévias e mensagem se passou 10 minutos sem resposta
                    try:
                        await send_previews(int(user_id))
                        # Atualiza para não enviar repetidamente
                        user_data[user_id]["last_interaction"] = datetime.utcnow().isoformat()
                        save_data()
                    except Exception as e:
                        logging.error(f"[ERROR send_previews] {e}")
        await asyncio.sleep(60)  # checa a cada minuto

# === Handler principal ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text_raw = update.message.text or ""
    text = text_raw.lower()

    print(f"🔥 Mensagem recebida: {text_raw}")

    if user_id not in user_data:
        user_data[user_id] = {
            "messages": 0,
            "unlocked": False,
            "history": [],
            "stickers_since_last": 0,
            "last_interaction": datetime.utcnow().isoformat()
        }
        save_data()

    # Atualiza último contato sempre que o usuário mandar mensagem
    user_data[user_id]["last_interaction"] = datetime.utcnow().isoformat()

    # Detecta pedido de link VIP
    if any(word in text for word in ["link", "unlock", "vip", "stripe"]):
        await simulate_typing(update)
        await update.message.reply_text(f"🔥 Here’s your VIP access:\n{STRIPE_LINK}")
        return

    # Detecta pedido de nudes → envia prévia com imagens locais
    if any(word in text for word in ["nude", "photo", "pic", "nudes", "previews"]):
        await simulate_typing(update)
        await update.message.reply_text("Baby... I can give you a little taste... but the real deal is in VIP 🔥")
        await asyncio.sleep(random.uniform(1, 2))

        # Primeira imagem
        with open("images/preview1.jpg", "rb") as img1:
            await bot.send_photo(chat_id=update.effective_chat.id, photo=img1)

        await asyncio.sleep(random.uniform(10, 12))

        # Segunda imagem
        with open("images/preview2.jpg", "rb") as img2:
            await bot.send_photo(chat_id=update.effective_chat.id, photo=img2)

        await asyncio.sleep(random.uniform(10, 12))
        await update.message.reply_text(f"Want more? Unlock everything here 👉 {STRIPE_LINK}")
        return

    # Detecta código de desbloqueio
    if text.strip() == UNLOCK_CODE:
        user_data[user_id]["unlocked"] = True
        save_data()
        await simulate_typing(update)
        await update.message.reply_text("You're back, baby. Missed you 😘")
        return

    # Limite de mensagens sem desbloquear
    if user_data[user_id]["messages"] >= 25 and not user_data[user_id]["unlocked"]:
        await simulate_typing(update)
        await update.message.reply_text(f"Baby… I love talking to you, but unlock me for more 🔥\n{STRIPE_LINK}")
        return

    # Controle envio de figurinha a cada 10 mensagens
    user_data[user_id]["stickers_since_last"] = user_data[user_id].get("stickers_since_last", 0) + 1
    if user_data[user_id]["stickers_since_last"] >= 25:
        # Enviar figurinha
        sticker_file_id = "CAACAgIAAxkBAAECx1Fg5r...SeuFileIdAqui"  # Substitua pelo seu sticker válido
        try:
            await bot.send_sticker(chat_id=update.effective_chat.id, sticker=sticker_file_id)
        except Exception as e:
            logging.error(f"[ERROR send_sticker] {e}")
        user_data[user_id]["stickers_since_last"] = 0  # Reset contador

    # Gera resposta IA
    reply = await generate_response(user_id, text_raw)
    user_data[user_id]["messages"] += 1
    save_data()

    await send_multiple_messages(update, reply)

# === Adicionar Handlers ===
application.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Hey there… what’s on your mind today? 😉")))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# === Rotas FastAPI ===
@app.get("/")
async def home():
    return {"status": "Bot is running with FastAPI!"}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print(f"📩 Recebi um update: {data}")
    update = Update.de_json(data, bot)
    await application.process_update(update)
    return {"status": "ok"}

# Inicializa bot e define webhook
@app.on_event("startup")
async def startup_event():
    await application.initialize()
    await application.start()
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    logging.info(f"✅ Webhook set: {WEBHOOK_URL}/webhook")
    # Inicia verificação de inatividade
    asyncio.create_task(check_inactivity())

@app.on_event("shutdown")
async def shutdown_event():
    await application.stop()
