"""Asynchronous unit and integration tests for Finger, Gopher, and Gemini servers."""

import asyncio
import ssl
import tempfile
from pathlib import Path

import pytest

from smolserve.finger import FingerServer
from smolserve.gemini import GeminiServer
from smolserve.gopher import GopherServer


@pytest.mark.asyncio
async def test_finger_server() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_file = Path(tmpdir) / "plan.txt"
        plan_file.write_text("Hello Finger World!\r\nLine 2\n", encoding="utf-8")

        server = FingerServer(host="127.0.0.1", port=0, plan_file=plan_file)
        await server.start()
        assert server.server is not None
        actual_port = server.server.sockets[0].getsockname()[1]

        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"dave\r\n")
            await writer.drain()

            response = await reader.read()
            writer.close()
            await writer.wait_closed()

            assert "Hello Finger World!" in response.decode("utf-8")
            assert "Line 2" in response.decode("utf-8")
        finally:
            await server.stop()


@pytest.mark.asyncio
async def test_gopher_server_directory_and_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "test.txt").write_text("Gopher text content", encoding="utf-8")

        server = GopherServer(host="127.0.0.1", port=0, root=root)
        await server.start()
        assert server.server is not None
        actual_port = server.server.sockets[0].getsockname()[1]

        try:
            # Request root menu
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"\r\n")
            await writer.drain()
            menu_response = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()

            assert "0test.txt\t/test.txt" in menu_response
            assert menu_response.endswith(".\r\n")

            # Request text file
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"/test.txt\r\n")
            await writer.drain()
            file_response = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()

            assert "Gopher text content" in file_response
            assert file_response.endswith(".\r\n")
        finally:
            await server.stop()


@pytest.mark.asyncio
async def test_gopher_server_security_path_traversal() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        server = GopherServer(host="127.0.0.1", port=0, root=root)
        await server.start()
        assert server.server is not None
        actual_port = server.server.sockets[0].getsockname()[1]

        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"/../secret.txt\r\n")
            await writer.drain()
            response = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()

            assert "3Access denied" in response or "3Item not found" in response
        finally:
            await server.stop()


@pytest.mark.asyncio
async def test_gopher_server_gophermap_dot_termination() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        gophermap_content = (
            "Welcome to Gopher\n0File 1\t/file1.txt\n.\nThis line should be ignored\n"
        )
        (root / "gophermap").write_text(gophermap_content, encoding="utf-8")

        server = GopherServer(host="127.0.0.1", port=0, root=root)
        await server.start()
        assert server.server is not None
        actual_port = server.server.sockets[0].getsockname()[1]

        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"\r\n")
            await writer.drain()
            response = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()

            assert "iWelcome to Gopher" in response
            assert "0File 1\t/file1.txt" in response
            assert "i." not in response
            assert "This line should be ignored" not in response
            assert response.endswith(".\r\n")
        finally:
            await server.stop()


@pytest.mark.asyncio
async def test_gemini_server_gmi_and_not_found() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "index.gmi").write_text(
            "# Gemini Title\n\nGemini text", encoding="utf-8"
        )

        server = GeminiServer(host="127.0.0.1", port=0, root=root)
        await server.start()
        assert server.server is not None
        actual_port = server.server.sockets[0].getsockname()[1]

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        try:
            # Request index.gmi via root path
            reader, writer = await asyncio.open_connection(
                "127.0.0.1", actual_port, ssl=ssl_ctx
            )
            writer.write(f"gemini://127.0.0.1:{actual_port}/\r\n".encode())
            await writer.drain()
            response = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()

            assert response.startswith("20 text/gemini")
            assert "# Gemini Title" in response

            # Request non-existent file
            reader, writer = await asyncio.open_connection(
                "127.0.0.1", actual_port, ssl=ssl_ctx
            )
            writer.write(f"gemini://127.0.0.1:{actual_port}/missing.gmi\r\n".encode())
            await writer.drain()
            not_found_resp = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()

            assert not_found_resp.startswith("51 ")
        finally:
            await server.stop()
