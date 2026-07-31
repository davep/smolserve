"""Finger protocol server implementation.

Listens for Finger queries (RFC 1288) and responds with the contents of a plan file.
"""

from pathlib import Path
import asyncio
import logging

logger = logging.getLogger(__name__)


class FingerServer:
    """Finger protocol (RFC 1288) server."""

    def __init__(self, host: str, port: int, plan_file: Path):
        """Initialize the Finger server.

        Args:
            host: Host IP or hostname to bind.
            port: Port to listen on (default 79 or 7979).
            plan_file: Path to the plan file to serve.
        """
        self.host = host
        self.port = port
        self.plan_file = plan_file
        self.server: asyncio.Server | None = None

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming Finger request.

        Args:
            reader: Stream reader for incoming socket.
            writer: Stream writer for outgoing socket.
        """
        try:
            # Read query line (up to 1024 bytes)
            line = await asyncio.wait_for(reader.readline(), timeout=10.0)
            query = line.decode("utf-8", errors="replace").strip()
            logger.info("Finger request from %s for query: '%s'", writer.get_extra_info("peername"), query)

            # Read plan file
            plan_path = self.plan_file.expanduser().resolve()
            if plan_path.is_file():
                try:
                    content = plan_path.read_text(encoding="utf-8", errors="replace")
                except Exception as exc:
                    content = f"Error reading plan file: {exc}\r\n"
            else:
                content = f"No plan file found at {self.plan_file}\r\n"

            # Format response with CRLF
            lines = content.splitlines()
            formatted = "\r\n".join(lines) + "\r\n"
            writer.write(formatted.encode("utf-8"))
            await writer.drain()
        except asyncio.TimeoutError:
            logger.warning("Finger request timed out.")
        except Exception as exc:
            logger.error("Error handling Finger request: %s", exc)
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        """Start listening for incoming Finger requests."""
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        logger.info("Finger server listening on %s:%d (plan file: %s)", self.host, self.port, self.plan_file)

    async def stop(self) -> None:
        """Stop the Finger server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Finger server stopped.")
