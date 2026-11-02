import argparse
import asyncio

from app.core.config import settings
from app.providers.mpesa_daraja import MpesaDarajaProvider


async def register_c2b_urls() -> None:
    if not settings.mpesa_enabled:
        raise RuntimeError("Enable and configure M-Pesa before registering C2B callbacks")
    provider = MpesaDarajaProvider()
    try:
        result = await provider.register_c2b_urls()
    finally:
        await provider.aclose()
    print(result.get("ResponseDescription", "C2B callbacks registered"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the Finance Platform Daraja integration.")
    parser.add_argument("command", choices=["register-c2b"])
    args = parser.parse_args()
    if args.command == "register-c2b":
        asyncio.run(register_c2b_urls())


if __name__ == "__main__":
    main()
