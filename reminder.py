import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import requests
import time

# --- НАЛАШТУВАННЯ ---

# Ініціалізація Firebase (використовуємо ті ж змінні, що і main.py)
if not firebase_admin._apps:
    cred_dict = {
        "type": "service_account",
        "project_id": "bonds-2fe74",
        "private_key_id": os.environ.get("FIREBASE_PRIVATE_KEY_ID"),
        "private_key": os.environ.get("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),
        "client_email": os.environ.get("FIREBASE_CLIENT_EMAIL"),
        "client_id": os.environ.get("FIREBASE_CLIENT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": os.environ.get("FIREBASE_CLIENT_CERT_URL")
    }
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()
TG_TOKEN = os.environ.get("TG_BOT_TOKEN")

def send_telegram(chat_id, message):
    """Відправка повідомлення"""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        # Якщо бот заблокований юзером, API поверне 403, обробляємо щоб не впав скрипт
        if response.status_code != 200:
            print(f"Failed to send to {chat_id}: {response.text}")
        time.sleep(0.5) 
    except Exception as e:
        print(f"Error sending to {chat_id}: {e}")

def check_credits():
    print("🚀 Початок перевірки кредитів...")
    today = datetime.now().date()
    
    # 1. Беремо всіх юзерів
    users_ref = db.collection('users')
    all_users = users_ref.stream()

    for user_doc in all_users:
        user_id = user_doc.id
        
        # Працюємо тільки з тими, хто має 'tg_' у назві (або прив'язаний до них)
        if not user_id.startswith('tg_'):
            continue

        # Отримуємо чистий Chat ID (видаляємо 'tg_')
        chat_id = user_id.replace('tg_', '')
        
        # Логіка синхронізації (якщо дані лежать в іншому акаунті)
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
                # Конвертуємо рядок "2025-12-08" у дату
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
                days_left = (deadline - today).days
                
                # Форматування суми (10000 -> 10 000)
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

        # 3. Відправляємо, якщо є про що
        if alerts:
            full_text = "🔔 <b>Кредитні нагадування:</b>\n\n" + "\n\n".join(alerts)
            send_telegram(chat_id, full_text)
            print(f"✅ Надіслано для {chat_id}")

if __name__ == "__main__":
    check_credits()
