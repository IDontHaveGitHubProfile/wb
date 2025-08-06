import sys
import os

from fastapi import FastAPI, Query
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import engine, SessionLocal, Base
from app.models import Product
from app.schemas import ProductSchema
from parser.wb_selenium import WBSeleniumParser

# Создание таблиц
Base.metadata.create_all(bind=engine)

# Приложение FastAPI
app = FastAPI()

@app.post("/parse")
def parse_products(query: str = Query(...), limit: int = Query(100)):
    parser = WBSeleniumParser(headless=True)
    products = parser.parse(query=query, max_products=limit)
    print(f"[DEBUG] Получено товаров от парсера: {len(products)}")

    db = SessionLocal()
    saved_count = 0
    try:
        for p in products:
            product = Product(
                name=p['name'],
                price=p['price'],
                rating=p['rating'],
                review_count=p['review_count'],
                in_stock=p['in_stock']
            )
            db.add(product)
            saved_count += 1
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Ошибка при сохранении: {e}")
    finally:
        db.close()

    return {"message": f"Сохранено товаров: {saved_count}"}

@app.get("/products", response_model=list[ProductSchema])
def get_products(search: str = Query(None)):
    db = SessionLocal()
    try:
        query = db.query(Product)
        if search:
            query = query.filter(Product.name.contains(search))
        products = query.all()
    finally:
        db.close()
    return products