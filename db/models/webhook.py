from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, LargeBinary
from db.engine import Base


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    secret: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self.__class__, k):
                setattr(self, k, v)
