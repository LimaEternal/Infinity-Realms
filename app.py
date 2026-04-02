import os
import json
import re
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
from openai import OpenAI

# Загрузка переменных окружения из .env в корне проекта
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dams-secret-key-change-in-production")

# Загрузка системных промптов из файлов
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


SYSTEM_PROMPT = load_prompt("system.txt")
START_PROMPT = load_prompt("start.txt")
SETTING_PROMPT = load_prompt("setting.txt")


def fix_truncated_json(content):
    """Пытается исправить обрезанный JSON"""
    content = content.strip()

    # Если JSON полный, возвращаем как есть
    if content.endswith("}"):
        try:
            json.loads(content)
            return content
        except:
            pass

    # Если обрезан на ключевом слове (например "image"), добавляем остаток
    if content.endswith('"image'):
        content += '_prompt": "generic scene"}'
    elif content.endswith('"imag'):
        content += 'e_prompt": "generic scene"}'
    elif content.endswith('"im'):
        content += 'age_prompt": "generic scene"}'

    # Пытаемся найти последнюю закрывающую скобку для массивов
    # и добавляем недостающие закрывающие скобки
    open_braces = content.count("{") - content.count("}")
    open_brackets = content.count("[") - content.count("]")
    open_quotes = content.count('"') % 2  # Нечётное = открытая кавычка

    # Закрываем кавычки
    if open_quotes:
        content += '"'

    # Закрываем скобки
    content += "}" * open_braces
    content += "]" * open_brackets

    # Если всё ещё не валидный, пробуем извлечь JSON из начала
    match = re.search(r"\{.*?\}", content, re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            json.loads(candidate)
            return candidate
        except:
            pass

    return content


# Инициализация клиента OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if OPENROUTER_API_KEY:
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )
    print("✅ OpenRouter подключён!")
else:
    client = None
    print("⚠️ OPENROUTER_API_KEY не найден! Нейросеть не будет работать.")

# Модель по умолчанию (бесплатная или дешёвая)
# Варианты: "qwen/qwen3-coder:free", "google/gemma-3-12b-it:free", "meta-llama/llama-3.2-3b-instruct:free"
DEFAULT_MODEL = os.getenv("AI_MODEL", "qwen/qwen3-coder:free")

# Временное хранилище состояния игры (в памяти)
game_state = {"history": [], "inventory": [], "effects": [], "location": "start"}


@app.route("/")
def index():
    """Главная страница игры"""
    return render_template("index.html")


@app.route("/api/action", methods=["POST"])
def handle_action():
    """Обработка действия игрока"""
    import time

    start_time = time.time()

    data = request.json
    action = data.get("action", "")

    if not client:
        return jsonify(
            {
                "description": "⚠️ API не настроен. Добавь ключ в .env файл.",
                "suggestions": ["Настроить API", "Попробовать снова", "Начать заново"],
                "inventory": [],
                "effects": [],
                "image_prompt": "error terminal screen",
            }
        )

    # Формируем историю диалога для контекста
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Добавляем последние 2 хода (экономим токены и время)
    for turn in game_state["history"][-2:]:
        messages.append({"role": "user", "content": turn["action"]})
        messages.append({"role": "assistant", "content": turn["response"]})

    messages.append({"role": "user", "content": action})

    try:
        # Запрос к AI через OpenRouter
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=400,  # Уменьшили для скорости
            response_format={"type": "json_object"},
        )

        # Проверяем, есть ли контент в ответе
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Пустой ответ от AI модели")

        # Пытаемся исправить обрезанный JSON
        content = fix_truncated_json(content)
        qwen_response = json.loads(content)

        # Проверяем обязательные поля
        if "description" not in qwen_response:
            raise ValueError("Отсутствует поле 'description' в ответе AI")

        # Обновляем историю
        game_state["history"].append(
            {"action": action, "response": qwen_response["description"]}
        )

        # Обновляем состояние
        game_state["inventory"] = qwen_response.get("inventory", [])
        game_state["effects"] = qwen_response.get("effects", [])

        # Логгируем время ответа
        elapsed = time.time() - start_time
        print(f"⏱ Ответ за {elapsed:.2f} сек | Модель: {DEFAULT_MODEL}")

        return jsonify(qwen_response)

    except json.JSONDecodeError as e:
        # Логгируем сырой ответ для отладки
        print(f"JSON decode error. Raw content: {content}")
        return jsonify(
            {
                "description": f"Ошибка формата ответа от DaMS. Попробуй другую формулировку.",
                "suggestions": ["Попробовать снова", "Начать заново", "Помощь"],
                "inventory": game_state["inventory"],
                "effects": game_state["effects"],
                "image_prompt": "error terminal glitch",
            }
        )
    except Exception as e:
        return jsonify(
            {
                "description": f"Ошибка DaMS: {str(e)}",
                "suggestions": ["Попробовать снова", "Начать заново", "Помощь"],
                "inventory": game_state["inventory"],
                "effects": game_state["effects"],
                "image_prompt": "error terminal glitch",
            }
        )


@app.route("/api/start", methods=["POST"])
def start_game():
    """Начало новой игры - выбор сеттинга"""
    import time

    start_time = time.time()

    game_state["history"] = []
    game_state["inventory"] = []
    game_state["effects"] = []
    game_state["location"] = "start"

    if not client:
        response = {
            "description": "DaMS загружен. API не настроен — добавь ключ в .env",
            "suggestions": ["Настроить API", "Начать заново"],
            "inventory": [],
            "effects": [],
            "image_prompt": "retro terminal loading screen",
        }
    else:
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": START_PROMPT},
            ]

            response_qwen = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=400,
                response_format={"type": "json_object"},
            )

            content = response_qwen.choices[0].message.content
            if not content:
                raise ValueError("Пустой ответ от AI")

            content = fix_truncated_json(content)
            response = json.loads(content)

            if "description" not in response:
                raise ValueError("Отсутствует поле 'description'")

            game_state["history"].append(
                {"action": "start", "response": response["description"]}
            )

            elapsed = time.time() - start_time
            print(f"⏱ Ответ за {elapsed:.2f} сек | Модель: {DEFAULT_MODEL}")

        except json.JSONDecodeError as e:
            print(f"JSON decode error in start_game. Raw content: {content}")
            response = {
                "description": "Ошибка формата ответа от DaMS. Попробуй начать заново.",
                "suggestions": ["Попробовать снова", "Начать заново"],
                "inventory": [],
                "effects": [],
                "image_prompt": "error terminal",
            }
        except Exception as e:
            response = {
                "description": f"Ошибка запуска DaMS: {str(e)}",
                "suggestions": ["Попробовать снова", "Начать заново"],
                "inventory": [],
                "effects": [],
                "image_prompt": "error terminal",
            }

    return jsonify(response)


@app.route("/api/setting", methods=["POST"])
def choose_setting():
    """Выбор сеттинга для игры"""
    import time

    start_time = time.time()

    data = request.json
    setting = data.get("setting", "1")

    # Словарь сеттингов
    settings_map = {
        "1": "фэнтези (замок, драконы, магия)",
        "2": "научная фантастика (космос, технологии, инопланетяне)",
        "3": "постапокалипсис (разрушенный город, выживание)",
    }

    setting_name = settings_map.get(setting, settings_map["1"])

    if not client:
        return jsonify(
            {
                "description": f"Вы выбрали: {setting_name}. API не настроен.",
                "suggestions": ["Идти вперёд", "Осмотреться", "Назад"],
                "inventory": [],
                "effects": [],
                "image_prompt": "fantasy castle or sci-fi space",
            }
        )

    try:
        # Формируем промпт для выбранного сеттинга
        setting_prompt = SETTING_PROMPT.replace("{setting}", setting_name)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": setting_prompt},
        ]

        response_qwen = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=400,
            response_format={"type": "json_object"},
        )

        content = response_qwen.choices[0].message.content
        if not content:
            raise ValueError("Пустой ответ от AI")

        content = fix_truncated_json(content)
        response = json.loads(content)

        if "description" not in response:
            raise ValueError("Отсутствует поле 'description'")

        # Сохраняем выбор сеттинга в историю
        game_state["location"] = setting
        game_state["history"].append(
            {
                "action": f"Выбор сеттинга: {setting_name}",
                "response": response["description"],
            }
        )

        elapsed = time.time() - start_time
        print(f"⏱ Сеттинг за {elapsed:.2f} сек | {setting_name}")

        return jsonify(response)

    except Exception as e:
        return jsonify(
            {
                "description": f"Ошибка: {str(e)}",
                "suggestions": ["Попробовать снова", "Начать заново"],
                "inventory": [],
                "effects": [],
                "image_prompt": "error terminal",
            }
        )


if __name__ == "__main__":
    # Запуск сервера
    print("🚀 DaMS запускается на http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=5000)
