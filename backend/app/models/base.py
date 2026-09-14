# Shared ORM base: collects model metadata used by SQLAlchemy and Alembic migrations.
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
