import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # MongoDB
    mongodb_url: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    mongodb_db_name: str = os.getenv("MONGODB_DB_NAME", "daily_inspiration")
    
    # Email Service (SMTP Protocol)
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
    smtp_use_ssl: bool = os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes")
    email_from: str = os.getenv("EMAIL_FROM", "")
    email_from_name: str = os.getenv("EMAIL_FROM_NAME", "Daily Inspiration")
    
    # External APIs & OAuth
    pexels_api_key: str = os.getenv("PEXELS_API_KEY", "")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    
    # App Settings & Deployment URLs
    app_base_url: str = os.getenv("APP_BASE_URL", os.getenv("BASE_URL", "http://localhost:8000"))
    admin_feedback_email: str = os.getenv("ADMIN_FEEDBACK_EMAIL", "promotionp270@gmail.com")
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    cron_secret: str = os.getenv("CRON_SECRET", "daily-inspiration-secret-key-change-in-prod")
    otp_expiry_minutes: int = int(os.getenv("OTP_EXPIRY_MINUTES", "5"))
    otp_max_attempts: int = int(os.getenv("OTP_MAX_ATTEMPTS", "3"))
    otp_rate_limit_minutes: int = int(os.getenv("OTP_RATE_LIMIT_MINUTES", "1"))

    @property
    def clean_base_url(self) -> str:
        """Return base application URL without trailing slash."""
        url = self.app_base_url or "http://localhost:8000"
        return url.strip().rstrip("/")

    @property
    def base_url(self) -> str:
        """Alias for clean_base_url."""
        return self.clean_base_url
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

