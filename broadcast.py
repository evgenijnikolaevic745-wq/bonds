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

# Ваше посилання
WEB_APP_URL = "https://incomparable-lolly-891d01.netlify.app/"

def send_update_message(chat_id):
    if not TG_TOKEN:
        print("❌ Немає токена Telegram")
        return

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    
    # Текст повідомлення
    message_text = (
        "<b>🚀 Оновлення InvestPro!</b>\n\n"
        "Ми додали можливість вводити <b>будь-який банк</b> вручну!\n\n"
        "✅ Більше ніяких обмежень списком.\n"
        "✅ Працює для кредитів, купівлі та продажу облігацій.\n"
        "✅ Якщо банку немає в списку — просто введіть назву.\n\n"
        "Натисніть кнопку нижче, щоб спробувати 👇"
    )

    # Параметри з кнопкою
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {
                    "text": "📱 Відкрити оновлений InvestPro",
                    "web_app": {"url": WEB_APP_URL}
                }
            ]]
        }
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"✅ Надіслано: {chat_id}")
        else:
            print(f"⚠️ Помилка {chat_id}: {response.text}")
        time.sleep(0.05) # Пауза, щоб не спамити API
    except Exception as e:
        print(f"❌ Помилка з'єднання: {e}")

def run_broadcast():
    print("📢 Починаємо розсилку оновлення...")
    
    # 1. Отримуємо прямих користувачів (документи tg_ID)
    users_ref = db.collection('users').stream()
    
    # Використовуємо set, щоб уникнути дублікатів
    target_users = set()

    for user in users_ref:
        user_id = user.id
        if user_id.startswith('tg_'):
            clean_id = user_id.replace('tg_', '')
            target_users.add(clean_id)

    # 2. Відправляємо повідомлення
    count = 0
    total = len(target_users)
    print(f"Знайдено {total} користувачів.")

    for chat_id in target_users:
        send_update_message(chat_id)
        count += 1
            
    print(f"🏁 Розсилку завершено! Відправлено: {count} з {total}")

if __name__ == "__main__":
    run_broadcast()
