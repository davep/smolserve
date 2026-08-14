"""Asynchronous unit and integration tests for Finger, Gopher, and Gemini servers."""

import asyncio
import ssl
import tempfile
from pathlib import Path

import pytest

from smolserve.finger import FingerServer
from smolserve.gemini import GeminiServer
from smolserve.gopher import GopherServer
from smolserve.nex import NexServer
from smolserve.spartan import SpartanServer


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


@pytest.mark.asyncio
async def test_spartan_server_gmi_and_not_found() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "index.gmi").write_text(
            "# Spartan Title\n\nSpartan text", encoding="utf-8"
        )

        server = SpartanServer(host="127.0.0.1", port=0, root=root)
        await server.start()
        assert server.server is not None
        actual_port = server.server.sockets[0].getsockname()[1]

        try:
            # Request index.gmi via root path
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"127.0.0.1 / 0\r\n")
            await writer.drain()
            response = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()

            assert response.startswith("2 text/gemini")
            assert "# Spartan Title" in response

            # Request non-existent file
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"127.0.0.1 /missing.gmi 0\r\n")
            await writer.drain()
            not_found_resp = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()

            assert not_found_resp.startswith("4 ")
        finally:
            await server.stop()


@pytest.mark.asyncio
async def test_spartan_server_directory_listing_and_upload() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        subdir = root / "files"
        subdir.mkdir()
        (subdir / "hello.txt").write_text("Hello Spartan", encoding="utf-8")

        server = SpartanServer(host="127.0.0.1", port=0, root=root)
        await server.start()
        assert server.server is not None
        actual_port = server.server.sockets[0].getsockname()[1]

        try:
            # Request directory listing
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"127.0.0.1 /files 0\r\n")
            await writer.drain()
            dir_resp = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()

            assert dir_resp.startswith("2 text/gemini")
            assert "hello.txt" in dir_resp

            # Request file with upload payload
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"127.0.0.1 /files/hello.txt 12\r\nSample Data!")
            await writer.drain()
            file_resp = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()

            assert file_resp.startswith("2 text/plain")
            assert "Hello Spartan" in file_resp
        finally:
            await server.stop()


@pytest.mark.asyncio
async def test_spartan_server_error_handling() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        server = SpartanServer(host="127.0.0.1", port=0, root=root)
        await server.start()
        assert server.server is not None
        actual_port = server.server.sockets[0].getsockname()[1]

        try:
            # Invalid request format (missing parts)
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"invalid request\r\n")
            await writer.drain()
            resp1 = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()
            assert resp1.startswith("4 ")

            # Non-absolute path
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"127.0.0.1 relative/path 0\r\n")
            await writer.drain()
            resp2 = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()
            assert resp2.startswith("4 ")

            # Invalid content-length
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"127.0.0.1 / invalid_len\r\n")
            await writer.drain()
            resp3 = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()
            assert resp3.startswith("4 ")

            # Path traversal attempt
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"127.0.0.1 /../secret 0\r\n")
            await writer.drain()
            resp4 = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()
            assert resp4.startswith("4 ")
        finally:
            await server.stop()


@pytest.mark.asyncio
async def test_nex_server_index_and_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "index.txt").write_text(
            "Hello Nex Index\n=> /about.txt About", encoding="utf-8"
        )
        (root / "hello.txt").write_text("Hello Nex World!", encoding="utf-8")

        server = NexServer(host="127.0.0.1", port=0, root=root)
        await server.start()
        assert server.server is not None
        actual_port = server.server.sockets[0].getsockname()[1]

        try:
            # Request root with empty string
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"\r\n")
            await writer.drain()
            resp_empty = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()
            assert "Hello Nex Index" in resp_empty
            assert "=> /about.txt About" in resp_empty

            # Request root with "/"
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"/\r\n")
            await writer.drain()
            resp_slash = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()
            assert "Hello Nex Index" in resp_slash

            # Request root with "nex://127.0.0.1/"
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(f"nex://127.0.0.1:{actual_port}/\r\n".encode())
            await writer.drain()
            resp_url = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()
            assert "Hello Nex Index" in resp_url

            # Request specific file hello.txt
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"hello.txt\r\n")
            await writer.drain()
            resp_file = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()
            assert resp_file == "Hello Nex World!"

            # Request file with leading slash
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"/hello.txt\r\n")
            await writer.drain()
            resp_file2 = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()
            assert resp_file2 == "Hello Nex World!"
        finally:
            await server.stop()


@pytest.mark.asyncio
async def test_nex_server_directory_listing() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        subdir = root / "docs"
        subdir.mkdir()
        (subdir / "guide.txt").write_text("Nex Guide", encoding="utf-8")
        nested_dir = subdir / "nested"
        nested_dir.mkdir()

        server = NexServer(host="127.0.0.1", port=0, root=root)
        await server.start()
        assert server.server is not None
        actual_port = server.server.sockets[0].getsockname()[1]

        try:
            # Request docs directory (without index file)
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"/docs\r\n")
            await writer.drain()
            dir_resp = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()

            assert "Directory listing for /docs" in dir_resp
            assert "=> / .. (parent directory)" in dir_resp
            assert "=> /docs/guide.txt guide.txt" in dir_resp
            assert "=> /docs/nested/ nested/" in dir_resp
        finally:
            await server.stop()


@pytest.mark.asyncio
async def test_nex_server_binary_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        binary_data = b"\x00\x01\x02\xfe\xff\xaa\x55"
        (root / "sample.bin").write_bytes(binary_data)

        server = NexServer(host="127.0.0.1", port=0, root=root)
        await server.start()
        assert server.server is not None
        actual_port = server.server.sockets[0].getsockname()[1]

        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"/sample.bin\r\n")
            await writer.drain()
            resp = await reader.read()
            writer.close()
            await writer.wait_closed()

            assert resp == binary_data
        finally:
            await server.stop()


@pytest.mark.asyncio
async def test_nex_server_security_and_errors() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        server = NexServer(host="127.0.0.1", port=0, root=root)
        await server.start()
        assert server.server is not None
        actual_port = server.server.sockets[0].getsockname()[1]

        try:
            # Request non-existent file
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"/missing.txt\r\n")
            await writer.drain()
            resp_missing = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()
            assert "File not found" in resp_missing

            # Path traversal attempt
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.write(b"/../secret.txt\r\n")
            await writer.drain()
            resp_traversal = (await reader.read()).decode("utf-8")
            writer.close()
            await writer.wait_closed()
            assert "Access denied" in resp_traversal

            # Immediate disconnect / empty
            reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()
