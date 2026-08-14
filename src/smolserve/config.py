"""Configuration management for smolserve.

Parses command-line arguments and optional TOML configuration files, merging
settings with appropriate defaults.
"""

import argparse
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GeminiConfig:
    """Gemini server settings."""

    enabled: bool = True
    port: int = 1965
    root: Path = field(default_factory=lambda: Path("./public_gemini"))
    cert_file: Path | None = None
    key_file: Path | None = None


@dataclass
class GopherConfig:
    """Gopher server settings."""

    enabled: bool = True
    port: int = 7070
    root: Path = field(default_factory=lambda: Path("./public_gopher"))


@dataclass
class FingerConfig:
    """Finger server settings."""

    enabled: bool = True
    port: int = 7979
    plan_file: Path = field(default_factory=lambda: Path("./plan.txt"))


@dataclass
class SpartanConfig:
    """Spartan server settings."""

    enabled: bool = True
    port: int = 3000
    root: Path = field(default_factory=lambda: Path("./public_spartan"))


@dataclass
class NexConfig:
    """Nex server settings."""

    enabled: bool = True
    port: int = 1900
    root: Path = field(default_factory=lambda: Path("./public_nex"))


@dataclass
class Config:
    """Root configuration for smolserve."""

    host: str = "127.0.0.1"
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    gopher: GopherConfig = field(default_factory=GopherConfig)
    finger: FingerConfig = field(default_factory=FingerConfig)
    spartan: SpartanConfig = field(default_factory=SpartanConfig)
    nex: NexConfig = field(default_factory=NexConfig)
    exec_command: list[str] | None = None
    verbose: bool = False
    quiet: bool = False

    @classmethod
    def from_toml(cls, path: Path) -> "Config":
        """Load configuration from a TOML file.

        Args:
            path: Path to the TOML configuration file.

        Returns:
            Config instance populated with TOML values.
        """
        with open(path, "rb") as f:
            data = tomllib.load(f)

        config = cls()

        if "general" in data:
            gen = data["general"]
            if "host" in gen:
                config.host = str(gen["host"])
            config.verbose = gen.get("verbose", config.verbose)
            config.quiet = gen.get("quiet", config.quiet)

        if "gemini" in data:
            gem = data["gemini"]
            config.gemini.enabled = gem.get("enabled", config.gemini.enabled)
            config.gemini.port = gem.get("port", config.gemini.port)
            if "root" in gem:
                config.gemini.root = Path(gem["root"])
            if "cert_file" in gem and gem["cert_file"]:
                config.gemini.cert_file = Path(gem["cert_file"])
            if "key_file" in gem and gem["key_file"]:
                config.gemini.key_file = Path(gem["key_file"])

        if "gopher" in data:
            goph = data["gopher"]
            config.gopher.enabled = goph.get("enabled", config.gopher.enabled)
            config.gopher.port = goph.get("port", config.gopher.port)
            if "root" in goph:
                config.gopher.root = Path(goph["root"])

        if "finger" in data:
            fing = data["finger"]
            config.finger.enabled = fing.get("enabled", config.finger.enabled)
            config.finger.port = fing.get("port", config.finger.port)
            if "plan_file" in fing:
                config.finger.plan_file = Path(fing["plan_file"])

        if "spartan" in data:
            spart = data["spartan"]
            config.spartan.enabled = spart.get("enabled", config.spartan.enabled)
            config.spartan.port = spart.get("port", config.spartan.port)
            if "root" in spart:
                config.spartan.root = Path(spart["root"])

        if "nex" in data:
            nx = data["nex"]
            config.nex.enabled = nx.get("enabled", config.nex.enabled)
            config.nex.port = nx.get("port", config.nex.port)
            if "root" in nx:
                config.nex.root = Path(nx["root"])

        return config


SAMPLE_TOML_CONFIG = """# smolserve sample configuration

[general]
host = "127.0.0.1"

[gemini]
enabled = true
port = 1965
root = "./public_gemini"
# cert_file = "./cert.pem"
# key_file = "./key.pem"

[gopher]
enabled = true
port = 7070
root = "./public_gopher"

[finger]
enabled = true
port = 7979
plan_file = "./plan.txt"

[spartan]
enabled = true
port = 3000
root = "./public_spartan"

[nex]
enabled = true
port = 1900
root = "./public_nex"
"""


def parse_args(args: list[str] | None = None) -> Config:
    """Parse command line arguments and merge with TOML config if specified.

    Args:
        args: List of command line arguments (defaults to sys.argv[1:]).

    Returns:
        Combined Config instance.
    """
    if args is None:
        args = sys.argv[1:]

    exec_cmd: list[str] | None = None
    server_args = list(args)

    # Check for 'exec' subcommand or '--exec' option
    if "exec" in server_args:
        exec_idx = server_args.index("exec")
        if "--" in server_args[exec_idx + 1 :]:
            dash_idx = server_args.index("--", exec_idx + 1)
            exec_cmd = server_args[dash_idx + 1 :]
            server_args = server_args[:exec_idx] + server_args[exec_idx + 1 : dash_idx]
        else:
            exec_cmd = server_args[exec_idx + 1 :]
            server_args = server_args[:exec_idx]
    elif "--exec" in server_args:
        exec_idx = server_args.index("--exec")
        if "--" in server_args[exec_idx + 1 :]:
            dash_idx = server_args.index("--", exec_idx + 1)
            exec_cmd = server_args[dash_idx + 1 :]
            server_args = server_args[:exec_idx] + server_args[exec_idx + 1 : dash_idx]
        else:
            exec_cmd = server_args[exec_idx + 1 :]
            server_args = server_args[:exec_idx]

    parser = argparse.ArgumentParser(
        description="smolserve - A lightweight Gemini, Gopher, Finger, Spartan, and Nex server."
    )

    exec_group = parser.add_argument_group("execution mode")
    exec_group.add_argument(
        "exec_help",
        nargs="*",
        metavar="[exec | --exec] [-- COMMAND [ARGS...]]",
        help="Run smolserve in the background for the duration of COMMAND and stop when finished.",
    )

    parser.add_argument(
        "-c", "--config", type=Path, help="Path to TOML configuration file."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging output."
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Silence informational output (errors only).",
    )
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Print a sample TOML configuration and exit.",
    )
    parser.add_argument("--host", type=str, help="Host address to bind servers to.")

    # Gemini flags
    parser.add_argument("--gemini-port", type=int, help="Gemini server port.")
    parser.add_argument("--gemini-root", type=Path, help="Gemini root directory.")
    parser.add_argument("--gemini-cert", type=Path, help="Gemini TLS certificate file.")
    parser.add_argument("--gemini-key", type=Path, help="Gemini TLS private key file.")
    parser.add_argument(
        "--no-gemini", action="store_true", help="Disable Gemini server."
    )

    # Gopher flags
    parser.add_argument("--gopher-port", type=int, help="Gopher server port.")
    parser.add_argument("--gopher-root", type=Path, help="Gopher root directory.")
    parser.add_argument(
        "--no-gopher", action="store_true", help="Disable Gopher server."
    )

    # Finger flags
    parser.add_argument("--finger-port", type=int, help="Finger server port.")
    parser.add_argument("--finger-plan", type=Path, help="Finger plan file path.")
    parser.add_argument(
        "--no-finger", action="store_true", help="Disable Finger server."
    )

    # Spartan flags
    parser.add_argument("--spartan-port", type=int, help="Spartan server port.")
    parser.add_argument("--spartan-root", type=Path, help="Spartan root directory.")
    parser.add_argument(
        "--no-spartan", action="store_true", help="Disable Spartan server."
    )

    # Nex flags
    parser.add_argument("--nex-port", type=int, help="Nex server port.")
    parser.add_argument("--nex-root", type=Path, help="Nex root directory.")
    parser.add_argument("--no-nex", action="store_true", help="Disable Nex server.")

    parsed = parser.parse_args(server_args)

    if parsed.generate_config:
        sys.stdout.write(SAMPLE_TOML_CONFIG)
        sys.exit(0)

    # Start with default config or load from TOML if specified
    config = Config.from_toml(parsed.config) if parsed.config else Config()

    config.exec_command = exec_cmd if exec_cmd else None

    # CLI overrides
    if parsed.verbose:
        config.verbose = True
    if parsed.quiet:
        config.quiet = True
    if parsed.host is not None:
        config.host = parsed.host

    # Gemini overrides
    if parsed.no_gemini:
        config.gemini.enabled = False
    if parsed.gemini_port is not None:
        config.gemini.port = parsed.gemini_port
    if parsed.gemini_root is not None:
        config.gemini.root = parsed.gemini_root
    if parsed.gemini_cert is not None:
        config.gemini.cert_file = parsed.gemini_cert
    if parsed.gemini_key is not None:
        config.gemini.key_file = parsed.gemini_key

    # Gopher overrides
    if parsed.no_gopher:
        config.gopher.enabled = False
    if parsed.gopher_port is not None:
        config.gopher.port = parsed.gopher_port
    if parsed.gopher_root is not None:
        config.gopher.root = parsed.gopher_root

    # Finger overrides
    if parsed.no_finger:
        config.finger.enabled = False
    if parsed.finger_port is not None:
        config.finger.port = parsed.finger_port
    if parsed.finger_plan is not None:
        config.finger.plan_file = parsed.finger_plan

    # Spartan overrides
    if parsed.no_spartan:
        config.spartan.enabled = False
    if parsed.spartan_port is not None:
        config.spartan.port = parsed.spartan_port
    if parsed.spartan_root is not None:
        config.spartan.root = parsed.spartan_root

    # Nex overrides
    if parsed.no_nex:
        config.nex.enabled = False
    if parsed.nex_port is not None:
        config.nex.port = parsed.nex_port
    if parsed.nex_root is not None:
        config.nex.root = parsed.nex_root

    return config
