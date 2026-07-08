from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(Base):
    __tablename__ = "roles"

    roleId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    roleName: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="role")
