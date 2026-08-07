"""Tests for smolserve configuration loading and CLI parsing."""

import tempfile
from pathlib import Path

from smolserve.config import Config, parse_args


def test_default_config() -> None:
    config = Config()
    assert config.host == "127.0.0.1"
    assert config.gemini.enabled is True
    assert config.gemini.port == 1965
    assert config.gopher.enabled is True
    assert config.gopher.port == 7070
    assert config.finger.enabled is True
    assert config.finger.port == 7979
    assert config.spartan.enabled is True
    assert config.spartan.port == 3000


def test_cli_argument_overrides() -> None:
    args = [
        "--host",
        "0.0.0.0",
        "--gemini-port",
        "1966",
        "--gopher-port",
        "7071",
        "--finger-port",
        "7980",
        "--no-finger",
        "--spartan-port",
        "3001",
        "--no-spartan",
    ]
    config = parse_args(args)
    assert config.host == "0.0.0.0"
    assert config.gemini.port == 1966
    assert config.gopher.port == 7071
    assert config.finger.port == 7980
    assert config.finger.enabled is False
    assert config.spartan.port == 3001
    assert config.spartan.enabled is False


def test_toml_config_loading() -> None:
    toml_content = """
[general]
host = "192.168.1.50"

[gemini]
enabled = false
port = 2965
root = "/tmp/gemini"

[gopher]
port = 7000
root = "/tmp/gopher"

[finger]
plan_file = "/tmp/my_plan.txt"

[spartan]
port = 3002
root = "/tmp/spartan"
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".toml", delete=False) as tf:
        tf.write(toml_content)
        tf_path = Path(tf.name)

    try:
        config = Config.from_toml(tf_path)
        assert config.host == "192.168.1.50"
        assert config.gemini.enabled is False
        assert config.gemini.port == 2965
        assert config.gemini.root == Path("/tmp/gemini")
        assert config.gopher.port == 7000
        assert config.gopher.root == Path("/tmp/gopher")
        assert config.finger.plan_file == Path("/tmp/my_plan.txt")
        assert config.spartan.port == 3002
        assert config.spartan.root == Path("/tmp/spartan")
    finally:
        tf_path.unlink()


def test_exec_parsing() -> None:
    # Test 'exec -- command args'
    config1 = parse_args(["--gemini-port", "1966", "exec", "--", "echo", "hello"])
    assert config1.gemini.port == 1966
    assert config1.exec_command == ["echo", "hello"]

    # Test 'exec command args' without '--'
    config2 = parse_args(["exec", "python", "-c", "print('hi')"])
    assert config2.exec_command == ["python", "-c", "print('hi')"]

    # Test '--exec command args'
    config3 = parse_args(["--exec", "ls", "-la"])
    assert config3.exec_command == ["ls", "-la"]
