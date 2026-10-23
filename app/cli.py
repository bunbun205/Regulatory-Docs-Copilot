import argparse
import asyncio
import sys

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.security import Scope, generate_api_key, hash_api_key
from app.db.models import ApiKey
from app.db.session import Database


async def _create_key(name: str, scope: Scope) -> int:
    database = Database(settings.DATABASE_URL)
    try:
        plaintext = generate_api_key()
        async with database.sessionmaker() as session:
            session.add(
                ApiKey(
                    name=name,
                    key_hash=hash_api_key(plaintext),
                    scope=scope.value,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                print(
                    f"Error: an API key named {name!r} already exists.",
                    file=sys.stderr,
                )
                return 1
        print(plaintext)
        return 0
    finally:
        await database.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_key = subparsers.add_parser(
        "create-key",
        help="Create an API key and print the plaintext key once.",
    )
    create_key.add_argument("--name", required=True, help="Human-readable key name.")
    create_key.add_argument(
        "--scope",
        required=True,
        choices=[scope.value for scope in Scope],
        help="Key scope. A write key also has read access.",
    )

    args = parser.parse_args(argv)
    if args.command == "create-key":
        return asyncio.run(_create_key(args.name, Scope(args.scope)))
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
