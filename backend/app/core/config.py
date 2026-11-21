from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./emr.db"
    jwt_secret: str = "change-me-in-production-use-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    seed_on_startup: bool = False
    clinic_name: str = "Endo Clinic"
    # "production" turns on strict startup checks and removes demo accounts and API docs.
    environment: str = "development"
    # When false, only the first doctor or a signed-in doctor can create doctor accounts.
    allow_public_registration: bool = False
    public_base_url: str = ""  # Optional address patients can open, such as https://clinic.example.com
    # Optional Twilio WhatsApp Business API (auto-send). Without these, app uses wa.me deep links.
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""  # e.g. whatsapp:+14155238886

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def uses_default_jwt_secret(self) -> bool:
        return self.jwt_secret.startswith("change-me")

    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
