# OpenAPI MCP Server

[![smithery badge](https://smithery.ai/badge/@rahgadda/openapi_mcp_server)](https://smithery.ai/server/@rahgadda/openapi_mcp_server)

## Overview
- This project will install `MCP - Model Context Protocol Server`, that provides configured REST API's as context to LLM's.
- Using this we can enable LLMs to interact with RestAPI's and perform REST API call's using LLM prompts.
- Currently we support HTTP API Call's `GET/PUT/POST/PATCH`.

## Installation
- Install package
  ```bash
  pip install openapi_mcp_server
  ```
- Create .env in a folder with minimum values for `OPENAPI_SPEC_PATH` & `API_BASE_URL`. Sample file available [here](https://raw.githubusercontent.com/rahgadda/openapi_mcp_server/refs/heads/main/.env)
- Test `openapi_mcp_server` server using `uv run openapi_mcp_server` from the above folder.

## Claud Desktop
- Configuration details for Claud Desktop
  ```json
  {
    "mcpServers": {
      "openapi_mcp_server":{
        "command": "uv",
        "args": ["run","openapi_mcp_server"]
        "env": {
            "DEBUG":"1",
            "API_BASE_URL":"https://petstore.swagger.io/v2",
            "OPENAPI_SPEC_PATH":"https://petstore.swagger.io/v2/swagger.json",
            "API_HEADERS":"Accept:application/json",
            "API_WHITE_LIST":"addPet,updatePet,findPetsByStatus"
        }
      }
    }
  }
  ```
  ![Pet Store Demo](https://github.com/rahgadda/openapi_mcp_server/blob/main/images/openapi_mcp_server_petstore_example.png?raw=true)

### Configuration
- List of available environment variables
  - `DEBUG`: Enable debug logging (optional default is False)
  - `OPENAPI_SPEC_PATH`: Path to the OpenAPI document. (required)
  - `API_BASE_URL`: Base URL for the API requests. (required)
  - `API_HEADERS`: Headers to include in the API requests (optional)
  - `API_WHITE_LIST`: White Listed operationId in list format ["operationId1", "operationId2"] (optional)
  - `API_BLACK_LIST`: Black Listed operationId in list format ["operationId3", "operationId4"] (optional)
  - `HTTP_PROXY`: HTTP Proxy details (optional)
  - `HTTPS_PROXY`: HTTPS Proxy details (optional)
  - `NO_PROXY`: No Proxy details (optional)

## Contributing
Contributions are welcome.    
Please feel free to submit a Pull Request.

## License
This project is licensed under the terms of the MIT license.

## Github Stars
[![Star History Chart](https://api.star-history.com/svg?repos=rahgadda/openapi_mcp_server=Date)](https://star-history.com/#rahgadda/openapi_mcp_server&Date)

## Appendix
### UV
```bash
mkdir -m777 openapi_mcp_server
cd openapi_mcp_server
uv init
uv add mcp[cli] pydantic python-dotenv requests
uv add --dev twine setuptools
uv sync
uv run openapi_mcp_server
uv build
pip install --force-reinstall --no-deps .\dist\openapi_mcp_server-*fileversion*.whl
export TWINE_USERNAME="rahgadda"
export TWINE_USERNAME="<<API Key>>"
uv run twine upload --verbose dist/*
```

## Reference
- [UV Overview](https://www.youtube.com/watch?v=WKc2BdgmGZE)