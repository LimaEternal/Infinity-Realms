import re
import requests as req
from urllib.parse import quote


def generate_image(prompt):
    """Генерирует уникальное изображение через Pollinations (без кэша)"""
    try:
        # Разбиваем слитные слова и чистим
        spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", prompt)
        spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
        parts = []
        for word in spaced.split():
            if word.isupper() and len(word) > 6:
                parts.extend([word[i : i + 4] for i in range(0, len(word), 4)])
            else:
                parts.append(word)
        clean = " ".join(parts)
        clean = re.sub(r"[^a-zA-Z\s]", "", clean)
        words = clean.split()[:6]
        full_prompt = " ".join(words).lower()
        print(f"🎨 '{prompt}' → '{full_prompt}'")

        safe_prompt = quote(full_prompt)
        # Уникальный seed = каждый раз новая картинка, соотношение 16:9
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=800&height=450&nologo=true&model=flux&seed={abs(hash(full_prompt + str(prompt)))}"

        # 3 попытки
        for attempt in range(3):
            try:
                response = req.get(url, timeout=60)
                if response.status_code == 200:
                    print(f"✅ Картинка готова (попытка {attempt + 1})")
                    return (
                        response.content,
                        200,
                        {"Content-Type": "image/jpeg", "Cache-Control": "no-store"},
                    )
                else:
                    print(
                        f"⚠️ Pollinations вернул {response.status_code} (попытка {attempt + 1})"
                    )
            except req.exceptions.Timeout:
                print(f"⏳ Таймаут (попытка {attempt + 1}/3)")
                continue

        print(f"❌ Pollinations не ответил за 3 попытки")
        return b"", 200, {"Content-Type": "image/jpeg"}
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return b"Error", 500
