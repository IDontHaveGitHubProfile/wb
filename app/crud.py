from sqlalchemy.orm import Session
from app.models import Product

def upsert_products(db: Session, items: list[dict]) -> int:
    """
    Вставка/обновление только нужных полей.
    Ключ — nm_id.
    """
    n = 0
    for p in items:
        nm_id = p.get("nm_id")
        if nm_id is None:
            continue

        row = db.query(Product).filter(Product.nm_id == nm_id).one_or_none()
        if row:
            row.name = p.get("name", row.name)
            row.price = int(p.get("price") or 0)
            row.rating = float(p.get("rating") or 0.0)
            row.review_count = int(p.get("review_count") or 0)
            row.stock = int(p.get("stock") or 0)
        else:
            db.add(Product(
                nm_id=nm_id,
                name=p.get("name", ""),
                price=int(p.get("price") or 0),
                rating=float(p.get("rating") or 0.0),
                review_count=int(p.get("review_count") or 0),
                stock=int(p.get("stock") or 0),
            ))
        n += 1

    db.commit()
    return n
