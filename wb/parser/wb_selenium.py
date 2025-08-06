import re
import time
import logging
from time import sleep
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class WBSeleniumParser:
    def __init__(self, headless=True, timeout=20):
        self.headless = headless
        self.timeout = timeout
        self.logger = self._setup_logger()
        self.driver = self._init_driver()
        self.wait = WebDriverWait(self.driver, self.timeout * 2 if self.headless else self.timeout)

    def _setup_logger(self):
        logger = logging.getLogger("WBSeleniumParser")
        if not logger.hasHandlers():
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def _init_driver(self):
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=ru-RU")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-webgl")
        options.add_argument("--disable-gcm")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        driver = webdriver.Chrome(options=options)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        return driver

    def _safe_int(self, text):
        try:
            return int(re.sub(r"[^\d]", "", text)) if text else 0
        except ValueError:
            return 0

    def _safe_float(self, text):
        try:
            return float(text.replace(",", ".").strip())
        except (ValueError, AttributeError):
            return 0.0

    def _get_text_safe(self, el, selector):
        try:
            return el.find_element(By.CSS_SELECTOR, selector).text.strip()
        except NoSuchElementException:
            return ""

    def _parse_card(self, card):
        try:
            brand = self._get_text_safe(card, ".product-card__brand")
            name = self._get_text_safe(card, ".product-card__name")
            full_name = f"{brand} {name}".strip()

            price_text = self._get_text_safe(card, ".price__lower-price") or \
                         self._get_text_safe(card, ".price-commission__current-price")
            old_price_text = self._get_text_safe(card, ".price__old-price del") or \
                             self._get_text_safe(card, ".price-commission__old-price")

            if price_text:
                price = self._safe_int(price_text)
                old_price = self._safe_int(old_price_text) if old_price_text else 0
            else:
                price = self._safe_int(old_price_text) if old_price_text else 0
                old_price = 0

            rating_element = card.find_elements(By.CSS_SELECTOR, ".address-rate-mini, .product-card__rating")
            rating = self._safe_float(rating_element[0].text) if rating_element else 0.0

            reviews_element = card.find_elements(By.CSS_SELECTOR, ".product-card__count, .product-card__review")
            reviews = self._safe_int(reviews_element[0].text) if reviews_element else 0

            in_stock = not bool(self._get_text_safe(card, ".product-card__not-available"))

            if not full_name or price == 0:
                self.logger.debug(f"Пропуск карточки: имя='{full_name}', цена={price}")
                return None

            return {
                "name": full_name,
                "price": price,
                "old_price": old_price,
                "discount": self._safe_int(self._get_text_safe(card, ".percentage-sale")),
                "rating": rating,
                "review_count": reviews,
                "in_stock": in_stock,
                "timestamp": int(time.time())
            }

        except Exception as e:
            self.logger.warning(f"Ошибка при парсинге карточки: {str(e)[:100]}...")
            return None

    def _scroll_to_load_all(self):
        SCROLL_PAUSE_TIME = 1.5
        last_count = 0
        attempts = 0
        max_attempts = 6

        while attempts < max_attempts:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            sleep(SCROLL_PAUSE_TIME)
            current_count = len(self.driver.find_elements(By.CSS_SELECTOR, "article.product-card"))

            if current_count == last_count:
                attempts += 1
            else:
                attempts = 0

            last_count = current_count

        self.logger.info(f"Прогрузка страницы завершена, товаров на странице: {last_count}")

    def _check_for_captcha(self):
        captcha_selectors = ["div.checkbox", "div.captcha-container", "div.captcha"]
        for selector in captcha_selectors:
            if len(self.driver.find_elements(By.CSS_SELECTOR, selector)) > 0:
                self.logger.error("Обнаружена капча. Парсинг остановлен.")
                return True
        return False

    def _get_total_from_search_page(self, query):
        url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={query}"
        try:
            self.driver.get(url)
            sleep(2)
            count_selectors = [".searching-results__count", ".goods-count", ".total-items"]
            for selector in count_selectors:
                try:
                    count_element = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    return self._safe_int(count_element.text)
                except:
                    continue
            self.logger.warning("Не удалось найти элемент с общим числом товаров")
            return None
        except Exception as e:
            self.logger.warning(f"Ошибка при получении общего числа товаров: {e}")
            return None

    def parse(self, query: str, max_products: int = None) -> list:
        products = []
        page = 1
        total = max_products or self._get_total_from_search_page(query)

        if not total:
            self.logger.error("Не удалось определить общее количество товаров. Парсинг остановлен.")
            return []

        while len(products) < total:
            url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={query}&page={page}"
            self.logger.info(f"Парсинг страницы {page}... URL: {url}")

            try:
                self.driver.get(url)
                if self._check_for_captcha():
                    return []

                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article.product-card")))
                except TimeoutException:
                    self.logger.warning(f"Товары не найдены на странице {page}. Пропускаем.")
                    page += 1
                    continue

                self._scroll_to_load_all()
                sleep(1)

                raw_cards = self.driver.find_elements(By.CSS_SELECTOR, "article.product-card")
                if not raw_cards:
                    self.logger.info("Карточки товаров не найдены — завершение.")
                    break

                parsed_count = 0
                for card in raw_cards:
                    if len(products) >= total:
                        break
                    product = self._parse_card(card)
                    if product:
                        products.append(product)
                        parsed_count += 1

                self.logger.info(f"На странице {page} найдено {len(raw_cards)} карточек, успешно распаршено {parsed_count}")

                cumulative_collected = len(products)
                self.logger.info(f"Собрано: {cumulative_collected} / {total}")

                page += 1
                sleep(1.5)

            except TimeoutException:
                self.logger.warning(f"Таймаут при загрузке страницы {page}. Прерывание.")
                break
            except Exception as e:
                self.logger.error(f"Неожиданная ошибка: {e}")
                break

        self.close()
        self.logger.info(f"Всего собрано товаров: {len(products)}")
        return products

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Драйвер закрыт")
            except:
                pass
