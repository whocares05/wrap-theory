from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import quote

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def normalize_database_url(raw_url: str, *, async_driver: bool = True) -> str:
    """Convert Supabase's copied URI into a SQLAlchemy-safe connection URL."""
    value = raw_url.strip().strip('"').strip("'")
    if "://" not in value:
        raise ValueError("DATABASE_URL must be a PostgreSQL connection URI")

    _scheme, remainder = value.split("://", 1)
    if "@" not in remainder:
        raise ValueError("DATABASE_URL must include credentials and a database host")

    # The final @ separates credentials from the host. Any earlier @ belongs to
    # the password and must be percent-encoded for a valid URI.
    credentials, host_and_path = remainder.rsplit("@", 1)
    if ":" not in credentials:
        raise ValueError("DATABASE_URL must include a database password")
    username, password = credentials.split(":", 1)
    encoded_password = quote(password, safe="%")

    path, separator, raw_query = host_and_path.partition("?")
    query_parts = []
    if separator:
        for part in raw_query.replace("?", "&").split("&"):
            if not part or part.lower().startswith("pgbouncer="):
                continue
            if part.lower().startswith(("sslmode=", "ssl=")):
                ssl_value = part.split("=", 1)[1]
                part = f"ssl={ssl_value}" if async_driver else f"sslmode={ssl_value}"
            query_parts.append(part)
    ssl_key = "ssl" if async_driver else "sslmode"
    if not any(part.lower().startswith(("ssl=", "sslmode=")) for part in query_parts):
        query_parts.append(f"{ssl_key}=require")

    driver = "postgresql+asyncpg" if async_driver else "postgresql+psycopg"
    query = f"?{'&'.join(query_parts)}" if query_parts else ""
    return f"{driver}://{username}:{encoded_password}@{path}{query}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    host: str = "0.0.0.0"
    port: int = Field(default=4000, ge=1, le=65535)
    log_level: str = "INFO"
    api_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:4000")
    frontend_app_url: AnyHttpUrl = AnyHttpUrl("http://localhost:5173")
    frontend_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    allowed_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1"]

    database_url: SecretStr
    supabase_url: AnyHttpUrl
    supabase_anon_key: SecretStr
    supabase_service_role_key: SecretStr
    supabase_jwt_audience: str = "authenticated"
    internal_job_secret: SecretStr = Field(min_length=32)

    whatsapp_enabled: bool = False
    whatsapp_phone_number_id: str | None = None
    whatsapp_access_token: SecretStr | None = None
    whatsapp_api_version: str = "v23.0"
    whatsapp_order_template: str = "order_confirmation"
    whatsapp_marketing_template: str = "marketing_campaign"
    whatsapp_template_language: str = "en"

    safepay_enabled: bool = False
    safepay_environment: Literal["sandbox", "production"] = "sandbox"
    safepay_api_key: SecretStr | None = None
    safepay_webhook_secret: SecretStr | None = None

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def split_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return [host.strip() for host in value.split(",") if host.strip()]
        return value

    @model_validator(mode="after")
    def validate_integrations(self) -> "Settings":
        if self.environment == "production" and "*" in self.allowed_hosts:
            raise ValueError("ALLOWED_HOSTS cannot contain '*' in production")
        if self.whatsapp_enabled and not (self.whatsapp_phone_number_id and self.whatsapp_access_token):
            raise ValueError("WhatsApp is enabled but its phone number ID or access token is missing")
        if self.safepay_enabled and not (self.safepay_api_key and self.safepay_webhook_secret):
            raise ValueError("Safepay is enabled but its API key or webhook secret is missing")
        return self

    @property
    def supabase_issuer(self) -> str:
        return f"{str(self.supabase_url).rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_issuer}/.well-known/jwks.json"

    @property
    def async_database_url(self) -> str:
        return normalize_database_url(self.database_url.get_secret_value())

    @property
    def migration_database_url(self) -> str:
        return normalize_database_url(self.database_url.get_secret_value(), async_driver=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
