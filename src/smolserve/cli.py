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
    try:
        config = parse_args(args)

        if config.verbose:
            log_level = logging.DEBUG
        elif config.quiet or (config.exec_command is not None):
            log_level = logging.WARNING
        else:
            log_level = logging.INFO

        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )

        code = asyncio.run(SmolServe(config).start())
        return code
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        logging.error("Fatal error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
