"""FastAPI main application"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import csv
import io
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
from src.api.routes.pdf import router as pdf_router
from src.handlers.email_handler import EmailHandler, EmailCaptureError
from src.database import get_db_session, init_db
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

# Simple in-memory chart counter (resets on server restart/redeploy)
chart_count = 0

# Initialize FastAPI app
app = FastAPI(
    title="Human Design Chart Generator API",
    description="Backend API for generating Human Design charts",
    version="1.0.0",
)

# Add rate limiter to app state
app.state.limiter = limiter


# Middleware: count successful chart generations
@app.middleware("http")
async def count_chart_requests(request: Request, call_next):
    global chart_count
    response = await call_next(request)
    if (request.url.path == "/api/hd-chart"
            and request.method == "POST"
            and response.status_code == 200):
        chart_count += 1
    return response


# Initialize database tables on startup
@app.on_event("startup")
async def startup_event():
    init_db()

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
app.include_router(pdf_router)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "hd-chart-generator"}


@app.get("/api/debug-stefano")
async def debug_stefano():
    """Debug endpoint: computes raw Sun longitude for Stefano 21.10.1963 04:50 Grosseto"""
    try:
        import swisseph as swe
        tz = pytz.timezone("Europe/Rome")
        birth_local = tz.localize(datetime(1963, 10, 21, 4, 50))
        birth_utc = birth_local.astimezone(pytz.UTC)
        jd = swe.julday(birth_utc.year, birth_utc.month, birth_utc.day,
                        birth_utc.hour + birth_utc.minute / 60.0)
        res = swe.calc_ut(jd, swe.SUN)
        sun_lon = float(res[0][0])
        adj = (sun_lon + 58.0) % 360.0
        gn = int(adj / 5.625)
        pig = adj % 5.625
        ln = int(pig / 0.9375) + 1
        wheel = [41,19,13,49,30,55,37,63,22,36,25,17,21,51,42,3,
                 27,24,2,23,8,20,16,35,45,12,15,52,39,53,62,56,
                 31,33,7,4,29,59,40,64,47,6,46,18,48,57,32,50,
                 28,44,1,43,14,34,9,5,26,11,10,58,38,54,61,60]
        gate = wheel[gn] if 0 <= gn < 64 else -1
        return {
            "ok": True,
            "birth_utc": str(birth_utc),
            "jd": jd,
            "sun_lon": sun_lon,
            "gate": gate,
            "line": ln,
            "expected_sun": 207.028,
            "expected_gate": 50,
            "expected_line": 1,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "type": type(e).__name__}


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
            first_name=email_request.first_name,
            hd_type=email_request.hd_type,
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


@app.get("/api/admin/leads")
async def export_leads(token: str = ""):
    """
    Export all email leads as CSV.
    Protected by ADMIN_TOKEN env var.
    """
    admin_token = os.getenv("ADMIN_TOKEN", "")
    if not admin_token or token != admin_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    from src.models.lead_email_db import LeadEmailDB
    db_session = None
    try:
        db_session = get_db_session()
        leads = db_session.query(LeadEmailDB).filter(
            LeadEmailDB.deleted_at.is_(None)
        ).order_by(LeadEmailDB.created_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["email", "first_name", "hd_type", "status", "created_at"])
        for lead in leads:
            writer.writerow([
                lead.email,
                lead.first_name or "",
                lead.hd_type or "",
                lead.status,
                lead.created_at.strftime("%Y-%m-%d %H:%M") if lead.created_at else "",
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=leads.csv"},
        )
    finally:
        if db_session:
            db_session.close()


@app.get("/api/admin/stats")
async def get_stats(token: str = ""):
    """Chart generation counter. Protected by ADMIN_TOKEN."""
    admin_token = os.getenv("ADMIN_TOKEN", "")
    if not admin_token or token != admin_token:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {
        "charts_generated": chart_count,
        "note": "Zähler wird bei Server-Neustart / Redeploy zurückgesetzt",
    }


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
