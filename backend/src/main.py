"""FastAPI main application"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
import html
import asyncio
import re
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.models.chart import ChartRequest, ChartResponse
from src.models.email import EmailCaptureRequest, EmailCaptureResponse
from src.services.validation_service import ValidationService, ValidationError
from src.services.hd_api_client import HDAPIClient
from src.services.normalization_service import NormalizationService
from src.api.routes.chart import router as chart_router
from src.handlers.email_handler import EmailHandler, EmailCaptureError
from src.database import get_db_session
from datetime import datetime
import pytz
from src.services.geocoding_service import GeocodingService
from src.services.calculation.bodygraph_calculator import BodygraphCalculator
from src.services.ephemeris.source_factory import get_ephemeris_source
from src.services.calculation.position_calculator import PositionCalculator
from src.services.calculation.design_time import calculate_design_datetime

# Load environment variables
load_dotenv()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app
app = FastAPI(
    title="Human Design Chart Generator API",
    description="Backend API for generating Human Design charts",
    version="1.0.0",
)

# Add rate limiter to app state
app.state.limiter = limiter

# Add HTTPS enforcement middleware in production
environment = os.getenv("ENVIRONMENT", "development")
if environment == "production":
    from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
    app.add_middleware(HTTPSRedirectMiddleware)

# Configure CORS with hardened settings
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
cors_origins = [frontend_url]
# Allow localhost only in development
if environment != "production":
    cors_origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,  # 1 hour cache for preflight
)

# Initialize services
validation_service = ValidationService()
hd_client = HDAPIClient()
normalization_service = NormalizationService()
email_handler = EmailHandler()
geocoding_service = GeocodingService()
bodygraph_calculator = BodygraphCalculator()

# Include routers
app.include_router(chart_router)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "hd-chart-generator"}


@app.post("/api/hd-chart", response_model=ChartResponse)
@limiter.limit("10/minute")  # 10 requests per minute for expensive calculation
async def generate_chart(request: Request, chart_request: ChartRequest):
    """
    Generate Human Design chart from birth data

    Args:
        chart_request: ChartRequest with birth information

    Returns:
        ChartResponse with complete HD chart data

    Raises:
        HTTPException: 400 for validation errors, 500 for API errors
    """
    try:
        # Sanitize input to prevent XSS with strict validation
        name = chart_request.firstName.strip()

        # Only allow German characters, spaces, hyphens, and apostrophes
        if not re.match(r'^[a-zA-ZäöüßÄÖÜ\s\-\.\']+$', name):
            raise ValidationError(
                "firstName",
                "Name darf nur Buchstaben, Leerzeichen, Bindestriche und Apostrophe enthalten."
            )

        # Additional length check
        if len(name) < 2 or len(name) > 100:
            raise ValidationError(
                "firstName",
                "Name muss zwischen 2 und 100 Zeichen lang sein."
            )

        # HTML escape for safe output rendering
        sanitized_name = html.escape(name)

        # Validate input
        is_valid, error_msg = validation_service.validate_name(sanitized_name)
        if not is_valid:
            raise ValidationError("firstName", error_msg)

        is_valid, error_msg = validation_service.validate_birth_date(chart_request.birthDate)
        if not is_valid:
            raise ValidationError("birthDate", error_msg)

        # Handle approximate time
        if chart_request.birthTimeApproximate and not chart_request.birthTime:
            chart_request.birthTime = "12:00"

        birth_time: str = chart_request.birthTime or "12:00"
        is_valid, error_msg = validation_service.validate_birth_time(birth_time)
        if not is_valid:
            raise ValidationError("birthTime", error_msg)

        # 1. Resolve coordinates and timezone
        if chart_request.latitude is not None and chart_request.longitude is not None:
            lat = chart_request.latitude
            lng = chart_request.longitude
            tz_str = geocoding_service.get_timezone_from_coords(lat, lng)
            if not tz_str:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "field": "birthPlace",
                        "error": "Zeitzone für den angegebenen Ort nicht gefunden.",
                    },
                )
        else:
            lat, lng, tz_str = geocoding_service.get_location_data(chart_request.birthPlace)
            if not lat or not lng or not tz_str:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "field": "birthPlace",
                        "error": "Ort nicht gefunden. Bitte prüfen Sie die Eingabe.",
                    },
                )

        # 2. Parse datetime
        try:
            birth_dt_str = f"{chart_request.birthDate} {birth_time}"
            birth_dt = datetime.strptime(birth_dt_str, "%d.%m.%Y %H:%M")
        except ValueError:
            raise ValidationError("birthDate", "Ungültiges Datumsformat")

        # 3. Localize to timezone
        try:
            tz = pytz.timezone(tz_str)
            birth_dt_local = tz.localize(birth_dt)
            birth_dt_utc = birth_dt_local.astimezone(pytz.UTC)
        except Exception as e:
            print(f"Timezone error: {e}")
            raise HTTPException(
                status_code=400,
                detail={"field": "birthPlace", "error": "Fehler bei der Zeitzonenverarbeitung. Bitte prüfen Sie den Ort."},
            )

        # 4. Calculate positions with timeout protection (60s for cold starts)
        try:
            # Use asyncio.timeout for async-safe timeout handling
            # Works reliably in async contexts and on all platforms (Windows, Linux, macOS)
            timeout_seconds = 60  # Allows time for cold starts on Railway

            async def calculate_with_timeout():
                """Calculate chart with timeout protection"""
                ephemeris_source = get_ephemeris_source()
                pos_calculator = PositionCalculator(ephemeris_source)

                personality_positions = pos_calculator.calculate_positions(birth_dt_utc)

                design_dt_utc = calculate_design_datetime(
                    birth_dt_utc, ephemeris_source, target_arc=88.0
                )
                design_positions = pos_calculator.calculate_positions(design_dt_utc)

                # 5. Calculate Bodygraph
                chart_response = bodygraph_calculator.calculate_chart(
                    personality_positions,
                    design_positions,
                    sanitized_name,
                    calculation_source=ephemeris_source.get_source_name(),
                )
                return chart_response

            try:
                chart_response = await asyncio.wait_for(
                    calculate_with_timeout(),
                    timeout=timeout_seconds
                )
                return chart_response
            except asyncio.TimeoutError:
                raise TimeoutError(f"Calculation exceeded maximum time limit ({timeout_seconds} seconds)")

        except TimeoutError as e:
            print(f"Calculation timeout: {e}")
            raise HTTPException(
                status_code=504,
                detail={
                    "field": "calculation",
                    "error": "Die Berechnung hat zu lange gedauert. Bitte versuchen Sie es später noch einmal."
                },
            )
        except RuntimeError as e:
            # Handle swisseph subprocess or calculation errors
            error_msg = str(e).lower()
            if "timeout" in error_msg or "timed out" in error_msg:
                status = 504
                detail_msg = "Die Berechnung hat zu lange gedauert. Bitte versuchen Sie es später noch einmal."
            else:
                status = 503
                detail_msg = "Ephemeris-Berechnungsdienst nicht verfügbar. Bitte versuchen Sie es später noch einmal."
            print(f"Calculation runtime error: {e}")
            raise HTTPException(
                status_code=status,
                detail={
                    "field": "calculation",
                    "error": detail_msg
                },
            )
        except Exception as e:
            print(f"Calculation error: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "field": "calculation",
                    "error": "Fehler bei der Chart-Berechnung. Bitte versuchen Sie es später noch einmal."
                },
            )

    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail={"field": e.field, "error": e.message}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es später noch einmal."
            },
        )


@app.post("/api/email-capture", response_model=EmailCaptureResponse)
@limiter.limit("5/minute")  # 5 requests per minute for email capture
async def capture_email(request: Request, email_request: EmailCaptureRequest):
    """
    Capture email for Business Reading interest

    Args:
        email_request: EmailCaptureRequest with email

    Returns:
        EmailCaptureResponse with success status

    Raises:
        HTTPException: 400 for validation errors, 409 for duplicates, 500 for server errors
    """
    db_session = None
    try:
        # Get database session
        db_session = get_db_session()

        # Capture email using handler
        result = email_handler.capture_email(
            email=email_request.email,
            db_session=db_session,
            ip_address=None,
            user_agent=None,
        )

        return EmailCaptureResponse(
            success=result["success"], id=result["id"], message=result["message"]
        )

    except EmailCaptureError as e:
        raise HTTPException(
            status_code=e.status_code, detail={"field": "email", "error": e.message}
        )
    except Exception as e:
        # Log the error (in production, use proper logging)
        print(f"Unexpected error in email capture: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "field": "email",
                "error": "Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es später noch einmal."
            },
        )
    finally:
        if db_session:
            db_session.close()


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors"""
    return JSONResponse(
        status_code=429,
        content={
            "field": "request",
            "error": "Zu viele Anfragen. Bitte warten Sie eine Minute und versuchen Sie es erneut."
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unexpected errors"""
    return JSONResponse(
        status_code=500,
        content={
            "field": "server",
            "error": "Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es später noch einmal."
        },
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port, reload=True)
