"""CLI entrypoint for smolserve."""

import asyncio
import logging
import sys

from .config import parse_args
from .server import SmolServe


def main(args: list[str] | None = None) -> int:
    """Main CLI entrypoint.

    Args:
        args: Command line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit status code.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        config = parse_args(args)
        asyncio.run(SmolServe(config).start())
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        logging.error("Fatal error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
