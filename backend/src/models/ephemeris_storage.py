"""
Database models for storing Swiss Ephemeris binary files.

Stores .se1 files in Postgres for deployment and runtime access.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, LargeBinary, DateTime, Integer
from sqlalchemy.orm import declarative_base

# Using declarative_base() for SQLAlchemy 1.4/2.0 compatibility
Base = declarative_base()  # type: ignore


class EphemerisFile(Base):  # type: ignore
    """
    Swiss Ephemeris binary file storage.

    Stores .se1 files as binary blobs for extraction to filesystem at runtime.
    """

    __tablename__ = "ephemeris_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), unique=True, nullable=False, index=True)
    file_data = Column(LargeBinary, nullable=False)
    file_size = Column(Integer, nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    source_url = Column(String(512), nullable=True)

    def __repr__(self):
        return f"<EphemerisFile(filename='{self.filename}', size={self.file_size})>"
