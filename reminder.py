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
        print(f"❌ Помилка: Немає змінної FIREBASE_KEY. Поточні змінні: {list(os.environ.keys())}")
        # Для локального тестування можна розкоментувати:
        # cred = credentials.Certificate("key.json")
        # firebase_admin.initialize_app(cred)
        # exit(1) # Якщо key.json немає, скрипт зупиниться

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
    
    # Словник: { 'tg_ID': [список_повідомлень] }
    notifications = {}
    
    # Список оброблених ID, щоб не дублювати
    processed_tg_ids = set()

    # --- ЕТАП 1: Шукаємо зв'язані акаунти (Linked Accounts) ---
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
                
                # Беремо кредити з Google-акаунту, але шлемо на Telegram ID
                credits = db.collection('users').document(linked_id).collection('credits').stream()
                process_credits(tg_id, credits, notifications, today)
                processed_tg_ids.add(tg_id)
    except Exception as e:
        print(f"❌ Помилка Етапу 1: {e}")

    # --- ЕТАП 2: "Мисливець за привидами" (Collection Group) ---
    # Знаходить кредити, навіть якщо у користувача немає linkedAccountId або документ користувача порожній
    print("👻 Етап 2: Пошук прямих записів...")
    try:
        # Шукаємо по всій базі ВСІ колекції з назвою 'credits'
        all_credits = db.collection_group('credits').stream()
        
        for cred in all_credits:
            # cred.reference.parent.parent -> це документ User
            owner_doc = cred.reference.parent.parent
            
            if not owner_doc: continue
            owner_id = owner_doc.id

            # Якщо це Telegram-користувач і ми його ще не обробили в Етапі 1
            if owner_id.startswith('tg_') and owner_id not in processed_tg_ids:
                process_single_credit(owner_id, cred, notifications, today)

    except Exception as e:
        print(f"❌ Помилка Етапу 2: {e}")

    # --- ЕТАП 3: Відправка ---
    print(f"📨 Готово до відправки: {len(notifications)} юзерів")
    for chat_id, alerts in notifications.items():
        if alerts:
            # Видаляємо дублікати повідомлень (на випадок помилки логіки)
            unique_alerts = list(set(alerts))
            
            # Прибираємо префікс 'tg_' для API Telegram
            chat_pure_id = chat_id.replace('tg_', '')
            
            # Заголовок блоку
            full_text = "👋 <b>Привіт! Звіт InvestPro:</b>\n\n" + "\n\n".join(unique_alerts)
            send_telegram(chat_pure_id, full_text)

def process_credits(tg_id, credits_stream, notif_dict, today):
    """Обробляє потік (stream) кредитів"""
    for cred in credits_stream:
        process_single_credit(tg_id, cred, notif_dict, today)

def process_single_credit(tg_id, cred, notif_dict, today):
    """Перевіряє один кредит і додає повідомлення згідно стратегії 'Розумна тиша'"""
    data = cred.to_dict()
    bank = data.get('bank', 'Банк')
    amount = data.get('amount', 0)
    deadline_str = data.get('deadline')

    if not deadline_str: return

    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        days_left = (deadline - today).days
        
        # Форматування суми: 10 000 замість 10000.0
        formatted_amount = "{:,.0f}".format(float(amount)).replace(',', ' ')
        msg = None

        # --- СТРАТЕГІЯ: РОЗУМНА ТИША (5, 3, 1, 0) ---
        
        # 1. За 5 днів: Планування
        if days_left == 5:
            msg = (
                f"☕️ <b>Фінансовий планер: {bank}</b>\n"
                f"Через 5 днів закінчується пільговий період.\n"
                f"Сума до закриття: <b>{formatted_amount} грн</b>.\n"
                f"<i>Є час спланувати перекази без поспіху.</i>"
            )

        # 2. За 3 дні: Тактична дія (Золота середина)
        elif days_left == 3:
            msg = (
                f"🛡 <b>Захист прибутку: {bank}</b>\n"
                f"Залишилось 3 дні. Найкращий час для погашення.\n"
                f"Сума: <b>{formatted_amount} грн</b>.\n"
                f"<i>Закрий зараз, щоб зафіксувати чистий дохід.</i>"
            )

        # 3. За 1 день: Термінове нагадування
        elif days_left == 1:
            msg = (
                f"🚀 <b>Завтра дедлайн: {bank}</b>\n"
                f"Завтра останній день грейсу.\n"
                f"Треба підготувати: <b>{formatted_amount} грн</b>.\n"
                f"<i>Не дай банку заробити на тобі жодної копійки! 😉</i>"
            )

        # 4. Сьогодні: Алярм
        elif days_left == 0:
            msg = (
                f"🔥 <b>СЬОГОДНІ: Дедлайн по {bank}!</b>\n"
                f"Сума: <b>{formatted_amount} грн</b>.\n"
                f"⚠️ Бажано погасити до 19:00, щоб платіж пройшов вчасно."
            )

        # 5. Прострочено: Повідомляємо щодня, поки не видалять запис
        elif days_left < 0:
            msg = (
                f"🔴 <b>ПРОСТРОЧЕНО: {bank}</b>\n"
                f"Термін сплив {deadline_str}.\n"
                f"Борг: <b>{formatted_amount} грн</b>.\n"
                f"<i>Терміново закрий, нараховуються відсотки!</i>"
            )

        # Дні 4 та 2 пропускаються спеціально, щоб не спамити.

        if msg:
            if tg_id not in notif_dict: notif_dict[tg_id] = []
            notif_dict[tg_id].append(msg)
            print(f"    🔔 Знайдено для {tg_id}: {bank} ({days_left} дн)")
            
    except ValueError:
        pass

if __name__ == "__main__":
    check_credits()
