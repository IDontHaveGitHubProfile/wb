import requests
from bs4 import BeautifulSoup
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_products():
    url = "https://www.wildberries.ru/catalog/0/search.aspx?search=термопаста"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.wildberries.ru/"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            logger.error(f"Ошибка запроса: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        
        # Новые селекторы для Wildberries (могут меняться)
        cards = soup.find_all("div", class_=re.compile(r"product-card__main"))
        
        products = []

        for card in cards:
            try:
                # Название товара
                name_tag = card.find("span", class_=re.compile(r"goods-name"))
                name = name_tag.get_text(strip=True) if name_tag else "Нет названия"
                
                # Цена
                price_tag = card.find("ins", class_=re.compile(r"price__lower-price")) or \
                          card.find("span", class_=re.compile(r"price__lower-price"))
                price_text = price_tag.get_text(strip=True) if price_tag else "0"
                price = int(re.sub(r"[^\d]", "", price_text)) if price_text else 0
                
                # Рейтинг
                rating_tag = card.find("span", class_=re.compile(r"address-rate-mini|product-card__rating"))
                rating = float(rating_tag.get("data-rate", "0")) if rating_tag else 0.0
                
                # Количество отзывов
                reviews_tag = card.find("span", class_=re.compile(r"product-card__count|review-count"))
                reviews_text = reviews_tag.get_text(strip=True) if reviews_tag else "0"
                reviews = int(re.sub(r"[^\d]", "", reviews_text)) if reviews_text else 0
                
                # Наличие
                stock_tag = card.find("span", class_=re.compile(r"product-card__tip"))
                stock = 0 if (stock_tag and "нет в наличии" in stock_tag.get_text().lower()) else 1

                products.append({
                    "name": name,
                    "price": price,
                    "rating": rating,
                    "review_count": reviews,
                    "stock": stock
                })
                
            except Exception as e:
                logger.warning(f"Ошибка при парсинге карточки: {e}")
                continue

        logger.info(f"Спарсено товаров: {len(products)}")
        return products

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка соединения: {e}")
        return []