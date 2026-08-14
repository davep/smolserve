# smolserve

A lightweight, multi-protocol server serving **Gemini**, **Gopher**, **Finger**, **Spartan**, and **Nex** protocols for local testing and documentation.

> [!important]
> Not to be confused with [SmolServ](https://git.nil.im/js/SmolServ)
> (no`e`), which is a genuine Gemini and HTTP server for the smol web.

## Features

- **Gemini Server**: Serves Gemtext documents (`.gmi`, `.gemini`) and static files over TLS. Auto-generates Gemtext directory listings when index files are absent. Auto-generates self-signed TLS certificates for development if none are provided.
- **Gopher Server**: Serves `gophermap` menus, directory listings, text files (with dot-stuffing), and binary files.
- **Finger Server**: Responds to Finger queries (RFC 1288) with contents of a plan file.
- **Spartan Server**: Serves Gemtext documents (`.gmi`, `.gemini`), static files, and directory listings over TCP. Supports file upload blocks.
- **Nex Server**: Serves documents, static files, and plain text directory listings with `=> ` links over TCP.
- **Flexible Configuration**: Configurable via command-line arguments or a TOML configuration file.
- **AsyncIO Powered**: Lightweight, single-process asynchronous server implementation.

---

## Installation & Setup

`smolserve` is managed using [`uv`](https://github.com/astral-sh/uv).

```bash
uv sync
```

---

## Usage

### Quick Start

Run `smolserve` with defaults (binds to `127.0.0.1`, Gemini on port `1965`, Gopher on port `7070`, Finger on port `7979`, Spartan on port `3000`, Nex on port `1900`):

```bash
uv run smolserve
```

If target directories or plan files do not exist, `smolserve` automatically creates sample content directories (`public_gemini/`, `public_gopher/`, `public_spartan/`, `public_nex/`, `plan.txt`) and self-signed TLS dev certificates.

---

### Exec / Command Wrapper Mode

`smolserve` includes a built-in process wrapper mode (`exec`), allowing you to temporarily run the Gemini, Gopher, Finger, Spartan, and Nex servers for the lifespan of an arbitrary command (such as static documentation site generation, live dev servers, or automated test runs).

#### How It Works

1. **Server Initialization**: `smolserve` starts and binds all configured protocol servers.
2. **Process Execution**: Once servers are running, `smolserve` launches the specified child command.
3. **Signal Forwarding**: Signals such as `SIGINT` (`Ctrl+C`) and `SIGTERM` are trapped and forwarded directly to the child process.
4. **Automatic Cleanup & Exit Propagation**: When the child process completes, `smolserve` gracefully stops all background servers and exits with the exact exit code returned by the child process (or exit code `130` on cancellation).

#### Command Syntax

You can specify the subcommand using `exec --`, `exec`, or `--exec`:

```bash
# Recommended POSIX standard syntax (using '--' separator)
uv run smolserve exec -- <command> [args...]

# Direct syntax without '--'
uv run smolserve exec <command> [args...]

# Flag syntax
uv run smolserve --exec <command> [args...]
```

#### Passing Server Options

`smolserve` flags and configuration options should be placed **before** the `exec` subcommand:

```bash
# Custom configuration file with exec
uv run smolserve -c smolserve.toml exec -- mkdocs build

# Custom host and port flags with exec
uv run smolserve --host 0.0.0.0 --gemini-port 1966 exec -- pytest
```

#### Use Cases & Examples

- **Build Pipelines**: Ensure background protocol servers are available while building documentation or static sites.
  ```bash
  uv run smolserve exec -- mkdocs build
  ```

- **Live Development Servers**: Run interactive documentation servers with live reload while `smolserve` serves required content.
  ```bash
  uv run smolserve exec -- mkdocs serve --livereload
  ```

- **Integration Testing**: Automatically spin up servers, run integration test suites or test clients, and shut down cleanly.
  ```bash
  uv run smolserve exec -- pytest tests/
  ```

- **Makefile Integration**:
  ```makefile
  .PHONY: docs
  docs:
  	uv run smolserve exec -- $(mkdocs) build

  .PHONY: rtfm
  rtfm:
  	uv run smolserve exec -- $(mkdocs) serve --livereload
  ```

---

### Command Line Options

```bash
uv run smolserve --help
```

Available flags:

- `-c`, `--config`: Path to TOML configuration file.
- `--generate-config`: Print sample TOML configuration to stdout and exit.
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
- `--nex-port`: Nex server port.
- `--nex-root`: Directory containing Nex content.
- `--no-nex`: Disable Nex server.

---

### TOML Configuration

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

[nex]
enabled = true
port = 1900
root = "./public_nex"
```

To generate a sample configuration file:

```bash
uv run smolserve --generate-config > smolserve.toml
```

---

## Running Tests

Run the test suite using `pytest`:

```bash
uv run pytest
```
