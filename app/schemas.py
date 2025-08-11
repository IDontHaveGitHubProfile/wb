from pydantic import BaseModel

class ProductSchema(BaseModel):
    id: int
    nm_id: int
    name: str
    price: int
    rating: float
    review_count: int
    stock: int

    class Config:
        from_attributes = True
