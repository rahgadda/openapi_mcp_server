@echo off
echo Installing locally built wheel...
for %%F in (dist\openapi_mcp_server-*.whl) do (
    echo Found wheel: %%F
    pip install --force-reinstall --no-deps %%F
)
echo Installation complete. You can now use openapi_mcp_server in any terminal.
