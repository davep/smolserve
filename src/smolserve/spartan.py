"""Spartan protocol server implementation.

Listens for Spartan requests over TCP and serves Gemtext documents, static files,
and directory listings from a specified root directory.
"""

import asyncio
import logging
import mimetypes
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)


class SpartanServer:
    """Spartan protocol server."""

    def __init__(self, host: str, port: int, root: Path):
        """Initialize the Spartan server.

        Args:
            host: Host IP or hostname to bind.
            port: Port to listen on (default 3000).
            root: Root directory containing Spartan content.
        """
        self.host = host
        self.port = port
        self.root = root.expanduser().resolve()
        self.server: asyncio.Server | None = None

    def _generate_directory_listing(
        self, dir_path: Path, relative_prefix: str
    ) -> bytes:
        """Generate a Gemtext directory listing.

        Args:
            dir_path: Directory path to list.
            relative_prefix: Request path prefix for building links.

        Returns:
            Bytes containing Gemtext directory listing content.
        """
        prefix = f"/{relative_prefix.strip('/')}" if relative_prefix.strip("/") else ""
        lines = [f"# Directory listing for {prefix or '/'}", ""]

        if prefix:
            parent_link = "/".join(prefix.split("/")[:-1]) or "/"
            lines.append(f"=> {parent_link} .. (parent directory)")
            lines.append("")

        try:
            entries = sorted(
                [p for p in dir_path.iterdir() if not p.name.startswith(".")],
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
            for entry in entries:
                display_name = f"{entry.name}/" if entry.is_dir() else entry.name
                rel_url = f"{prefix}/{entry.name}"
                lines.append(f"=> {rel_url} {display_name}")
        except Exception as exc:
            logger.error("Error listing directory %s: %s", dir_path, exc)
            lines.append(f"Error listing directory: {exc}")

        gemtext = "\r\n".join(lines) + "\r\n"
        return gemtext.encode("utf-8")

    def _determine_mime_type(self, path: Path) -> str:
        """Determine MIME type for a file.

        Args:
            path: Target file path.

        Returns:
            MIME string for Spartan response header.
        """
        if path.suffix.lower() in (".gmi", ".gemini"):
            return "text/gemini; charset=utf-8"

        mime, _ = mimetypes.guess_type(path)
        if not mime:
            mime = "application/octet-stream"
        elif mime.startswith("text/") and "charset" not in mime:
            mime += "; charset=utf-8"

        return mime

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming Spartan request.

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
                "Spartan request from %s: '%s'",
                writer.get_extra_info("peername"),
                raw_request,
            )

            parts = raw_request.split(" ", 2)
            if len(parts) != 3:
                writer.write(b"4 Bad request: Invalid request line\r\n")
                await writer.drain()
                return

            _host_str, path_str, length_str = parts

            if not path_str.startswith("/"):
                writer.write(b"4 Bad request: Absolute path required\r\n")
                await writer.drain()
                return

            try:
                content_length = int(length_str)
                if content_length < 0:
                    raise ValueError("Negative content length")
            except ValueError:
                writer.write(b"4 Bad request: Invalid content length\r\n")
                await writer.drain()
                return

            if content_length > 0:
                try:
                    _data_payload = await asyncio.wait_for(
                        reader.readexactly(content_length), timeout=10.0
                    )
                except (asyncio.IncompleteReadError, TimeoutError):
                    writer.write(b"4 Bad request: Failed to read request body\r\n")
                    await writer.drain()
                    return

            rel_path_str = urllib.parse.unquote(path_str).lstrip("/")
            target_path = (self.root / rel_path_str).resolve()

            if not self.root.exists():
                writer.write(b"5 Spartan root directory not found\r\n")
                await writer.drain()
                return

            # Security check: path traversal
            if not target_path.is_relative_to(self.root):
                writer.write(b"4 Access denied\r\n")
                await writer.drain()
                return

            if not target_path.exists():
                writer.write(b"4 File not found\r\n")
                await writer.drain()
                return

            if target_path.is_dir():
                # Check for index.gmi or index.gemini
                index_gmi = target_path / "index.gmi"
                index_gemini = target_path / "index.gemini"

                if index_gmi.is_file():
                    target_path = index_gmi
                elif index_gemini.is_file():
                    target_path = index_gemini
                else:
                    # Serve Gemtext directory listing
                    body = self._generate_directory_listing(target_path, rel_path_str)
                    header = b"2 text/gemini; charset=utf-8\r\n"
                    writer.write(header + body)
                    await writer.drain()
                    return

            # Serve file
            mime = self._determine_mime_type(target_path)
            header = f"2 {mime}\r\n".encode()
            body = target_path.read_bytes()
            writer.write(header + body)
            await writer.drain()

        except TimeoutError:
            logger.warning("Spartan request timed out.")
        except Exception as exc:
            logger.error("Error handling Spartan request: %s", exc)
            try:
                writer.write(b"5 Server error\r\n")
                await writer.drain()
            except Exception:
                pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        """Start listening for incoming Spartan requests."""
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        logger.info(
            "Spartan server listening on spartan://%s:%d (root: %s)",
            self.host,
            self.port,
            self.root,
        )

    async def stop(self) -> None:
        """Stop the Spartan server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Spartan server stopped.")
