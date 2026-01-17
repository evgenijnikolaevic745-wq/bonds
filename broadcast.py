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

# ПОСИЛАННЯ НА ДОДАТОК
WEB_APP_URL = "https://globalitevolutions.com.ua/index.html" 

def send_update_message(chat_id):
    if not TG_TOKEN: return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    
    # ВАШ НОВИЙ ТЕКСТ
    message_text = (
        "<b>💎 Нова функція у додатку InvestPro: облік комісій!</b>\n\n"
        "Купуєте облігації з комісією банку? Тепер InvestPro вміє це рахувати!\n\n"
        "<b>Як це працює:</b>\n"
        "При додаванні облігації вкажіть суму комісії — і додаток автоматично відніме її від вашого прибутку.\n\n"
        "✅ Бачите реальну дохідність.\n"
        "✅ Жодних прихованих витрат.\n"
        "✅ Ще точніша аналітика портфелю.\n\n"
        "Натисніть кнопку, щоб спробувати 👇"
    )

    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {
                    "text": "📊 Спробувати нову функцію",
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
    
    time.sleep(0.04) # Ліміт Телеграм (до 30 повідомлень в секунду)
    return False

def run_global_broadcast():
    print("📢 Починаємо ГЛОБАЛЬНУ розсилку всім користувачам...")
    
    all_users = set()

    # 1. Збираємо з папки users (офіційні)
    try:
        users_ref = db.collection('users').stream()
        for user in users_ref:
            if user.id.startswith('tg_'):
                all_users.add(user.id.replace('tg_', ''))
    except Exception as e:
        print(f"Помилка при скануванні users: {e}")

    # 2. Збираємо через Кредити (приховані)
    try:
        credits_ref = db.collection_group('credits').stream()
        for cred in credits_ref:
            owner = cred.reference.parent.parent
            if owner and owner.id.startswith('tg_'):
                all_users.add(owner.id.replace('tg_', ''))
    except Exception as e:
        print(f"Помилка при скануванні credits: {e}")

    # 3. Збираємо через Облігації (приховані)
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

    # ВІДПРАВКА
    sent_count = 0
    for chat_id in all_users:
        success = send_update_message(chat_id)
        if success:
            sent_count += 1
            
    print("-" * 30)
    print(f"🏁 Розсилку завершено! Успішно доставлено: {sent_count} з {total}")

if __name__ == "__main__":
    run_global_broadcast()
