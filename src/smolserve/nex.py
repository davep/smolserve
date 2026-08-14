"""Nex protocol server implementation.

Listens for Nex requests over TCP and serves documents, static files,
and directory listings from a specified root directory.
"""

import asyncio
import logging
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)


class NexServer:
    """Nex protocol server."""

    def __init__(self, host: str, port: int, root: Path):
        """Initialize the Nex server.

        Args:
            host: Host IP or hostname to bind.
            port: Port to listen on (default 1900).
            root: Root directory containing Nex content.
        """
        self.host = host
        self.port = port
        self.root = root.expanduser().resolve()
        self.server: asyncio.Server | None = None

    def _generate_directory_listing(
        self, dir_path: Path, relative_prefix: str
    ) -> bytes:
        """Generate a Nex plain text directory listing.

        Args:
            dir_path: Directory path to list.
            relative_prefix: Request path prefix for building links.

        Returns:
            Bytes containing Nex plain text directory listing content.
        """
        prefix = f"/{relative_prefix.strip('/')}" if relative_prefix.strip("/") else ""
        lines = [f"# Directory listing for {prefix or '/'}", ""]

        if prefix:
            parent_link = "/".join(prefix.split("/")[:-1]) or "/"
            if not parent_link.endswith("/"):
                parent_link += "/"
            lines.append(f"=> {parent_link} .. (parent directory)")
            lines.append("")

        try:
            entries = sorted(
                [p for p in dir_path.iterdir() if not p.name.startswith(".")],
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
            for entry in entries:
                if entry.is_dir():
                    display_name = f"{entry.name}/"
                    rel_url = f"{prefix}/{entry.name}/"
                else:
                    display_name = entry.name
                    rel_url = f"{prefix}/{entry.name}"
                lines.append(f"=> {rel_url} {display_name}")
        except Exception as exc:
            logger.error("Error listing directory %s: %s", dir_path, exc)
            lines.append(f"Error listing directory: {exc}")

        content = "\r\n".join(lines) + "\r\n"
        return content.encode()

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming Nex request.

        Args:
            reader: Stream reader for incoming socket.
            writer: Stream writer for outgoing socket.
        """
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=10.0)
            if not line:
                return

            raw_request = line.decode("utf-8", errors="replace").rstrip("\r\n")
            logger.info(
                "Nex request from %s: '%s'",
                writer.get_extra_info("peername"),
                raw_request,
            )

            if raw_request.startswith("nex://") or raw_request.startswith("//"):
                parsed = urllib.parse.urlsplit(raw_request)
                path_str = parsed.path
            else:
                path_str = raw_request

            rel_path_str = urllib.parse.unquote(path_str).lstrip("/")
            target_path = (self.root / rel_path_str).resolve()

            if not self.root.exists():
                writer.write(b"Error: Nex root directory not found\r\n")
                await writer.drain()
                return

            # Security check: path traversal
            if not target_path.is_relative_to(self.root):
                writer.write(b"Error: Access denied\r\n")
                await writer.drain()
                return

            if not target_path.exists():
                writer.write(f"Error: File not found: /{rel_path_str}\r\n".encode())
                await writer.drain()
                return

            if target_path.is_dir():
                # Check for index files
                index_candidates = ("index.txt", "index", "index.nex", "index.gmi")
                index_file = None
                for candidate in index_candidates:
                    cand_path = target_path / candidate
                    if cand_path.is_file():
                        index_file = cand_path
                        break

                if index_file is not None:
                    target_path = index_file
                else:
                    body = self._generate_directory_listing(target_path, rel_path_str)
                    writer.write(body)
                    await writer.drain()
                    return

            # Serve file content as-is
            body = target_path.read_bytes()
            writer.write(body)
            await writer.drain()

        except TimeoutError:
            logger.warning("Nex request timed out.")
        except Exception as exc:
            logger.error("Error handling Nex request: %s", exc)
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        """Start listening for incoming Nex requests."""
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        logger.info(
            "Nex server listening on nex://%s:%d (root: %s)",
            self.host,
            self.port,
            self.root,
        )

    async def stop(self) -> None:
        """Stop the Nex server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Nex server stopped.")
