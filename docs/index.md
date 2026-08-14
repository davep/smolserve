# smolserve

A lightweight, multi-protocol server serving **Gemini**, **Gopher**, **Finger**, and **Spartan** protocols for local testing, development, and documentation.

!!! important

    Not to be confused with [SmolServ](https://git.nil.im/js/SmolServ) (no`e`), which is a genuine Gemini and HTTP server for the smol web.

## Features

- **Gemini Server**: Serves Gemtext documents (`.gmi`, `.gemini`) and static files over TLS. Auto-generates Gemtext directory listings when index files are absent and auto-generates self-signed TLS certificates for local development if none are provided.
- **Gopher Server**: Serves `gophermap` menus, directory listings, text files (with dot-stuffing), and binary files.
- **Finger Server**: Responds to Finger queries (RFC 1288) with the contents of a plan file.
- **Spartan Server**: Serves Gemtext documents (`.gmi`, `.gemini`), static files, and directory listings over TCP. Supports file upload blocks.
- **Exec Process Wrapper**: Run `smolserve` in the background for the duration of an arbitrary command (such as `mkdocs build`, `pytest`, or `mkdocs serve`).
- **Flexible Configuration**: Fully configurable via command-line arguments or a TOML configuration file.
- **AsyncIO Powered**: Lightweight, single-process asynchronous server implementation.

---

## Installing

`smolserve` is a Python application and is distributed via PyPI. It can be installed using tools such as [pipx](https://pipx.pypa.io/stable/):

```bash
pipx install smolserve
```

or [`uv`](https://docs.astral.sh/uv/):

```bash
uv tool install smolserve
```

If you have `uv` installed, you can also run `smolserve` directly using [`uvx`](https://docs.astral.sh/uv/guides/tools/):

```bash
uvx smolserve
```

### Development Installation

If you are developing or contributing to `smolserve`, clone the repository and sync dependencies using `uv`:

```bash
git clone https://github.com/davep/smolserve.git
cd smolserve
uv sync
```

---

## Quick Start

Run `smolserve` with defaults (binds to `127.0.0.1`, Gemini on port `1965`, Gopher on port `7070`, Finger on port `7979`, Spartan on port `3000`):

```bash
smolserve
```

or with `uv`:

```bash
uv run smolserve
```

If target directories or plan files do not exist, `smolserve` automatically creates sample content directories (`public_gemini/`, `public_gopher/`, `public_spartan/`, `plan.txt`) and self-signed TLS development certificates.

---

## Exec / Command Wrapper Mode

`smolserve` includes a built-in process wrapper mode (`exec`), allowing you to temporarily run the Gemini, Gopher, Finger, and Spartan servers for the lifespan of an arbitrary command (such as static documentation site generation, live dev servers, or automated test runs).

### How It Works

1. **Server Initialization**: `smolserve` starts and binds all configured protocol servers.
2. **Process Execution**: Once servers are running, `smolserve` launches the specified child command.
3. **Signal Forwarding**: Signals such as `SIGINT` (`Ctrl+C`) and `SIGTERM` are trapped and forwarded directly to the child process.
4. **Automatic Cleanup & Exit Propagation**: When the child process completes, `smolserve` gracefully stops all background servers and exits with the exact exit code returned by the child process (or exit code `130` on cancellation).

### Command Syntax

You can specify the subcommand using `exec --`, `exec`, or `--exec`:

```bash
# Recommended POSIX standard syntax (using '--' separator)
smolserve exec -- <command> [args...]

# Direct syntax without '--'
smolserve exec <command> [args...]

# Flag syntax
smolserve --exec <command> [args...]
```

### Passing Server Options

`smolserve` flags and configuration options should be placed **before** the `exec` subcommand:

```bash
# Custom configuration file with exec
smolserve -c smolserve.toml exec -- mkdocs build

# Custom host and port flags with exec
smolserve --host 0.0.0.0 --gemini-port 1966 exec -- pytest
```

### Use Cases & Examples

- **Build Pipelines**: Ensure background protocol servers are available while building documentation or static sites.
  ```bash
  smolserve exec -- mkdocs build
  ```

- **Live Development Servers**: Run interactive documentation servers with live reload while `smolserve` serves required content.
  ```bash
  smolserve exec -- mkdocs serve --livereload
  ```

- **Integration Testing**: Automatically spin up servers, run integration test suites or test clients, and shut down cleanly.
  ```bash
  smolserve exec -- pytest tests/
  ```

- **Makefile Integration**:
  ```makefile
  .PHONY: docs
  docs:
  	smolserve exec -- $(mkdocs) build

  .PHONY: rtfm
  rtfm:
  	smolserve exec -- $(mkdocs) serve --livereload
  ```

---

## Command Line Options

Run `smolserve --help` to display all available options:

```bash
smolserve --help
```

Available flags:

- `-c`, `--config`: Path to TOML configuration file.
- `--generate-config`: Print sample TOML configuration to stdout and exit.
- `-v`, `--verbose`: Enable verbose logging output.
- `-q`, `--quiet`: Silence informational output (errors only).
- `--host`: Host address to bind servers to (e.g. `127.0.0.1` or `0.0.0.0`).
- `--gemini-port`: Gemini server port.
- `--gemini-root`: Directory containing Gemtext/static content.
- `--gemini-cert`: Path to custom TLS PEM certificate.
- `--gemini-key`: Path to custom TLS PEM private key.
- `--no-gemini`: Disable Gemini server.
- `--gopher-port`: Gopher server port.
- `--gopher-root`: Directory containing Gopher content / gophermaps.
- `--no-gopher`: Disable Gopher server.
- `--finger-port`: Finger server port.
- `--finger-plan`: Path to Finger plan file.
- `--no-finger`: Disable Finger server.
- `--spartan-port`: Spartan server port.
- `--spartan-root`: Directory containing Spartan content.
- `--no-spartan`: Disable Spartan server.

---

## TOML Configuration

You can pass a TOML configuration file via `-c` / `--config`:

```toml
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
```

To generate a sample configuration file:

```bash
smolserve --generate-config > smolserve.toml
```

---

## Development and Testing

Run the test suite using `pytest` or `make`:

```bash
uv run pytest
```

or run the full suite of linting, type checks, and tests:

```bash
make checkall
```
