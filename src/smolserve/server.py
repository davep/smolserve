"""Main smolserve server orchestrator.

Manages the lifecycle of Gemini, Gopher, and Finger servers concurrently.
"""

import asyncio
import logging
import signal

from .config import Config
from .finger import FingerServer
from .gemini import GeminiServer
from .gopher import GopherServer

logger = logging.getLogger(__name__)


def create_sample_content(config: Config) -> None:
    """Create sample directory and file content if paths do not exist.

    Args:
        config: Server configuration containing target paths.
    """
    # Gemini sample content
    if config.gemini.enabled:
        gemini_root = config.gemini.root.expanduser().resolve()
        if not gemini_root.exists():
            gemini_root.mkdir(parents=True, exist_ok=True)
            sample_gmi = gemini_root / "index.gmi"
            sample_gmi.write_text(
                "# Welcome to smolserve Gemini Server!\n\n"
                "This is a sample Gemtext document served by smolserve.\n\n"
                "## Features\n"
                "* Simple Gemini protocol support\n"
                "* Automatic directory listings\n"
                "* Local testing environment\n",
                encoding="utf-8",
            )
            logger.info("Created sample Gemini root at %s", gemini_root)

    # Gopher sample content
    if config.gopher.enabled:
        gopher_root = config.gopher.root.expanduser().resolve()
        if not gopher_root.exists():
            gopher_root.mkdir(parents=True, exist_ok=True)
            sample_gophermap = gopher_root / "gophermap"
            sample_gophermap.write_text(
                "Welcome to smolserve Gopher Server!\n"
                "-----------------------------------\n\n"
                "0About smolserve\t/about.txt\t\t\n"
                "i\t\t\t\n"
                "iEnjoy exploring Gopher space!\t\t\t\n",
                encoding="utf-8",
            )
            about_file = gopher_root / "about.txt"
            about_file.write_text(
                "smolserve is a lightweight server for Gemini, Gopher, and Finger protocols.\n",
                encoding="utf-8",
            )
            logger.info("Created sample Gopher root at %s", gopher_root)

    # Finger sample content
    if config.finger.enabled:
        plan_file = config.finger.plan_file.expanduser().resolve()
        if not plan_file.exists():
            plan_file.parent.mkdir(parents=True, exist_ok=True)
            plan_file.write_text(
                "User Plan\n---------\nWorking on smolweb client & server testing!\n",
                encoding="utf-8",
            )
            logger.info("Created sample Finger plan file at %s", plan_file)


class SmolServe:
    """Orchestrator for multi-protocol servers."""

    def __init__(self, config: Config):
        """Initialize SmolServe.

        Args:
            config: Server configuration.
        """
        self.config = config
        self.servers: list[GeminiServer | GopherServer | FingerServer] = []
        self.ready_event = asyncio.Event()

    async def start(self) -> int:
        """Start all enabled protocol servers and run until stopped or child process exits.

        Returns:
            Exit code (0 for success, child process return code if exec_command was provided).
        """
        create_sample_content(self.config)

        if self.config.gemini.enabled:
            gem_server = GeminiServer(
                host=self.config.host,
                port=self.config.gemini.port,
                root=self.config.gemini.root,
                cert_file=self.config.gemini.cert_file,
                key_file=self.config.gemini.key_file,
            )
            self.servers.append(gem_server)

        if self.config.gopher.enabled:
            goph_server = GopherServer(
                host=self.config.host,
                port=self.config.gopher.port,
                root=self.config.gopher.root,
            )
            self.servers.append(goph_server)

        if self.config.finger.enabled:
            fing_server = FingerServer(
                host=self.config.host,
                port=self.config.finger.port,
                plan_file=self.config.finger.plan_file,
            )
            self.servers.append(fing_server)

        if not self.servers:
            logger.error("No protocol servers enabled! Exiting.")
            return 1

        # Start all servers
        for server in self.servers:
            await server.start()

        self.ready_event.set()

        if self.config.exec_command:
            cmd_str = " ".join(self.config.exec_command)
            logger.info("Executing child command: %s", cmd_str)

            proc = await asyncio.create_subprocess_exec(
                self.config.exec_command[0],
                *self.config.exec_command[1:],
            )

            loop = asyncio.get_running_loop()

            def _forward_signal(sig: int) -> None:
                logger.info(
                    "Signal received, forwarding to child process (PID %d)...", proc.pid
                )
                try:
                    proc.send_signal(sig)
                except ProcessLookupError:
                    pass

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, _forward_signal, sig)
                except NotImplementedError:
                    pass

            try:
                returncode = await proc.wait()
            except asyncio.CancelledError:
                try:
                    proc.terminate()
                    await proc.wait()
                except Exception:
                    pass
                returncode = 130
            finally:
                await self.stop()

            return returncode
        else:
            logger.info("smolserve is running. Press Ctrl+C to stop.")

            # Setup graceful shutdown handling
            loop = asyncio.get_running_loop()
            stop_event = asyncio.Event()

            def _signal_handler() -> None:
                logger.info("Shutdown signal received.")
                stop_event.set()

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, _signal_handler)
                except NotImplementedError:
                    # Windows support fallback
                    pass

            try:
                await stop_event.wait()
            except asyncio.CancelledError:
                pass
            finally:
                await self.stop()

            return 0

    async def stop(self) -> None:
        """Stop all running servers."""
        logger.info("Stopping all servers...")
        for server in self.servers:
            try:
                await server.stop()
            except Exception as exc:
                logger.error("Error stopping server: %s", exc)
        self.servers.clear()
        self.ready_event.clear()
        logger.info("All servers stopped.")
