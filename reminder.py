import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
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

def send_telegram(chat_id, message):
    if not TG_TOKEN:
        print("❌ Немає токена Telegram")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"⚠️ Telegram помилка {chat_id}: {response.text}")
        else:
            print(f"✅ Надіслано: {chat_id}")
        time.sleep(0.3) 
    except Exception as e:
        print(f"❌ Помилка з'єднання: {e}")

def check_credits():
    print("🚀 Початок ГЛОБАЛЬНОЇ перевірки...")
    today = datetime.now().date()
    
    # Словник, щоб збирати кредити: { 'tg_ID': [список_нагадувань] }
    notifications = {}
    
    # Список оброблених ID, щоб не дублювати
    processed_tg_ids = set()

    # --- ЕТАП 1: Шукаємо зв'язані акаунти (через users stream) ---
    print("🔎 Етап 1: Пошук зв'язаних акаунтів...")
    try:
        users_stream = db.collection('users').stream()
        for user_doc in users_stream:
            tg_id = user_doc.id
            if not tg_id.startswith('tg_'): continue
            
            data = user_doc.to_dict()
            if 'linkedAccountId' in data and data['linkedAccountId']:
                linked_id = data['linkedAccountId']
                print(f"   🔗 Знайдено лінк: {tg_id} -> {linked_id}")
                
                # Беремо кредити з Google-акаунту
                credits = db.collection('users').document(linked_id).collection('credits').stream()
                process_credits(tg_id, credits, notifications, today)
                processed_tg_ids.add(tg_id)
    except Exception as e:
        print(f"❌ Помилка Етапу 1: {e}")

    # --- ЕТАП 2: "Мисливець за привидами" (Collection Group) ---
    # Цей метод знаходить ВСІ кредити в базі, навіть якщо юзера "не існує" офіційно
    print("👻 Етап 2: Пошук невидимих користувачів...")
    try:
        # Шукаємо по всій базі колекції з назвою 'credits'
        all_credits = db.collection_group('credits').stream()
        
        for cred in all_credits:
            # Магія: дізнаємось, кому належить цей кредит
            # cred.reference.parent = collection 'credits'
            # cred.reference.parent.parent = document 'users/tg_XXXX'
            owner_doc = cred.reference.parent.parent
            
            if not owner_doc: continue
            owner_id = owner_doc.id

            # Нас цікавлять тільки папки, що починаються на 'tg_'
            # І які ми ще НЕ обробили в Етапі 1 (щоб не дублювати Google-акаунти)
            if owner_id.startswith('tg_') and owner_id not in processed_tg_ids:
                # Це і є наш "невидимий" користувач!
                # Обробляємо цей конкретний кредит
                process_single_credit(owner_id, cred, notifications, today)

    except Exception as e:
        print(f"❌ Помилка Етапу 2: {e}")

    # --- ЕТАП 3: Відправка ---
    print(f"📨 Готово до відправки: {len(notifications)} юзерів")
    for chat_id, alerts in notifications.items():
        if alerts:
            # Видаляємо дублікати повідомлень
            unique_alerts = list(set(alerts))
            chat_pure_id = chat_id.replace('tg_', '')
            full_text = "🔔 <b>Кредитні нагадування:</b>\n\n" + "\n\n".join(unique_alerts)
            send_telegram(chat_pure_id, full_text)

def process_credits(tg_id, credits_stream, notif_dict, today):
    """Обробляє потік (stream) кредитів"""
    for cred in credits_stream:
        process_single_credit(tg_id, cred, notif_dict, today)

def process_single_credit(tg_id, cred, notif_dict, today):
    """Перевіряє один кредит і додає в словник, якщо треба"""
    data = cred.to_dict()
    bank = data.get('bank', 'Банк')
    amount = data.get('amount', 0)
    deadline_str = data.get('deadline')

    if not deadline_str: return

    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        days_left = (deadline - today).days
        
        formatted_amount = "{:,.0f}".format(float(amount)).replace(',', ' ')
        msg = None

        if days_left < 0: msg = f"🔴 <b>ПРОСТРОЧЕНО!</b>\n{bank}: {formatted_amount} грн (було {deadline_str})"
        elif days_left == 0: msg = f"🚨 <b>СЬОГОДНІ!</b>\n{bank}: {formatted_amount} грн — треба гасити!"
        elif days_left == 1: msg = f"⚠️ <b>{bank}</b>: {formatted_amount} грн — завтра дедлайн!"
        elif days_left == 3: msg = f"⏳ <b>{bank}</b>: {formatted_amount} грн — залишилось 3 дні"
        elif days_left == 5: msg = f"📅 <b>{bank}</b>: {formatted_amount} грн — через 5 днів"

        if msg:
            if tg_id not in notif_dict: notif_dict[tg_id] = []
            notif_dict[tg_id].append(msg)
            print(f"   🔔 Знайдено для {tg_id}: {bank} ({days_left} дн)")
            
    except ValueError:
        pass

if __name__ == "__main__":
    check_credits()
