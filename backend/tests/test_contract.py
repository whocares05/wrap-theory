import os

os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "postgresql+asyncpg://postgres:password@localhost:5432/postgres",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "anon-key-with-more-than-twenty-characters",
        "SUPABASE_SERVICE_ROLE_KEY": "service-key-with-more-than-twenty-characters",
        "INTERNAL_JOB_SECRET": "a-secure-test-secret-with-at-least-32-characters",
        "FRONTEND_ORIGINS": "http://localhost:3000,https://shop.example.com",
    }
)

from app.core.config import get_settings, normalize_database_url  # noqa: E402
from app.main import app  # noqa: E402


def test_environment_parses_comma_separated_origins() -> None:
    assert get_settings().frontend_origins == ["http://localhost:3000", "https://shop.example.com"]


def test_openapi_exposes_public_and_protected_surfaces() -> None:
    paths = app.openapi()["paths"]
    assert "/v1/public/orders" in paths
    assert "/v1/public/menu" in paths
    assert "/v1/admin/orders" in paths
    assert "/v1/admin/reports/sales" in paths
    assert "/v1/admin/staff/invitations" in paths


def test_safepay_and_whatsapp_default_to_disabled() -> None:
    settings = get_settings()
    assert settings.safepay_enabled is False
    assert settings.whatsapp_enabled is False


def test_supabase_copied_database_url_is_normalized() -> None:
    raw = "postgresql://postgres.ref:p@ss@pooler.supabase.com:5432/postgres?pgbouncer=true?sslmode=require"
    assert normalize_database_url(raw) == (
        "postgresql+asyncpg://postgres.ref:p%40ss@pooler.supabase.com:5432/postgres?ssl=require"
    )
    assert normalize_database_url(raw, async_driver=False) == (
        "postgresql+psycopg://postgres.ref:p%40ss@pooler.supabase.com:5432/postgres?sslmode=require"
    )
