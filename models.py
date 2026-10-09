"""Database models used by the Product API."""

from datetime import datetime, timezone
from decimal import Decimal

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column


# The SQLAlchemy object is created without an application so the app factory
# can attach it later. This also allows tests to use a different database.
db = SQLAlchemy()


class Product(db.Model):
    """A product that can be stored, sold, and tracked in inventory."""

    # SQLAlchemy infers the table name "product" from the class name. The
    # integer primary key is generated automatically when a row is inserted.
    id: Mapped[int] = mapped_column(primary_key=True)

    # name and price are the only product fields required from API clients.
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # Text is used because a description may be longer than a typical VARCHAR.
    description: Mapped[str | None] = mapped_column(Text)

    # Numeric stores an exact decimal monetary value with up to two decimal
    # places. This avoids rounding problems associated with floating-point data.
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # New products default to zero units when stock is omitted.
    stock: Mapped[int] = mapped_column(default=0, nullable=False)

    # SKU is optional but must be unique when provided, making it suitable as an
    # external inventory identifier.
    sku: Mapped[str | None] = mapped_column(String(64), unique=True)

    # Store timestamps in UTC. Using callables instead of evaluated datetime
    # values ensures every row receives the time at which it is actually saved.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self):
        """Convert the model into values that Flask can serialize as JSON."""

        # Decimal and datetime are converted explicitly because plain JSON does
        # not have native representations for these Python types.
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": float(self.price),
            "stock": self.stock,
            "sku": self.sku,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
