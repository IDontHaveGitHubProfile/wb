from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app import models, schemas, database, crud
from parser.wb_api import WBApiParser

app = FastAPI(title="WB Parser API — минимальная версия")
models.Base.metadata.create_all(bind=database.engine)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/parse", summary="Спарсить и сохранить все товары по запросу 'термопаста'")
def parse_products(db: Session = Depends(get_db)):
    """
    Собирает ВСЕ страницы по запросу 'термопаста' и сохраняет в БД.
    """
    parser = WBApiParser()
    rows = parser.parse(query="термопаста", max_products=None, max_pages=None)

    prepared = []
    for p in rows:
        prepared.append({
            "nm_id": int(p.get("nm_id") or p.get("id")),
            "name": (p.get("name") or "").strip(),
            "price": int(p.get("price_final") or p.get("price_api") or 0),
            "rating": float(p.get("rating") or 0.0),
            "review_count": int(p.get("review_count") or 0),
            "stock": int(p.get("stock") or 0),
        })

    inserted = crud.upsert_products(db, prepared)
    return {"inserted_or_updated": inserted, "total_fetched": len(prepared), "query": "термопаста"}

@app.get("/products", response_model=list[schemas.ProductSchema], summary="Получить все сохранённые товары")
def get_products(db: Session = Depends(get_db)):
    """
    ВАЖНО: отдаёт весь массив целиком.
    Если записей 5k+, Swagger/браузер может подвисать — это ожидаемо.
    """
    return db.query(models.Product).order_by(models.Product.id.desc()).all()
