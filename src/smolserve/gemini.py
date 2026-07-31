"""Gemini protocol server implementation.

Listens for Gemini requests (Project Gemini spec) over TLS and serves Gemtext
documents and static files from a specified root directory.
"""

from pathlib import Path
import asyncio
import logging
import mimetypes
import ssl
import urllib.parse

from .certs import ensure_certificate

logger = logging.getLogger(__name__)


class GeminiServer:
    """Gemini protocol server."""

    def __init__(
        self,
        host: str,
        port: int,
        root: Path,
        cert_file: Path | None = None,
        key_file: Path | None = None,
    ):
        """Initialize the Gemini server.

        Args:
            host: Host IP or hostname to bind.
            port: Port to listen on (default 1965).
            root: Root directory containing Gemini content.
            cert_file: Optional path to PEM TLS certificate file.
            key_file: Optional path to PEM TLS private key file.
        """
        self.host = host
        self.port = port
        self.root = root.expanduser().resolve()
        self.cert_file = cert_file
        self.key_file = key_file
        self.server: asyncio.Server | None = None

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create and configure the SSL context for Gemini TLS.

        Returns:
            Configured ssl.SSLContext instance.
        """
        cache_dir = Path.home() / ".cache" / "smolserve"
        cert_path, key_path = ensure_certificate(
            self.cert_file, self.key_file, default_dir=cache_dir, hostname=self.host
        )

        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        return ssl_ctx

    def _generate_directory_listing(self, dir_path: Path, relative_prefix: str) -> bytes:
        """Generate a Gemtext directory listing.

        Args:
            dir_path: Directory path to list.
            relative_prefix: Request path prefix for building links.

        Returns:
            Bytes containing Gemtext directory listing content.
        """
        prefix = f"/{relative_prefix.strip('/')}" if relative_prefix.strip('/') else ""
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
            MIME string for Gemini response header.
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
        """Handle an incoming Gemini request.

        Args:
            reader: Stream reader for incoming socket.
            writer: Stream writer for outgoing socket.
        """
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=10.0)
            if not line:
                return

            raw_url = line.decode("utf-8", errors="replace").rstrip("\r\n")
            logger.info("Gemini request from %s: '%s'", writer.get_extra_info("peername"), raw_url)

            # Parse URL
            parsed = urllib.parse.urlparse(raw_url)

            # Validate scheme if present
            if parsed.scheme and parsed.scheme.lower() != "gemini":
                writer.write(b"59 Bad request: Invalid URL scheme\r\n")
                await writer.drain()
                return

            rel_path_str = urllib.parse.unquote(parsed.path).lstrip("/")
            target_path = (self.root / rel_path_str).resolve()

            if not self.root.exists():
                writer.write(b"51 Gemini root directory not found\r\n")
                await writer.drain()
                return

            # Security check: path traversal
            if not target_path.is_relative_to(self.root):
                writer.write(b"59 Access denied\r\n")
                await writer.drain()
                return

            if not target_path.exists():
                writer.write(b"51 File not found\r\n")
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
                    header = f"20 text/gemini; charset=utf-8\r\n".encode("utf-8")
                    writer.write(header + body)
                    await writer.drain()
                    return

            # Serve file
            mime = self._determine_mime_type(target_path)
            header = f"20 {mime}\r\n".encode("utf-8")
            body = target_path.read_bytes()
            writer.write(header + body)
            await writer.drain()

        except asyncio.TimeoutError:
            logger.warning("Gemini request timed out.")
        except Exception as exc:
            logger.error("Error handling Gemini request: %s", exc)
            try:
                writer.write(b"59 Server error\r\n")
                await writer.drain()
            except Exception:
                pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        """Start listening for incoming Gemini TLS requests."""
        ssl_ctx = self._create_ssl_context()
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port, ssl=ssl_ctx
        )
        logger.info("Gemini server listening on gemini://%s:%d (root: %s)", self.host, self.port, self.root)

    async def stop(self) -> None:
        """Stop the Gemini server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Gemini server stopped.")
