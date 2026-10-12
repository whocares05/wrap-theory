# Setup checklist

1. Create a Supabase project.
2. Configure `backend/.env` and `frontend/.env.local` from their examples.
3. Run `python -m alembic upgrade head` in `backend/`.
4. Create the first administrator with `backend/scripts/create_staff.py`.
5. Start FastAPI on port 4000 and the frontend on its Vite port.
6. Replace the seeded branch contact details, address, hours, delivery zones, stock, and tax setting before launch.
7. Leave WhatsApp and Safepay disabled until provider credentials and commercial terms are approved.

Full instructions are in `README.md`.
