from sqlalchemy import Column, Integer, String, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Можно оставить String — в PostgreSQL он мапится на TEXT
    price = Column(Integer, nullable=False)
    rating = Column(Float)
    review_count = Column(Integer, default=0, nullable=False)
    in_stock = Column(Boolean, nullable=False)
