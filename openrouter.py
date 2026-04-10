import json
import re
from config import openrouter_client, DEFAULT_MODEL, SYSTEM_PROMPT, game_state


def clean_json_response(content):
    """Извлекает JSON из ответа, убирая мусор и чиня обрезанный JSON"""
    print(f"📥 Сырой ответ от модели: {content[:200]}...")

    content = content.strip()

    # Убираем HTML-подобые теги
    content = re.sub(r'<[^>]+>', '', content)

    # 1. Если JSON полный — возвращаем
    if content.endswith("}"):
        try:
            json.loads(content)
            return content
        except:
            pass

    # 2. Ищем валидный JSON от { до }
    start = content.find('{')
    if start != -1:
        for end in range(content.rfind('}'), start, -1):
            candidate = content[start:end + 1]
            try:
                json.loads(candidate)
                return candidate
            except:
                continue

    # 3. Если JSON обрезан — пытаемся починить
    if start != -1:
        fixed = content[start:]

        # Находим последнее корректное место (перед обрезанным текстом)
        # Удаляем оборванный хвост после последней закрывающей скобки/кавычки
        last_good = max(
            fixed.rfind('}'),
            fixed.rfind(']'),
            fixed.rfind('"') if fixed.count('"') % 2 == 0 else fixed.rfind('"', 0, fixed.rfind('"'))
        )
        if last_good > 0 and last_good < len(fixed) - 5:
            # Если есть большой хвост после последней хорошей позиции — обрезаем
            potential = fixed[:last_good + 1]
            # Проверяем не обрываем ли мы строку
            if potential.count('"') % 2 == 0:
                fixed = potential

        # Закрываем открытую кавычку
        if fixed.count('"') % 2 != 0:
            fixed += '"'

        # Закрываем незакрытые объекты/массивы
        open_braces = fixed.count('{') - fixed.count('}')
        open_brackets = fixed.count('[') - fixed.count(']')
        fixed += '}' * open_braces + ']' * open_brackets

        try:
            json.loads(fixed)
            print(f"🔧 Починили обрезанный JSON")
            return fixed
        except:
            # Если не вышло, пробуем минимальный fallback JSON
            print(f"⚠️ Стандартная починка не сработала, используем fallback")
            return '{"description": "Ошибка обработки ответа. Попробуйте другое действие.", "suggestions": ["Попробовать снова", "Начать заново"], "inventory": [], "effects": [], "image_prompt": "error terminal"}'

    print(f"❌ Не удалось извлечь JSON. Контент: {content[:300]}")
    raise ValueError("Не удалось извлечь JSON из ответа")


def call_openrouter(messages, max_tokens=1000, temperature=0.7):
    """Вызов OpenRouter API с переданными сообщениями"""
    if not openrouter_client:
        return None

    response = openrouter_client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )

    # Проверяем, есть ли контент в ответе
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Пустой ответ от AI модели")

    # Извлекаем и чистим JSON
    content = clean_json_response(content)
    return json.loads(content)
