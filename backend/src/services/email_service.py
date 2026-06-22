"""
Email service for database operations.

Handles saving and checking email addresses in the database.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.lead_email_db import LeadEmailDB


class EmailService:
    """Service for email database operations."""

    @staticmethod
    def check_duplicate(email: str, db_session: Session) -> bool:
        """
        Check if email already exists in database.

        Args:
            email: Email address to check (case-insensitive)
            db_session: SQLAlchemy database session

        Returns:
            bool: True if email exists (excluding soft-deleted), False otherwise
        """
        # Case-insensitive check, excluding soft-deleted records
        existing = db_session.query(LeadEmailDB).filter(
            func.lower(LeadEmailDB.email) == func.lower(email),
            LeadEmailDB.deleted_at.is_(None)
        ).first()

        return existing is not None

    @staticmethod
    def save_email(
        email: str,
        db_session: Session,
        source: Optional[str] = "business_reading_interest",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> dict:
        """
        Save email to database with timestamp.

        Args:
            email: Email address to save
            db_session: SQLAlchemy database session
            source: Source of the email capture
            ip_address: Client IP address (optional)
            user_agent: Client user agent (optional)

        Returns:
            dict: Dictionary with id, email, and created_at

        Raises:
            Exception: If database operation fails
        """
        # Create new lead email record
        lead_email = LeadEmailDB(
            email=email.lower(),  # Store normalized lowercase
            status="pending",
            source=source,
            consent_given=True,  # Implicit consent by submitting
            consent_date=datetime.now(timezone.utc),
            ip_address=ip_address,
            user_agent=user_agent
        )

        db_session.add(lead_email)
        db_session.commit()
        db_session.refresh(lead_email)

        return {
            "id": lead_email.id,
            "email": lead_email.email,
            "created_at": lead_email.created_at
        }

    @staticmethod
    def get_email_by_id(email_id: str, db_session: Session) -> Optional[LeadEmailDB]:
        """
        Retrieve email record by ID.

        Args:
            email_id: UUID of the email record
            db_session: SQLAlchemy database session

        Returns:
            LeadEmailDB or None if not found
        """
        return db_session.query(LeadEmailDB).filter(
            LeadEmailDB.id == email_id
        ).first()

    @staticmethod
    def soft_delete_email(email: str, db_session: Session) -> bool:
        """
        Soft delete an email record.

        Args:
            email: Email address to soft delete
            db_session: SQLAlchemy database session

        Returns:
            bool: True if deleted, False if not found
        """
        record = db_session.query(LeadEmailDB).filter(
            func.lower(LeadEmailDB.email) == func.lower(email),
            LeadEmailDB.deleted_at.is_(None)
        ).first()

        if record:
            record.deleted_at = datetime.now()  # type: ignore
            db_session.commit()
            return True

        return False
