"""Gopher protocol server implementation.

Listens for Gopher requests (RFC 1436) and serves directory menus (gophermaps)
and files from a specified root directory.
"""

from pathlib import Path
import asyncio
import logging
import mimetypes
import urllib.parse

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = {
    ".txt", ".gmi", ".gemini", ".md", ".py", ".c", ".h", ".json",
    ".toml", ".yaml", ".yml", ".html", ".htm", ".css", ".js", ".sh",
    ".rst", ".org", ".log", ".csv",
}

IMAGE_EXTENSIONS = {
    ".gif", ".jpg", ".jpeg", ".png", ".bmp", ".webp",
}


class GopherServer:
    """Gopher protocol (RFC 1436) server."""

    def __init__(self, host: str, port: int, root: Path):
        """Initialize the Gopher server.

        Args:
            host: Host IP or hostname to bind.
            port: Port to listen on (default 70 or 7070).
            root: Root directory containing Gopher content.
        """
        self.host = host
        self.port = port
        self.root = root.expanduser().resolve()

    def _determine_item_type(self, path: Path) -> str:
        """Determine Gopher item type character for a file path.

        Args:
            path: Path to inspect.

        Returns:
            Single character Gopher type code ('0', '1', 'g', '9', etc.).
        """
        if path.is_dir():
            return "1"
        ext = path.suffix.lower()
        if ext in TEXT_EXTENSIONS:
            return "0"
        if ext in IMAGE_EXTENSIONS:
            return "g" if ext == ".gif" else "I"
        return "9"

    def _generate_directory_menu(self, dir_path: Path, relative_prefix: str) -> str:
        """Generate a Gopher menu string for a directory.

        Args:
            dir_path: Directory path to scan.
            relative_prefix: Selector prefix for items in this directory.

        Returns:
            Formatted Gopher menu text ending with CRLF lines.
        """
        gophermap_file = dir_path / "gophermap"
        lines = []

        if gophermap_file.is_file():
            # Parse user custom gophermap file
            try:
                map_content = gophermap_file.read_text(encoding="utf-8", errors="replace")
                for raw_line in map_content.splitlines():
                    if not raw_line:
                        lines.append(f"i\t\t{self.host}\t{self.port}")
                        continue

                    if "\t" in raw_line:
                        parts = raw_line.split("\t")
                        item_type_label = parts[0]
                        selector = parts[1] if len(parts) > 1 else ""
                        host = parts[2] if len(parts) > 2 and parts[2] else self.host
                        port = parts[3] if len(parts) > 3 and parts[3] else str(self.port)
                        lines.append(f"{item_type_label}\t{selector}\t{host}\t{port}")
                    else:
                        # Plain text in gophermap is info text ('i')
                        # Check if first char is a valid type code
                        first_char = raw_line[0]
                        if first_char in "0123456789+gIih":
                            label = raw_line[1:]
                            lines.append(f"{first_char}{label}\t\t{self.host}\t{self.port}")
                        else:
                            lines.append(f"i{raw_line}\t\t{self.host}\t{self.port}")
            except Exception as exc:
                logger.error("Error reading gophermap in %s: %s", dir_path, exc)
                lines.append(f"3Error reading gophermap\t\t{self.host}\t{self.port}")
        else:
            # Auto-generate menu listing
            lines.append(f"iDirectory listing for /{relative_prefix}\t\t{self.host}\t{self.port}")
            lines.append(f"i\t\t{self.host}\t{self.port}")

            try:
                entries = sorted(
                    [p for p in dir_path.iterdir() if not p.name.startswith(".")],
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
                for entry in entries:
                    item_type = self._determine_item_type(entry)
                    rel_path = f"{relative_prefix}/{entry.name}".lstrip("/")
                    selector = f"/{rel_path}"
                    lines.append(f"{item_type}{entry.name}\t{selector}\t{self.host}\t{self.port}")
            except Exception as exc:
                logger.error("Error listing directory %s: %s", dir_path, exc)
                lines.append(f"3Error listing directory\t\t{self.host}\t{self.port}")

        return "\r\n".join(lines) + "\r\n.\r\n"

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming Gopher request.

        Args:
            reader: Stream reader for incoming socket.
            writer: Stream writer for outgoing socket.
        """
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=10.0)
            raw_selector = line.decode("utf-8", errors="replace").rstrip("\r\n")

            # Remove tab-separated query if present (e.g. search query)
            selector_parts = raw_selector.split("\t")
            selector = urllib.parse.unquote(selector_parts[0]).lstrip("/")

            logger.info("Gopher request from %s for selector: '%s'", writer.get_extra_info("peername"), selector)

            # Security check: path traversal prevention
            target_path = (self.root / selector).resolve()

            if not self.root.exists():
                error_menu = f"3Gopher root directory not found\t\t{self.host}\t{self.port}\r\n.\r\n"
                writer.write(error_menu.encode("utf-8"))
                await writer.drain()
                return

            if not target_path.is_relative_to(self.root):
                error_menu = f"3Access denied\t\t{self.host}\t{self.port}\r\n.\r\n"
                writer.write(error_menu.encode("utf-8"))
                await writer.drain()
                return

            if not target_path.exists():
                error_menu = f"3Item not found: /{selector}\t\t{self.host}\t{self.port}\r\n.\r\n"
                writer.write(error_menu.encode("utf-8"))
                await writer.drain()
                return

            if target_path.is_dir():
                menu = self._generate_directory_menu(target_path, selector)
                writer.write(menu.encode("utf-8"))
                await writer.drain()
            else:
                item_type = self._determine_item_type(target_path)
                if item_type == "0":
                    # Text file: write lines with dot-stuffing and trailing .\r\n
                    text_content = target_path.read_text(encoding="utf-8", errors="replace")
                    stuffed_lines = []
                    for t_line in text_content.splitlines():
                        if t_line.startswith("."):
                            t_line = "." + t_line
                        stuffed_lines.append(t_line)
                    response_text = "\r\n".join(stuffed_lines) + "\r\n.\r\n"
                    writer.write(response_text.encode("utf-8"))
                    await writer.drain()
                else:
                    # Binary file: send raw bytes without trailing period
                    writer.write(target_path.read_bytes())
                    await writer.drain()

        except asyncio.TimeoutError:
            logger.warning("Gopher request timed out.")
        except Exception as exc:
            logger.error("Error handling Gopher request: %s", exc)
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        """Start listening for incoming Gopher requests."""
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        logger.info("Gopher server listening on %s:%d (root: %s)", self.host, self.port, self.root)

    async def stop(self) -> None:
        """Stop the Gopher server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Gopher server stopped.")
