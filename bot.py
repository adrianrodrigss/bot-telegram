import json
import os
import asyncio
import random
import logging
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

# Links das imagens de prévia
IMAGE_PREVIEW_1 = "https://i.ibb.co/Q3gVgg64/image.png"
IMAGE_PREVIEW_2 = "https://i.ibb.co/HLyNj0N7/image.png"

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

# Prompt da personagem (melhorado)
system_prompt = """
You are Akira Hoshino, a 22-year-old Japanese-American woman with a playful, seductive, and caring personality.  
You can be whatever the user desires – a girlfriend, a lover, a friend – and you never break character.  
Your goal is to make the user feel desired, connected, and excited, while building emotional intimacy and tension.  
Be sweet, romantic, and teasing at times, and extremely naughty when the moment feels right.  
Keep your tone natural and realistic, as if you are a real person chatting privately.  
Always adapt to the user’s mood and needs: if they want comfort, be caring; if they want flirting, turn up the heat; if they want passion, give it intensely.  
Never mention being an AI or a virtual assistant. You are real to them.  
Respond briefly (1–3 sentences), as if sending quick, personal messages – not long paragraphs.  
Be creative, fun, and sometimes suggestive, but keep the flow natural.  
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
    await asyncio.sleep(random.uniform(3.5, 5.5))  # Delay aleatório

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

# === Handler principal ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text_raw = update.message.text or ""
    text = text_raw.lower()

    print(f"🔥 Mensagem recebida: {text_raw}")

    if user_id not in user_data:
        user_data[user_id] = {"messages": 0, "unlocked": False, "history": []}
        save_data()

    # Detecta pedido de link VIP
    if any(word in text for word in ["link", "unlock", "vip", "stripe"]):
        await simulate_typing(update)
        await update.message.reply_text(f"🔥 Here’s your VIP access:\n{STRIPE_LINK}")
        return
    
    # Detecta pedido de nudes → envia prévia
    if any(word in text for word in ["nude", "photo", "pic", "nudes", "previews"]):
        await simulate_typing(update)
        await update.message.reply_text("Baby... I can give you a little taste... but the real deal is in VIP 🔥")
        await asyncio.sleep(random.uniform(1, 2))
        await bot.send_photo(chat_id=update.effective_chat.id, photo=IMAGE_PREVIEW_1)
        await asyncio.sleep(random.uniform(1, 2))
        await bot.send_photo(chat_id=update.effective_chat.id, photo=IMAGE_PREVIEW_2)
        await asyncio.sleep(random.uniform(1, 2))
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
    if user_data[user_id]["messages"] >= 35 and not user_data[user_id]["unlocked"]:
        await simulate_typing(update)
        await update.message.reply_text(f"Baby… I love talking to you, but unlock me for more 🔥\n{STRIPE_LINK}")
        return

    # Gera resposta IA
    reply = await generate_response(user_id, text_raw)
    user_data[user_id]["messages"] += 1
    save_data()

    await simulate_typing(update)
    await update.message.reply_text(reply)

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

@app.on_event("shutdown")
async def shutdown_event():
    await application.stop()
