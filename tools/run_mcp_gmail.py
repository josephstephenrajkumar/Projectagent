import sys
import os

try:
    from mcp_gmail.server import mcp
    mcp.run()
except Exception as e:
    print(f"Failed to run mcp_gmail server: {e}", file=sys.stderr)
    sys.exit(1)
