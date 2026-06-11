from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    ENV: str = "dev"
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ALGORITHM: str = "HS256"

    SMS_PROVIDER: str = "console"
    SMS_API_KEY: str = ""
    SMS_TEMPLATE: str = "hafteyar-otp"
    OTP_EXPIRE_MINUTES: int = 5
    OTP_RESEND_SECONDS: int = 60
    OTP_MAX_ATTEMPTS: int = 5

    # Webhook Bot Configurations
    TELEGRAM_BOT_TOKEN: str = ""
    BALE_BOT_TOKEN: str = ""
    FRONTEND_URL: str = "http://localhost:3000"


settings = Settings()

