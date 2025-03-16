#!/bin/bash
echo "Installing locally built wheel..."
WHEEL_FILE=$(ls dist/openapi_mcp_server-*.whl | head -1)
if [ -n "$WHEEL_FILE" ]; then
    echo "Found wheel: $WHEEL_FILE"
    pip install --force-reinstall --no-deps "$WHEEL_FILE"
    echo "Installation complete. You can now use openapi_mcp_server in any terminal."
else
    echo "No wheel file found! Make sure to build the package first."
    exit 1
fi
