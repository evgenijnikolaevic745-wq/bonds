import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import requests
import time

# --- НАЛАШТУВАННЯ ---

# Ініціалізація Firebase
if not firebase_admin._apps:
    # Отримуємо весь JSON-ключ як один рядок (надійно і без помилок формату)
    firebase_key_json = os.environ.get("FIREBASE_KEY")
    
    if firebase_key_json:
        try:
            # Перетворюємо рядок JSON у словник
            cred_dict = json.loads(firebase_key_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            print(f"❌ Помилка обробки FIREBASE_KEY: {e}")
            exit(1)
    else:
        print("❌ Помилка: Не знайдено змінну оточення FIREBASE_KEY")
        exit(1)

db = firestore.client()
TG_TOKEN = os.environ.get("TG_BOT_TOKEN")

def send_telegram(chat_id, message):
    """Відправка повідомлення"""
    if not TG_TOKEN:
        print("❌ Помилка: Немає TG_BOT_TOKEN")
        return

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Failed to send to {chat_id}: {response.text}")
        time.sleep(0.5) 
    except Exception as e:
        print(f"Error sending to {chat_id}: {e}")

def check_credits():
    print("🚀 Початок перевірки кредитів...")
    today = datetime.now().date()
    
    # 1. Беремо всіх юзерів
    try:
        users_ref = db.collection('users')
        all_users = users_ref.stream()
    except Exception as e:
        print(f"❌ Помилка доступу до БД: {e}")
        return

    for user_doc in all_users:
        user_id = user_doc.id
        
        # Працюємо тільки з тими, хто має 'tg_' у назві
        if not user_id.startswith('tg_'):
            continue

        chat_id = user_id.replace('tg_', '')
        
        # Логіка синхронізації
        user_data = user_doc.to_dict()
        target_db_id = user_id 
        
        if 'linkedAccountId' in user_data and user_data['linkedAccountId']:
            target_db_id = user_data['linkedAccountId']

        # 2. Ліземо в папку credits цього юзера
        credits_ref = db.collection('users').document(target_db_id).collection('credits')
        credits = credits_ref.stream()
        
        alerts = []

        for cred in credits:
            data = cred.to_dict()
            bank = data.get('bank', 'Банк')
            amount = data.get('amount', 0)
            deadline_str = data.get('deadline')

            if not deadline_str:
                continue

            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
                days_left = (deadline - today).days
                
                formatted_amount = "{:,.0f}".format(float(amount)).replace(',', ' ')

                # --- УМОВИ НАГАДУВАННЯ ---
                if days_left < 0:
                    alerts.append(f"🔴 <b>ПРОСТРОЧЕНО!</b>\n{bank}: {formatted_amount} грн (було {deadline_str})")
                elif days_left == 0:
                    alerts.append(f"🚨 <b>СЬОГОДНІ!</b>\n{bank}: {formatted_amount} грн — треба гасити!")
                elif days_left == 1:
                    alerts.append(f"⚠️ <b>{bank}</b>: {formatted_amount} грн — завтра дедлайн!")
                elif days_left == 3:
                    alerts.append(f"⏳ <b>{bank}</b>: {formatted_amount} грн — залишилось 3 дні")
                elif days_left == 5:
                    alerts.append(f"📅 <b>{bank}</b>: {formatted_amount} грн — через 5 днів")
                
            except ValueError:
                continue 

        # 3. Відправляємо
        if alerts:
            full_text = "🔔 <b>Кредитні нагадування:</b>\n\n" + "\n\n".join(alerts)
            send_telegram(chat_id, full_text)
            print(f"✅ Надіслано для {chat_id}")

if __name__ == "__main__":
    check_credits()
