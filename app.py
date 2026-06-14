#!/usr/bin/env python3
"""Demo production entry point for Constrain framework.

This is a template for running Constrain in containerized production.
Customize skills, register workflows, and wire up agents as needed.

Run with docker-compose:
    docker compose up -d

Or standalone:
    CONSTRAIN_MODE=production python app.py
"""

import asyncio
import logging
import os

from core.harness import Harness, HarnessConfig

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")


async def main():
    # Load config from env vars (docker-compose or .env)
    config = HarnessConfig()
    config.apply_env_overrides()
    config.tracing_enabled = True
    config.tracing_mode = os.getenv("CONSTRAIN_TRACING_MODE", "production")

    harness = Harness(config)

    # === Register your skills here ===
    # from my_skills import MySkill
    # harness.register_skill(MySkill())

    # === Register your workflows here ===
    # harness._skill_registry.register_workflow("my_workflow", build_my_workflow())

    try:
        await harness.start()
        logger.info("Constrain framework ready | mode=%s", config.mode)

        # Keep alive — in production this would be your HTTP/gRPC server
        logger.info("Waiting for tasks... (press Ctrl+C to stop)")
        while True:
            await asyncio.sleep(10)

    except asyncio.CancelledError:
        pass
    finally:
        await harness.shutdown()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
