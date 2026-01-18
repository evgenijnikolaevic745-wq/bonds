import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
import requests
import time

# --- НАЛАШТУВАННЯ ---
if not firebase_admin._apps:
    firebase_key_json = os.environ.get("FIREBASE_KEY")
    if firebase_key_json:
        try:
            cred_dict = json.loads(firebase_key_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            print(f"❌ Помилка FIREBASE_KEY: {e}")
            exit(1)
    else:
        print("❌ Помилка: Немає змінної FIREBASE_KEY")
        exit(1)

db = firestore.client()
TG_TOKEN = os.environ.get("TG_BOT_TOKEN")

# ✅ 1. ВАШЕ ПОСИЛАННЯ НА ДОДАТОК
WEB_APP_URL = "https://incomparable-lolly-891d01.netlify.app/"

# ✅ 2. ВАШЕ НОВЕ ПРЯМЕ ПОСИЛАННЯ НА ЗОБРАЖЕННЯ
IMAGE_URL = "https://i.ibb.co/27tvHxn2/IMG-1846.jpg"

def send_update_message(chat_id):
    if not TG_TOKEN: return
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    
    # Текст повідомлення (підпис до фото)
    message_text = (
        "<b>🔥 Оновлення InvestPro: додавайте записи одним реченням!</b>\n\n"
        "Забудьте про ручне заповнення полів та калькулятор. Ми додали функцію \"розумний ввід\", яка виконує роботу за вас.\n\n"
        "<b>Як це працює?</b>\n"
        "Ви просто пишете в полі: <code>сьогодні 30 шт на 32079 грн</code>\n\n"
        "Додаток миттєво обробить текст і сам:\n"
        "🔹 Виставить дату сьогоднішнім днем.\n"
        "🔹 Впише кількість: 30 шт.\n"
        "🔹 Порахує ціну за одну облігацію (32079 ÷ 30 = 1069.3 грн) і підставить її у відповідне поле.\n\n"
        "<b>Що ще він вміє?</b>\n"
        "• Розпізнає банки для кредитів: напишіть <code>sense 20000 до 18.02</code> — і система автоматично обере банк, впише суму та розрахує дедлайн.\n"
        "• Розуміє слова: \"вчора\", \"завтра\", \"28 січня\".\n\n"
        "Натисніть кнопку, щоб спробувати 👇"
    )

    payload = {
        "chat_id": chat_id,
        "photo": IMAGE_URL,       # Ваше нове посилання
        "caption": message_text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {
                    "text": "✨ Спробувати нову функцію",
                    "web_app": {"url": WEB_APP_URL}
                }
            ]]
        }
    }

    try:
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            print(f"✅ Надіслано: {chat_id}")
            return True
        elif response.status_code == 403:
            print(f"🔕 Бот заблокований користувачем: {chat_id}")
        else:
            print(f"⚠️ Помилка {chat_id}: {response.text}")
    except Exception as e:
        print(f"❌ Помилка з'єднання: {e}")
    
    time.sleep(0.04) # Ліміт
    return False

def run_global_broadcast():
    print("📢 Починаємо ГЛОБАЛЬНУ розсилку (з ФОТО)...")
    
    all_users = set()

    # 1. Збираємо з users
    try:
        users_ref = db.collection('users').stream()
        for user in users_ref:
            if user.id.startswith('tg_'):
                all_users.add(user.id.replace('tg_', ''))
    except Exception as e:
        print(f"Помилка при скануванні users: {e}")

    # 2. Збираємо з credits
    try:
        credits_ref = db.collection_group('credits').stream()
        for cred in credits_ref:
            owner = cred.reference.parent.parent
            if owner and owner.id.startswith('tg_'):
                all_users.add(owner.id.replace('tg_', ''))
    except Exception as e:
        print(f"Помилка при скануванні credits: {e}")

    # 3. Збираємо з bonds
    try:
        bonds_ref = db.collection_group('bonds').stream()
        for bond in bonds_ref:
            owner = bond.reference.parent.parent
            if owner and owner.id.startswith('tg_'):
                all_users.add(owner.id.replace('tg_', ''))
    except Exception as e:
        print(f"Помилка при скануванні bonds: {e}")

    total = len(all_users)
    print(f"🎯 Всього знайдено унікальних користувачів: {total}")
    print("-" * 30)

    sent_count = 0
    for chat_id in all_users:
        success = send_update_message(chat_id)
        if success:
            sent_count += 1
            
    print("-" * 30)
    print(f"🏁 Розсилку завершено! Успішно доставлено: {sent_count} з {total}")

if __name__ == "__main__":
    run_global_broadcast()
