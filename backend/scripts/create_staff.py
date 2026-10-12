import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# Running `python scripts/create_staff.py` otherwise puts only scripts/ first on
# sys.path and can accidentally import an older globally installed `app` package.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import httpx  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.models.entities import StaffProfile, StaffRole  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="Invite or register the initial Wrap Theory staff user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=[role.value for role in StaffRole], default="admin")
    args = parser.parse_args()
    settings = get_settings()
    service_key = settings.supabase_service_role_key.get_secret_value()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{str(settings.supabase_url).rstrip('/')}/auth/v1/invite",
            params={"redirect_to": f"{str(settings.frontend_app_url).rstrip('/')}/auth/callback"},
            headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
            json={"email": args.email},
        )
        response.raise_for_status()
        user_id = uuid.UUID(response.json()["id"])
    database = Database(settings)
    try:
        async with database.sessions() as session, session.begin():
            await session.execute(
                insert(StaffProfile)
                .values(
                    user_id=user_id,
                    email=args.email.lower(),
                    display_name=args.name,
                    role=StaffRole(args.role),
                )
                .on_conflict_do_update(
                    index_elements=[StaffProfile.user_id],
                    set_={
                        "email": args.email.lower(),
                        "display_name": args.name,
                        "role": StaffRole(args.role),
                        "is_active": True,
                    },
                )
            )
    finally:
        await database.close()
    print(f"Invitation sent and {args.role} profile created for {args.email}")


if __name__ == "__main__":
    asyncio.run(main())
