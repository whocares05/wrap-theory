# Wrap Theory FastAPI backend

The backend uses FastAPI, async SQLAlchemy, Alembic, asyncpg, Pydantic, structured logging, and Supabase Auth JWT verification. It separates HTTP transport (`app/api`), use cases (`app/services`), persistence (`app/models`, `app/db`), and providers (`app/integrations`).

All money is integer paisa. Order totals are recalculated from database prices. Order creation locks store, zone, product, coupon, and inventory records in one transaction and combines a PostgreSQL advisory lock with a unique idempotency key to prevent duplicates.

## API surface

- Public: store, menu, zones, coupon quotes, guest order creation and token-protected tracking
- Operations: dashboard, orders, guarded transitions, cancellations, refunds, menu, stock, customers, coupons, campaigns, tasks, reports, and live order events
- Administration: staff invitations/roles, store configuration, audit records, campaign dispatch, and refund decisions

Admin routes require a valid Supabase access token and an active `staff_profiles` record. Managers operate the store; administrator-only operations remain separately guarded.

## Integrations

WhatsApp uses a durable database outbox with retry scheduling. Order notifications are marked skipped while disabled, and campaign dispatch is refused.

Safepay is intentionally not live because it charges per transaction and requires merchant onboarding. The payment boundary exists, but COD is enforced until credentials and signed webhooks are confirmed and tested. Never enable it before completing that work.

The POS protocol and disabled adapter in `app/integrations/pos.py` allow a future vendor to be added without changing order-domain code.
