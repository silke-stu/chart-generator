"""
Integration tests for email capture functionality.

Tests email service, handler, and database integration.
"""

import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, DateTime, Boolean, Text, Column
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from src.services.email_service import EmailService
from src.handlers.email_handler import EmailHandler, EmailCaptureError


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite:///:memory:"

# Create test-specific base and model for SQLite compatibility
TestBase = declarative_base()


class LeadEmailDB(TestBase):
    """Test version of LeadEmailDB using String for UUID (SQLite compatible)."""

    __tablename__ = "lead_emails"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")
    source = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, index=True)
    notes = Column(Text, nullable=True)
    consent_given = Column(Boolean, nullable=False, default=False)
    consent_date = Column(DateTime, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)


# Monkey patch the model for tests
import src.models.lead_email_db
src.models.lead_email_db.LeadEmailDB = LeadEmailDB
src.models.lead_email_db.Base = TestBase


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine(TEST_DATABASE_URL)
    TestBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def email_service():
    """Create email service instance."""
    return EmailService()


@pytest.fixture
def email_handler():
    """Create email handler instance."""
    return EmailHandler(model_cls=LeadEmailDB)


class TestEmailService:
    """Test email service database operations."""

    def test_save_email_success(self, email_service, db_session):
        """Test saving a new email."""
        result = email_service.save_email(
            email="test@example.com",
            db_session=db_session
        )

        assert result["email"] == "test@example.com"
        assert "id" in result
        assert "created_at" in result

    def test_save_email_normalizes_case(self, email_service, db_session):
        """Test that emails are stored in lowercase."""
        result = email_service.save_email(
            email="Test@Example.COM",
            db_session=db_session
        )

        assert result["email"] == "test@example.com"

    def test_save_email_with_metadata(self, email_service, db_session):
        """Test saving email with IP and user agent."""
        result = email_service.save_email(
            email="test@example.com",
            db_session=db_session,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )

        # Verify in database
        record = db_session.query(LeadEmailDB).filter_by(
            id=result["id"]
        ).first()

        assert record.ip_address == "192.168.1.1"
        assert record.user_agent == "Mozilla/5.0"
        assert record.consent_given is True

    def test_check_duplicate_not_exists(self, email_service, db_session):
        """Test duplicate check returns False for new email."""
        is_duplicate = email_service.check_duplicate(
            email="new@example.com",
            db_session=db_session
        )

        assert is_duplicate is False

    def test_check_duplicate_exists(self, email_service, db_session):
        """Test duplicate check returns True for existing email."""
        # Save email first
        email_service.save_email(
            email="existing@example.com",
            db_session=db_session
        )

        # Check duplicate
        is_duplicate = email_service.check_duplicate(
            email="existing@example.com",
            db_session=db_session
        )

        assert is_duplicate is True

    def test_check_duplicate_case_insensitive(self, email_service, db_session):
        """Test duplicate check is case-insensitive."""
        # Save lowercase
        email_service.save_email(
            email="test@example.com",
            db_session=db_session
        )

        # Check with different case
        is_duplicate = email_service.check_duplicate(
            email="Test@Example.COM",
            db_session=db_session
        )

        assert is_duplicate is True

    def test_check_duplicate_excludes_soft_deleted(self, email_service, db_session):
        """Test that soft-deleted records are not considered duplicates."""
        # Save and soft delete
        result = email_service.save_email(
            email="deleted@example.com",
            db_session=db_session
        )

        record = db_session.query(LeadEmailDB).filter_by(
            id=result["id"]
        ).first()
        record.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        # Check duplicate should return False
        is_duplicate = email_service.check_duplicate(
            email="deleted@example.com",
            db_session=db_session
        )

        assert is_duplicate is False

    def test_soft_delete_email(self, email_service, db_session):
        """Test soft deleting an email."""
        # Save email
        email_service.save_email(
            email="todelete@example.com",
            db_session=db_session
        )

        # Soft delete
        deleted = email_service.soft_delete_email(
            email="todelete@example.com",
            db_session=db_session
        )

        assert deleted is True

        # Verify it's soft deleted
        record = db_session.query(LeadEmailDB).filter(
            LeadEmailDB.email == "todelete@example.com"
        ).first()

        assert record.deleted_at is not None


class TestEmailHandler:
    """Test email handler business logic."""

    def test_capture_email_success(self, email_handler, db_session):
        """Test successful email capture."""
        result = email_handler.capture_email(
            email="valid@example.com",
            db_session=db_session
        )

        assert result["success"] is True
        assert "id" in result
        assert "message" in result

    def test_capture_email_invalid_format(self, email_handler, db_session):
        """Test capture with invalid email format."""
        with pytest.raises(EmailCaptureError) as exc_info:
            email_handler.capture_email(
                email="invalid-email",
                db_session=db_session
            )

        assert exc_info.value.status_code == 400

    def test_capture_email_duplicate(self, email_handler, db_session):
        """Test capture with duplicate email."""
        # First capture
        email_handler.capture_email(
            email="duplicate@example.com",
            db_session=db_session
        )

        # Second capture should raise error
        with pytest.raises(EmailCaptureError) as exc_info:
            email_handler.capture_email(
                email="duplicate@example.com",
                db_session=db_session
            )

        assert exc_info.value.status_code == 409
        assert "bereits registriert" in exc_info.value.message

    def test_capture_email_with_metadata(self, email_handler, db_session):
        """Test capture with IP and user agent."""
        result = email_handler.capture_email(
            email="metadata@example.com",
            db_session=db_session,
            ip_address="10.0.0.1",
            user_agent="Test Agent"
        )

        # Verify in database
        record = db_session.query(LeadEmailDB).filter_by(
            id=result["id"]
        ).first()

        assert record.ip_address == "10.0.0.1"
        assert record.user_agent == "Test Agent"


class TestDatabaseModel:
    """Test database model functionality."""

    def test_lead_email_creation(self, db_session):
        """Test creating a LeadEmailDB record."""
        lead = LeadEmailDB(
            email="model@example.com",
            status="pending",
            source="test"
        )

        db_session.add(lead)
        db_session.commit()

        assert lead.id is not None
        assert lead.created_at is not None
        assert lead.updated_at is not None
        assert lead.deleted_at is None

    def test_lead_email_defaults(self, db_session):
        """Test default values for LeadEmailDB."""
        lead = LeadEmailDB(email="defaults@example.com")

        db_session.add(lead)
        db_session.commit()

        assert lead.status == "pending"
        assert lead.consent_given is False
        assert lead.source is None
