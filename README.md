# Wrap Theory

Wrap Theory is now a two-service application:

- `frontend/` — Vinext/Next.js React storefront and staff operations UI
- `backend/` — Python FastAPI service backed by Supabase PostgreSQL and Supabase Auth

Customers use guest checkout. Only invited `admin` and `manager` users can access operations. Cash on delivery is the only enabled payment method. Safepay and WhatsApp are isolated, disabled adapters that can be activated after provider onboarding and credentials are available.

## Architecture

```text
Browser (storefront + staff UI)
        |
        | HTTPS / Bearer JWT for staff
        v
FastAPI backend -----------------> Meta WhatsApp Cloud API (optional)
        |                         Safepay (disabled pending merchant onboarding)
        |
        +---- Supabase Auth (staff identity)
        +---- Supabase PostgreSQL (all business data)
```

The frontend never receives the Supabase service key or direct access to business tables. PostgreSQL RLS is enabled and browser roles are revoked; the backend owns validation, pricing, stock, and authorization.

## Local setup

Requirements: Node.js 22.13+, Python 3.12+, npm, and a Supabase project.

1. Copy `backend/.env.example` to `backend/.env` and fill in the Supabase values.
2. Copy `frontend/.env.example` to `frontend/.env.local` and fill in its public values.
3. Install and migrate the backend:

   ```bash
   cd backend
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # Linux/macOS: source .venv/bin/activate
   python -m pip install -e ".[dev]"
   python -m alembic upgrade head
   python scripts/create_staff.py --email owner@example.com --name "Owner Name" --role admin
   uvicorn app.main:app --reload --port 4000
   ```

4. Start the frontend in another terminal:

   ```bash
   cd frontend
   npm ci
   npm run dev
   ```

The API is at `http://localhost:4000`; Swagger is at `/docs` outside production. Use the **Team CRM** link on the storefront to sign in with the invited staff account.

## Supabase connection

Use the Supabase session pooler for a persistent Docker/container backend. Convert the URI scheme to `postgresql+asyncpg://` and use `?ssl=require`, as shown in `backend/.env.example`. Alembic automatically switches that URL to psycopg for migrations. Keep the service-role key only in backend secrets.

The initial migration creates menu/modifiers, ingredient recipes and stock movements, guest customers, idempotent orders, payments, cancellations, refunds, coupons, campaigns, notifications, team tasks, RBAC staff, audit logs, reports, and delivery settings.

It seeds the current wraps, a Gulberg branch, two editable Lahore delivery zones, delivery-only fulfillment, a Rs. 500 minimum, Rs. 150/250 zone fees, free-delivery thresholds, and zero tax until the business supplies its registered tax requirement.

## Verification

```bash
cd backend
ruff check app tests scripts alembic
mypy app
pytest

cd ../frontend
npm exec tsc -- --noEmit
npm exec eslint -- app lib worker
npm run build            # Linux/CI; on Windows use: npm exec vite -- build
```

## Deployment

- Deploy `backend/` as a Docker service using `backend/Dockerfile`.
- Run `python -m alembic upgrade head` as a release command before starting a new backend version.
- Set `ENVIRONMENT=production`, exact `FRONTEND_ORIGINS`, exact `ALLOWED_HOSTS`, and all Supabase secrets in the host.
- Deploy `frontend/` independently and point `NEXT_PUBLIC_API_URL` at the HTTPS backend.
- Add global rate limiting/WAF rules at the ingress or CDN. The API also has a bounded per-process order limit.
- Keep WhatsApp and Safepay disabled until provider credentials, templates, commercial terms, and webhook behavior are approved.

See `backend/README.md` for backend operations and production notes.
