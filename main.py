import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import re
from datetime import datetime
import os
import json

# --- НАЛАШТУВАННЯ FIREBASE (УНІВЕРСАЛЬНЕ) ---
try:
    if not firebase_admin._apps:
        # 1. Спробуємо взяти ключ із змінних середовища (для GitHub)
        firebase_key_env = os.environ.get('FIREBASE_KEY')
        
        if firebase_key_env:
            # Якщо ми на GitHub -> розбираємо JSON з рядка
            cred_info = json.loads(firebase_key_env)
            cred = credentials.Certificate(cred_info)
        else:
            # 2. Якщо змінної немає -> шукаємо файл (для локального запуску)
            cred = credentials.Certificate("key.json")
            
        firebase_admin.initialize_app(cred)
    
    db = firestore.client()
    print("З'єднання з Firestore встановлено.")
except Exception as e:
    print(f"Помилка ініціалізації Firebase: {e}")
    exit(1)



# --- НАЛАШТУВАННЯ ПАРСЕРА ---
URL = "https://kinto.com/funds/shop/armybonds"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def clean_price(price_str):
    if not price_str:
        return 0.0
    clean = price_str.replace(' ', '').replace('грн.', '').replace(',', '.').strip()
    try:
        return float(clean)
    except ValueError:
        return 0.0

def scrape_and_update():
    print("Завантажую сторінку Кінто...")
    response = requests.get(URL, headers=HEADERS)
    response.encoding = 'utf-8'
    
    if response.status_code != 200:
        print(f"Помилка сайту: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    bond_titles = soup.find_all("div", class_="order-book-title")
    print(f"Знайдено облігацій: {len(bond_titles)}")
    
    count = 0
    batch = db.batch() # Використовуємо batch для пакетного запису (швидше і економніше)

    for title_div in bond_titles:
        try:
            # 1. Назва та Дата
            full_title = title_div.get_text(strip=True)
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', full_title)
            maturity_date = date_match.group(1) if date_match else "Unknown"
            bond_name = full_title.split('(')[0].strip().replace('“', '').replace('”', '').replace('"', '')

            # 2. ISIN та Дохідність
            moderator_div = title_div.find_next_sibling("div", class_="order-book-moderator")
            isin = "Unknown"
            yield_percent = 0.0
            
            if moderator_div:
                mod_text = moderator_div.get_text(strip=True)
                isin_match = re.search(r'(UA\w{10})', mod_text)
                isin = isin_match.group(1) if isin_match else "Unknown"
                
                yield_match = re.search(r'(\d+\.\d+)%', mod_text)
                if yield_match:
                    yield_percent = float(yield_match.group(1))

            # 3. Ціни
            table_div = title_div.find_next_sibling("div", class_="order-book-table")
            price_buy = 0.0
            price_sell = 0.0
            payout_amount = 0.0
            
            if table_div:
                headers = table_div.find_all("div", class_="order-book-table-header")
                for header in headers:
                    header_text = header.get_text(strip=True).lower()
                    price_div = header.find_next_sibling("div", class_="order-book-table-price")
                    
                    if price_div:
                        price_val = clean_price(price_div.get_text(strip=True))
                        if "купити" in header_text:
                            price_buy = price_val
                        elif "продати" in header_text:
                            price_sell = price_val
                        elif "виплати" in header_text:
                            payout_amount = price_val

            # Формуємо документ
            bond_data = {
                "name": bond_name,
                "maturity_date": maturity_date,
                "isin": isin,
                "yield_percent": yield_percent,
                "price_buy": price_buy,
                "price_sell": price_sell,
                "payout_amount": payout_amount,
                "updated_at": datetime.now().isoformat()
            }
            
            print(f"Готуємо: {bond_name} ({isin})")

            # Додаємо в пакет на відправку, якщо є ISIN
            if isin != "Unknown":
                # market_data - назва колекції
                # isin - назва документу (ID)
                doc_ref = db.collection('market_data').document(isin)
                batch.set(doc_ref, bond_data)
                count += 1
                
        except Exception as e:
            print(f"Помилка парсингу: {e}")
            continue

    # Відправляємо всі дані в Firestore одним запитом
    if count > 0:
        print("Записую дані в Firestore...")
        batch.commit()
        print(f"Успішно оновлено {count} документів у колекції 'market_data'.")
    else:
        print("Немає даних для запису.")

if __name__ == "__main__":
    scrape_and_update()