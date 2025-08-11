import json, sys
src = "cookies_raw.json"   # сюда положи экспорт EditThisCookie
dst = "cookies.json"       # это итоговый файл для проекта
data = json.load(open(src, "r", encoding="utf-8"))
out = []
for c in data:
    if "wildberries.ru" not in (c.get("domain") or ""):
        continue
    out.append({
        "name": c.get("name"),
        "value": c.get("value"),
        "domain": c.get("domain"),
        "path": c.get("path", "/"),
        "secure": bool(c.get("secure", False)),
        "httpOnly": bool(c.get("httpOnly", False)),
    })
json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Saved {len(out)} cookies to {dst}")
