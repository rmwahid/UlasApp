"""Sidecar entrypoint: bind 127.0.0.1 on a fixed or free port and print a handshake line.

The desktop shell spawns this process, reads the ENGINE_READY line to learn the port, and
monitors the process. Standalone development can pass --port explicitly.
"""

import argparse
import socket

import uvicorn


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the UlasApp engine")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    port = args.port if args.port is not None else free_port()
    print(f"ENGINE_READY port={port}", flush=True)
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
