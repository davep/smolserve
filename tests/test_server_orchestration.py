"""Integration tests for SmolServe orchestrator and CLI features."""

from pathlib import Path
import asyncio
import tempfile
import pytest

from smolserve.config import Config, parse_args
from smolserve.server import SmolServe, create_sample_content


def test_create_sample_content():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        config = Config()
        config.gemini.root = base / "gemini"
        config.gopher.root = base / "gopher"
        config.finger.plan_file = base / "finger" / "plan.txt"

        create_sample_content(config)

        assert (base / "gemini" / "index.gmi").is_file()
        assert (base / "gopher" / "gophermap").is_file()
        assert (base / "gopher" / "about.txt").is_file()
        assert (base / "finger" / "plan.txt").is_file()


def test_generate_config_option(capsys):
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--generate-config"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[general]" in captured.out
    assert "[gemini]" in captured.out
    assert "[gopher]" in captured.out
    assert "[finger]" in captured.out


@pytest.mark.asyncio
async def test_smolserve_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        config = Config()
        config.gemini.port = 0
        config.gopher.port = 0
        config.finger.port = 0
        config.gemini.root = base / "gemini"
        config.gopher.root = base / "gopher"
        config.finger.plan_file = base / "finger" / "plan.txt"

        smol = SmolServe(config)

        # Start servers in background task
        task = asyncio.create_task(smol.start())
        # Give servers a moment to bind
        await asyncio.sleep(0.1)

        assert len(smol.servers) == 3
        for s in smol.servers:
            assert s.server is not None
            assert s.server.is_serving()

        # Stop servers
        await smol.stop()
        task.cancel()
