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
        if response.status_code == 200:
            print(f"✅ Повідомлення надіслано юзеру {chat_id}")
        else:
            print(f"⚠️ Telegram помилка {chat_id}: {response.text}")
        time.sleep(0.5) 
    except Exception as e:
        print(f"❌ Помилка з'єднання: {e}")

def check_credits():
    print("🚀 Початок перевірки...")
    today = datetime.now().date()
    print(f"📅 Сьогоднішня дата: {today}")
    
    # Отримуємо всіх юзерів
    users_ref = db.collection('users')
    all_users = list(users_ref.stream()) # Конвертуємо в список, щоб порахувати
    
    print(f"🔎 Знайдено користувачів у базі: {len(all_users)}")

    if len(all_users) == 0:
        print("⚠️ УВАГА: Список користувачів порожній! Можливо, документи users/ID є віртуальними.")

    for user_doc in all_users:
        user_id = user_doc.id
        print(f"👤 Перевірка юзера: {user_id}")
        
        if not user_id.startswith('tg_'):
            print(f"   -> Пропускаємо (не починається на tg_)")
            continue

        chat_id = user_id.replace('tg_', '')
        
        user_data = user_doc.to_dict()
        
        # --- ВИПРАВЛЕННЯ: ПЕРЕВІРЯЄМО САМЕ ТЕЛЕГРАМ АКАУНТ ---
        # Ми примусово кажемо скрипту: "Дивись у tg_ID, навіть якщо є лінк"
        # target_db_id = user_id 
        
        # АБО (найкращий варіант): Перевіримо ОБИДВА місця
        paths_to_check = [user_id]
        if 'linkedAccountId' in user_data and user_data['linkedAccountId']:
             paths_to_check.append(user_data['linkedAccountId'])
             print(f"   -> Знайдено зв'язок з: {user_data['linkedAccountId']}")

        all_alerts = []

        for target_db_id in paths_to_check:
            print(f"   📂 Перевіряю папку: {target_db_id}")
            credits_ref = db.collection('users').document(target_db_id).collection('credits')
            credits = credits_ref.stream()

            for cred in credits:
                data = cred.to_dict()
                bank = data.get('bank', 'Банк')
                amount = data.get('amount', 0)
                deadline_str = data.get('deadline')

                if not deadline_str: continue

                try:
                    deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
                    days_left = (deadline - today).days
                    
                    print(f"      💳 {bank}: дедлайн {deadline_str} (через {days_left} дн)")
                    formatted_amount = "{:,.0f}".format(float(amount)).replace(',', ' ')

                    msg = None
                    if days_left < 0: msg = f"🔴 <b>ПРОСТРОЧЕНО!</b>\n{bank}: {formatted_amount} грн (було {deadline_str})"
                    elif days_left == 0: msg = f"🚨 <b>СЬОГОДНІ!</b>\n{bank}: {formatted_amount} грн — треба гасити!"
                    elif days_left == 1: msg = f"⚠️ <b>{bank}</b>: {formatted_amount} грн — завтра дедлайн!"
                    elif days_left == 3: msg = f"⏳ <b>{bank}</b>: {formatted_amount} грн — залишилось 3 дні"
                    elif days_left == 5: msg = f"📅 <b>{bank}</b>: {formatted_amount} грн — через 5 днів"
                    
                    if msg: all_alerts.append(msg)
                except ValueError: continue 

        if all_alerts:
            # Прибираємо дублікати повідомлень (set)
            unique_alerts = list(set(all_alerts))
            full_text = "🔔 <b>Кредитні нагадування:</b>\n\n" + "\n\n".join(unique_alerts)
            send_telegram(chat_id, full_text)
        else:
            print("   -> Немає нагадувань.")
            
        # Цей continue треба, щоб не йти далі по старому коду циклу
        continue

        credits_ref = db.collection('users').document(target_db_id).collection('credits')
        credits = credits_ref.stream()
        
        alerts = []
        credit_count = 0

        for cred in credits:
            credit_count += 1
            data = cred.to_dict()
            bank = data.get('bank', 'Банк')
            amount = data.get('amount', 0)
            deadline_str = data.get('deadline')

            if not deadline_str:
                continue

            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
                days_left = (deadline - today).days
                
                print(f"   💳 Кредит {bank}: дедлайн {deadline_str}, залишилось днів: {days_left}")

                formatted_amount = "{:,.0f}".format(float(amount)).replace(',', ' ')

                # Логіка
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
                print(f"   ❌ Помилка дати: {deadline_str}")
                continue 

        if credit_count == 0:
            print("   -> Кредитів не знайдено.")

        if alerts:
            full_text = "🔔 <b>Кредитні нагадування:</b>\n\n" + "\n\n".join(alerts)
            send_telegram(chat_id, full_text)
        else:
            print("   -> Немає повідомлень для відправки (дні не співпали).")

if __name__ == "__main__":
    check_credits()
