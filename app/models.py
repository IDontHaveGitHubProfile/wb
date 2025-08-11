from sqlalchemy import Column, Integer, BigInteger, Text, Float
from app.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    nm_id = Column(BigInteger, unique=True, index=True, nullable=False)

    name = Column(Text, nullable=False)
    price = Column(Integer, nullable=False)                
    rating = Column(Float, nullable=False, default=0.0)
    review_count = Column(Integer, nullable=False, default=0)
    stock = Column(Integer, nullable=False, default=0)
