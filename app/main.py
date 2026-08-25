import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime

from core.database import connect_to_mongo, close_mongo_connection, get_database
from core.config import settings
from routers import subscription_router, preferences_router, feedback_router, jobs_router
from services.quote_service import QuoteService
from services.scheduler_service import DailyJobService


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    print("Success: Connected to MongoDB")

    # Initialize quote dataset from local JSON into MongoDB
    db = get_database()
    quote_service = QuoteService(db)
    await quote_service.ensure_minimum_quotes(minimum=50)
    print("Success: Quotes initialized from local dataset")

    yield

    # Shutdown
    await close_mongo_connection()
    print("Success: Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Daily Inspiration",
    description="A web application that sends personalized daily inspirational emails",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define absolute paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Include routers
app.include_router(subscription_router)
app.include_router(preferences_router)
app.include_router(feedback_router)
app.include_router(jobs_router)


# Home page
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# Features page
@app.get("/features", response_class=HTMLResponse)
async def features_page(request: Request):
    return templates.TemplateResponse("features.html", {"request": request})


# How It Works page
@app.get("/how-it-works", response_class=HTMLResponse)
async def how_it_works_page(request: Request):
    return templates.TemplateResponse("how_it_works.html", {"request": request})


# Sample Email page
@app.get("/sample-email", response_class=HTMLResponse)
async def sample_email_page(request: Request):
    return templates.TemplateResponse("sample_email.html", {"request": request})


# About page
@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


# Verification page
@app.get("/verify", response_class=HTMLResponse)
async def verify_page(request: Request, email: str = ""):
    return templates.TemplateResponse("verify.html", {
        "request": request,
        "email": email
    })


# Success page
@app.get("/success", response_class=HTMLResponse)
async def success_page(request: Request, email: str = ""):
    return templates.TemplateResponse("success.html", {
        "request": request,
        "email": email
    })


# My Account & Preferences Control Center
@app.get("/preferences", response_class=HTMLResponse)
@app.get("/feedback", response_class=HTMLResponse)
@app.get("/account", response_class=HTMLResponse)
async def preferences_page(request: Request, email: str = ""):
    is_verified = False
    is_unsubscribed = False
    user_status = "not_found"
    interests = []
    feedback_history = []

    if email:
        try:
            db = get_database()
            user = await db.users.find_one({"email": email.lower().strip()})
            if user:
                user_status = user.get("status", "pending")
                is_verified = user_status == "verified"
                is_unsubscribed = user_status == "unsubscribed"
                interests = user.get("interests", [])
                user_id = str(user.get("_id"))
                feedback_history = await db.feedback.find({
                    "$or": [{"user_email": email.lower().strip()}, {"user_id": user_id}]
                }).sort("created_at", -1).limit(10).to_list(length=10)
        except Exception:
            pass

    return templates.TemplateResponse("preferences.html", {
        "request": request,
        "email": email,
        "is_verified": is_verified,
        "is_unsubscribed": is_unsubscribed,
        "user_status": user_status,
        "interests": interests,
        "feedback_history": feedback_history,
        "user_email": email if is_verified else None
    })


# Unsubscribe page
@app.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_page(request: Request, email: str = ""):
    return templates.TemplateResponse("unsubscribed.html", {
        "request": request,
        "email": email
    })


# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


# API info
@app.get("/api")
async def api_info():
    return {
        "name": "Daily Inspiration API",
        "version": "2.0.0",
        "description": "API for Daily Inspiration application",
        "endpoints": {
            "subscription": {
                "request_otp": "POST /api/subscription/request-otp",
                "verify_otp": "POST /api/subscription/verify-otp",
                "google_auth": "POST /api/subscription/google-auth",
                "google_client_id": "GET /api/subscription/google-client-id",
                "status": "GET /api/subscription/status",
                "unsubscribe": "POST /api/subscription/unsubscribe"
            },
            "preferences": {
                "get": "GET /api/preferences",
                "update": "PUT /api/preferences"
            },
            "feedback": {
                "submit": "POST /api/feedback",
                "email_link": "GET /api/feedback",
                "history": "GET /api/feedback/history"
            },
            "jobs": {
                "send_daily_inspiration": "POST /api/jobs/send-daily-inspiration (Header: X-Cron-Secret)",
                "import_quotes": "POST /api/jobs/import-quotes (Header: X-Cron-Secret)"
            }
        }
    }


# Manual trigger for daily emails (for testing locally or in staging)
@app.post("/api/admin/send-daily")
async def trigger_daily_emails():
    """Manually trigger daily email sending (for testing purposes)."""
    db = get_database()
    job_service = DailyJobService(db)
    result = await job_service.execute_daily_inspiration_job()
    return {"message": "Daily emails job executed successfully", "result": result}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
