#!/usr/bin/env python3
"""
Context Layer MCP Server - Direct runner
Run with: python run_mcp.py
"""

import subprocess
import sys

def main():
    # Keep stdout reserved for MCP JSON-RPC when this is launched by a client.
    print("Starting Context Layer MCP Server...", file=sys.stderr)
    print("Install dependencies first with: python -m pip install -r requirements.txt",
          file=sys.stderr)
    try:
        return subprocess.call([sys.executable, "start_mcp.py"])
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
