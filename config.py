import os
from flask import Flask
from dotenv import load_dotenv
from openai import OpenAI

# Загрузка переменных окружения из .env в корне проекта
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)

# Flask приложение
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dams-secret-key-change-in-production")

# Директория с промптами
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def load_prompt(filename):
    """Загружает промпт из файла"""
    filepath = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"⚠️ Промпт {filename} не найден!")
        return ""


# Загрузка системных промптов
SYSTEM_PROMPT = load_prompt("system.txt")
START_PROMPT = load_prompt("start.txt")
SETTING_PROMPT = load_prompt("setting.txt")

# Инициализация клиента OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if OPENROUTER_API_KEY:
    openrouter_client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )
    print("✅ OpenRouter подключён!")
else:
    openrouter_client = None
    print("⚠️ OPENROUTER_API_KEY не найден! Нейросеть не будет работать.")

# Модель по умолчанию (бесплатная или дешёвая)
DEFAULT_MODEL = os.getenv("AI_MODEL", "qwen/qwen3-coder:free")

# Временное хранилище состояния игры (в памяти)
game_state = {"history": [], "inventory": [], "effects": [], "location": "start"}
