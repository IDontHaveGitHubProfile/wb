from sqlalchemy.orm import Session
from .models import Product

def save_products(db: Session, products: list):
    for p in products:
        product = Product(
            name=p["name"],
            price=p["price"],
            rating=p.get("rating", 0.0),
            review_count=p.get("review_count", 0),
            stock=p.get("stock", 0),
            link=p.get("link", ""),
            in_stock=p.get("in_stock", False)
        )
        db.add(product)
    db.commit()
