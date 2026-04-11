import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Text, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class InterestLevel(str, enum.Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Contact info for unauthenticated users who express interest in admission
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    agent_response: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunks: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON serialised

    admission_interest: Mapped[InterestLevel] = mapped_column(
        Enum(InterestLevel), default=InterestLevel.none, nullable=False
    )
    escalated_to_human: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="chat_logs")  # noqa: F821


class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vonage_call_uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    caller_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)  # Full call transcript
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)       # AI generated summary
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    admission_interest: Mapped[InterestLevel] = mapped_column(
        Enum(InterestLevel), default=InterestLevel.none, nullable=False
    )
    escalated_to_human: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    call_status: Mapped[str] = mapped_column(String(30), default="initiated", nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="call_logs")  # noqa: F821
