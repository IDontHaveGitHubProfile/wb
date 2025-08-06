import json
from wb_selenium import WBSeleniumParser

if __name__ == "__main__":
    parser = WBSeleniumParser(headless=False)
    products = parser.parse_products("термопаста", max_products=100)

    with open("products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(f"Сохранено товаров: {len(products)}")
