"""Request/response models (pydantic v2)."""
from typing import Any

from pydantic import BaseModel, Field

PRODUCT_ID_PATTERN = r"^[A-Za-z0-9_-]+$"


class ReviewCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=64, pattern=PRODUCT_ID_PATTERN,
                            examples=["OLJCESPC7Z"])
    author: str = Field(min_length=1, max_length=100)
    rating: int = Field(ge=1, le=5, strict=True)
    title: str = Field(default="", max_length=200)
    body: str = Field(min_length=1, max_length=2000)


class ReviewEdit(BaseModel):
    """Full replacement of the editable fields."""
    rating: int = Field(ge=1, le=5, strict=True)
    title: str = Field(default="", max_length=200)
    body: str = Field(min_length=1, max_length=2000)


class CommandResult(BaseModel):
    review_id: str
    seq: int


class Review(BaseModel):
    review_id: str
    product_id: str
    author: str
    rating: int
    title: str
    body: str
    created_at: str
    updated_at: str


class RatingSummary(BaseModel):
    product_id: str
    count: int
    average: float


class EventOut(BaseModel):
    seq: int
    review_id: str
    type: str
    payload: dict[str, Any]
    created_at: str


class RebuildResult(BaseModel):
    events_replayed: int
    reviews: int


class Version(BaseModel):
    version: str


class Health(BaseModel):
    status: str
