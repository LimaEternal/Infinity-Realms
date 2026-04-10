import time
import json
from flask import jsonify, request
from config import (
    app,
    SYSTEM_PROMPT,
    START_PROMPT,
    SETTING_PROMPT,
    openrouter_client,
    DEFAULT_MODEL,
    game_state,
)
from openrouter import call_openrouter
from image_api import generate_image


@app.route("/")
def index():
    """Главная страница игры"""
    from flask import render_template

    return render_template("index.html")


@app.route("/api/action", methods=["POST"])
def handle_action():
    """Обработка действия игрока"""
    start_time = time.time()

    data = request.json
    action = data.get("action", "")

    if not openrouter_client:
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
        qwen_response = call_openrouter(messages)

        if qwen_response is None:
            raise ValueError("Клиент OpenRouter не инициализирован")

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
    start_time = time.time()

    game_state["history"] = []
    game_state["inventory"] = []
    game_state["effects"] = []
    game_state["location"] = "start"

    if not openrouter_client:
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

            response = call_openrouter(messages)

            if response is None:
                raise ValueError("Клиент OpenRouter не инициализирован")

            if "description" not in response:
                raise ValueError("Отсутствует поле 'description'")

            game_state["history"].append(
                {"action": "start", "response": response["description"]}
            )

            elapsed = time.time() - start_time
            print(f"⏱ Ответ за {elapsed:.2f} сек | Модель: {DEFAULT_MODEL}")

        except json.JSONDecodeError as e:
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


@app.route("/api/image", methods=["GET"])
def generate_image_route():
    """Генерирует уникальное изображение через Pollinations (без кэша)"""
    prompt = request.args.get("prompt", "scene")
    return generate_image(prompt)


@app.route("/api/setting", methods=["POST"])
def choose_setting():
    """Выбор сеттинга для игры"""
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

    if not openrouter_client:
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

        response = call_openrouter(messages)

        if response is None:
            raise ValueError("Клиент OpenRouter не инициализирован")

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
