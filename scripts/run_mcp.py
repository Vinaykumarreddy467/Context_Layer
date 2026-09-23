#!/usr/bin/env python3
"""
Context Layer MCP Server - Direct runner
Run with: python run_mcp.py
"""

import subprocess
import sys

def main():
    print("Starting Context Layer MCP Server...")
    print("Database and API configuration will be loaded from the project .env file.")
    
    # Install dependencies
    print("Installing dependencies...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    if result.returncode != 0:
        print("Failed to install dependencies")
        return 1
    
    print()
    print("Starting MCP server (stdio mode)...")
    print("This window must stay open for the MCP to work.")
    print("Press Ctrl+C to stop.")
    print()
    
    # Run the MCP server
    try:
        subprocess.run([sys.executable, "mcp_server.py"], check=True)
    except KeyboardInterrupt:
        print("\nStopped.")
    except subprocess.CalledProcessError as e:
        print(f"MCP server exited with error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
