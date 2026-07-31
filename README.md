# smolserve

A lightweight, multi-protocol server serving **Gemini**, **Gopher**, and **Finger** protocols for local testing and documentation.

## Features

- **Gemini Server**: Serves Gemtext documents (`.gmi`, `.gemini`) and static files over TLS. Auto-generates Gemtext directory listings when index files are absent. Auto-generates self-signed TLS certificates for development if none are provided.
- **Gopher Server**: Serves `gophermap` menus, directory listings, text files (with dot-stuffing), and binary files.
- **Finger Server**: Responds to Finger queries (RFC 1288) with contents of a plan file.
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

Run `smolserve` with defaults (binds to `127.0.0.1`, Gemini on port `1965`, Gopher on port `7070`, Finger on port `7979`):

```bash
uv run smolserve
```

If target directories or plan files do not exist, `smolserve` automatically creates sample content directories (`public_gemini/`, `public_gopher/`, `plan.txt`) and self-signed TLS dev certificates.

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
