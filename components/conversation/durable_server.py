#!/usr/bin/env python3
"""Opt-in v2 JSON-lines endpoint. Existing fresh_server.py remains v1."""
from fresh_server import main

if __name__ == '__main__':
    raise SystemExit(main(api_version=2))
