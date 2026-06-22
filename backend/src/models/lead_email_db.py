"""
Database model for lead email storage.

SQLAlchemy ORM model for storing email captures with soft-delete support.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid

from src.models.ephemeris_storage import Base


class LeadEmailDB(Base):
    """
    Lead email database table.

    Stores captured emails with metadata and soft-delete support.
    """

    __tablename__ = "lead_emails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")
    source = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True, index=True)
    notes = Column(Text, nullable=True)
    consent_given = Column(Boolean, nullable=False, default=False)
    consent_date = Column(DateTime, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    def __repr__(self):
        return f"<LeadEmailDB(id='{self.id}', email='{self.email}', status='{self.status}')>"
