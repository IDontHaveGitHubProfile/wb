from pydantic import BaseModel
from typing import Optional

class ProductSchema(BaseModel):
    id: int
    name: str
    price: int
    rating: Optional[float] = None
    review_count: int
    in_stock: bool

    class Config:
        from_attributes = True
