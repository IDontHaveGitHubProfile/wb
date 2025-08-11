import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def export_cookies_and_ua(debugger="127.0.0.1:9222", out="cookies.json", ua_out="ua.txt"):
    opts = Options()
    opts.debugger_address = debugger  # подключаемся к уже запущенному Chrome
    driver = webdriver.Chrome(options=opts)
    try:
        driver.get("https://www.wildberries.ru")
        # 1) Все cookies (в т.ч. HttpOnly)
        cookies = driver.execute_cdp_cmd("Network.getAllCookies", {})["cookies"]
        with open(out, "w", encoding="utf-8") as f:
            json.dump([
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".wildberries.ru"),
                    "path": c.get("path", "/"),
                    "secure": c.get("secure", False),
                    "httpOnly": c.get("httpOnly", False),
                } for c in cookies
            ], f, ensure_ascii=False, indent=2)

        # 2) Точный User-Agent
        ua = driver.execute_script("return navigator.userAgent")
        with open(ua_out, "w", encoding="utf-8") as f:
            f.write(ua)

        print(f"Saved {len(cookies)} cookies to {out} and UA to {ua_out}")
    finally:
        driver.quit()

if __name__ == "__main__":
    export_cookies_and_ua()
