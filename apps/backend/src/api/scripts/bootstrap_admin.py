"""Create or update the first administrator / 建立或更新第一個管理員。"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from api.core.database import session_factory
from api.core.security import hash_password
from api.domain.models import User


async def create_admin(email: str, password: str) -> None:
    normalized_email = email.strip().lower()
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()
        if user is None:
            session.add(
                User(
                    email=normalized_email,
                    password_hash=hash_password(password),
                    role="admin",
                    is_active=True,
                )
            )
        else:
            user.password_hash = hash_password(password)
            user.role = "admin"
            user.is_active = True
        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a BiteMap administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    if len(args.password) < 6:
        parser.error("password must contain at least 6 characters")
    asyncio.run(create_admin(args.email, args.password))
    print(f"Administrator ready: {args.email.strip().lower()}")


if __name__ == "__main__":
    main()
