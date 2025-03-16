import os
import sys
from requests import request
import json
import argparse

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, create_model, Field

from dotenv import load_dotenv
from openapi_mcp_server.utils import setup_logging, load_swagger_spec, extract_api_metadata
from mcp.server.fastmcp import FastMCP

# Global variables
HTTP_PROXY = None
HTTPS_PROXY = None
NO_PROXY = None
OPENAPI_SPEC_PATH = None
API_BASE_URL = None
API_HEADERS = None
API_WHITE_LIST = None
API_BLACK_LIST = None

# Logger
logger = None

# Debug flag
DEBUG = os.getenv("DEBUG", "TRUE").lower() in ("true", "1", "yes")

# FastMCP server
mcp = FastMCP("openapi_mcp_server")

# Pydantic model cache and mapping
model_cache = {}
model_mapping = {}

def log_configuration_setup():
    """
    Setup logging configuration

    Args:
        None
    
    Returns:
        None    
    """
    
    global logger, DEBUG
    
    try:
        logger = setup_logging(debug=DEBUG)
    except Exception as e:
        print(f"ERROR: Failed to configure logging: {e}")
        sys.exit(1)

def load_environment_variables(env_path: str = None):
    """
    Load environment variables

    Args:
        env_path (str): Path to the .env file
    
    Returns:
        None
    """
    global HTTP_PROXY, HTTPS_PROXY, NO_PROXY, OPENAPI_SPEC_PATH, API_BASE_URL, API_HEADERS, API_WHITE_LIST, API_BLACK_LIST, logger, DEBUG
    
    # Processing CLI input arguments
    parser = argparse.ArgumentParser(
        description="OpenAPI MCP Server CLI v0.3.0",
        prog="openapi_mcp_server"
    )
    parser.add_argument(
        "--env",
        help="Path to .env file to load environment variables from",
        default=None
    )
    args = parser.parse_args()
    
    # Load environment variables
    env_path = args.env if args.env else os.path.join(os.getcwd(), ".env")
    
    # Processing .env file
    try:
        if env_path and os.path.exists(env_path):
            load_dotenv(env_path)
            logger.debug(f"Environment variables loaded from: {env_path}")
        else:
            logger.debug("No .env file specified or file does not exist")

        # Updating logging level from environment variable
        DEBUG = os.getenv("DEBUG", "FALSE").lower() in ("true", "1", "yes")
        logger = setup_logging(debug=DEBUG)
        logger.debug("DEBUG: %s", DEBUG)

        # Configure proxy settings from environment variables
        HTTP_PROXY = os.getenv("HTTP_PROXY")
        HTTPS_PROXY = os.getenv("HTTPS_PROXY")
        NO_PROXY = os.getenv("NO_PROXY")

        # Apply proxy settings to the environment if they exist
        if HTTP_PROXY:
            os.environ["HTTP_PROXY"] = HTTP_PROXY
            logger.debug(f"HTTP proxy set: {HTTP_PROXY}")
        if HTTPS_PROXY:
            os.environ["HTTPS_PROXY"] = HTTPS_PROXY
            logger.debug(f"HTTPS proxy set: {HTTPS_PROXY}")
        if NO_PROXY:
            os.environ["NO_PROXY"] = NO_PROXY
            logger.debug(f"No proxy domains: {NO_PROXY}")

        # Updating OpenAPI spec path from environment variable
        if not os.getenv("OPENAPI_SPEC_PATH"):
            logger.error("OPENAPI_SPEC_PATH environment variable is not set")
            sys.exit(1)
        else:
            OPENAPI_SPEC_PATH = os.getenv("OPENAPI_SPEC_PATH")
            logger.debug("OPENAPI_SPEC_PATH: %s", OPENAPI_SPEC_PATH)
        
        # Updating API base URL from environment variable
        if not os.getenv("API_BASE_URL"):
            logger.error("API_BASE_URL environment variable is not set")
            sys.exit(1)
        else:
            API_BASE_URL = os.getenv("API_BASE_URL")
            logger.debug("API_BASE_URL: %s", API_BASE_URL)

        # Updating API headers from environment variable
        API_HEADERS = os.getenv("API_HEADERS")
        logger.debug("API_HEADERS: %s", API_HEADERS)

        # Updating API white/black list from environment variable
        API_WHITE_LIST = os.getenv("API_WHITE_LIST")
        logger.debug("API_WHITE_LIST: %s", API_WHITE_LIST)

        API_BLACK_LIST = os.getenv("API_BLACK_LIST")
        logger.debug("API_BLACK_LIST: %s", API_BLACK_LIST)
    
    except Exception as e:
        logger.error(f"Error loading environment variables: {str(e)}")
        sys.exit(1)

def get_py_type(json_type):
    """
    Convert JSON schema types to Python/Pydantic types
    
    Args:
        json_type (str): JSON/Swagger schema type
    
    Returns:
        Any: Python/Pydantic type
    """
    type_map = {
        'integer': int,
        'number': float,
        'string': Any,
        'boolean': bool,
        'array': List,
        'object': Dict[str, Any]
    }
    return type_map.get(json_type, Any)

def get_param_type(param):
    """
    Get the Python type of the parameter

    Args:
        param (dict): Parameter schema
    
    Returns:
        str: Python type of the parameter
    """

    if 'schema' in param:
        json_type = param['schema'].get('type', 'string')
    elif 'type' in param:
        json_type = param.get('type', 'string')
    else:
        json_type = 'string'  # default to string if type info is missing
    
    # Convert to Python type and get its name
    return get_py_type(json_type).__name__ 

def create_pydantic_model_from_json(json_obj, model_name):
    """
    Create a Pydantic model from a JSON object

    Args:
        json_obj (dict): JSON object representing the model
        model_name (str): Name of the Pydantic model
    
    Returns:
        Pydantic model: Pydantic model representing the JSON object
    """
    
    try:
        # Check if model already exists in cache
        if model_name in model_cache:
            return model_cache[model_name]
        
        # Create a Pydantic model from the JSON object
        logger.debug(f"Generating Pydantic model: {model_name}")
        
        if not isinstance(json_obj, dict):
            logger.error(f"Invalid JSON object for model {model_name}: expected dict, got {type(json_obj)}")
            return BaseModel  # Return base model as fallback
        
        fields = {}
        nested_models = []

        # Iterate over the JSON object and create fields
        for field_name, field_value in json_obj.items():
            try:
                if isinstance(field_value, dict):
                    # Create nested model
                    nested_model_name = f"{model_name}{field_name.capitalize()}"
                    nested_model = create_pydantic_model_from_json(field_value, nested_model_name)
                    fields[field_name] = (Optional[nested_model], field_value)
                    nested_models.append(nested_model)
                elif isinstance(field_value, list) and field_value and isinstance(field_value[0], dict):
                    # Create nested model for array items
                    nested_model_name = f"{model_name}{field_name.capitalize()}Item"
                    nested_model = create_pydantic_model_from_json(field_value[0], nested_model_name)
                    fields[field_name] = (List[nested_model], [])
                    nested_models.append(nested_model)
                else:
                    # Determine type from example value
                    py_type = type(field_value)
                    if py_type is str:
                        fields[field_name] = (Optional[str], field_value)
                    elif py_type is int:
                        fields[field_name] = (Optional[int], field_value)
                    elif py_type is float:
                        fields[field_name] = (Optional[float], field_value)
                    elif py_type is bool:
                        fields[field_name] = (Optional[bool], field_value)
                    elif py_type is list:
                        fields[field_name] = (List[str], [])
                    else:
                        fields[field_name] = (Any, field_value)
            except Exception as e:
                logger.error(f"Error processing field '{field_name}' for model {model_name}: {str(e)}")
                fields[field_name] = (Any, None)  # Use Any type as fallback

        try:
            # Create the Pydantic model
            model = create_model(model_name, **fields)
            model_cache[model_name] = model

            # Add nested models to the model mapping
            for nested_model in nested_models:
                globals()[nested_model.__name__] = nested_model

            # Make model available in global scope
            globals()[model_name] = model

            logger.debug(f"Generated Pydantic model: {model_name}")
            logger.debug(model.model_json_schema())

            return model
        except Exception as e:
            logger.error(f"Failed to create Pydantic model {model_name}: {str(e)}")
            return BaseModel  # Return base model as fallback
    except Exception as e:
        logger.error(f"Unexpected error creating model {model_name}: {str(e)}")
        return BaseModel  # Return base model as fallback

def create_dynamic_tools() -> str:
    """
    Create dynamic tools for the FastMCP server
    
    Args:
        None
    
    Returns:
        str: Python function representing dynamic tools 
    """

    logger.info("Loading Tools From Swagger Spec")

    # Load the OpenAPI spec
    try:
        logger.debug(f"Loading OpenAPI Spec from: {OPENAPI_SPEC_PATH}")
        if os.path.exists(OPENAPI_SPEC_PATH):
            with open(OPENAPI_SPEC_PATH, "r") as file:
                openapi_spec = file.read()
        else:
            openapi_spec = request('GET',OPENAPI_SPEC_PATH).text
    except Exception as e:
        logger.error(f"Error loading OpenAPI Spec: {e}")
        sys.exit(1)

    # Convert openapi_spec to json
    try:
        openapi_spec_json = json.loads(openapi_spec)
    except Exception as e:
        logger.error(f"Error parsing OpenAPI Spec: {e}")
        sys.exit(1)

    # Extract API metadata
    try:
        version = load_swagger_spec(openapi_spec_json)
        metadata = extract_api_metadata(API_WHITE_LIST, API_BLACK_LIST, openapi_spec_json, version)
    except Exception as e:
        logger.error(f"Error processing OpenAPI Spec Metadata: {e}")
        sys.exit(1)

    # Create Pydantic models for request objects
    try:
        for endpoint in metadata:
            if endpoint['request_body'] is not None:
                model_name = f"{endpoint['operationId'].capitalize()}Request"
                model = create_pydantic_model_from_json(endpoint['request_body'], model_name)
                model_mapping[endpoint['operationId']] = model_name
    except Exception as e:
        logger.error(f"Error creating Pydantic models: {e}")
        sys.exit(1)

    # Create dynamic tools
    for endpoint in metadata:
        try:
            func_name = endpoint['operationId']
            path = endpoint['path']
            method = endpoint['method'].upper()
            
            logger.debug(f"Generating function for endpoint: {func_name} ({method} {path})")
            
            # Parameter collections
            parameters = []
            doc_parameters = []
            
            # Path parameters
            for p in endpoint['path_parameters']:
                param_name = p['name']
                param_type = get_param_type(p)
                parameters.append(f"{param_name}: {param_type}")
                
                p_description = p.get('description', '')
                doc_parameters.append(
                    f"{param_name} (path): {p_description} "
                    f"(required, {param_type})"
                )

            # Query parameters
            for q in endpoint['query_parameters']:
                param_name = q['name']
                param_type = get_param_type(q)
                required = q.get('required', False)
                enum = None
                
                # Get enum values if present in either schema or direct parameter definition
                if 'schema' in q:
                    enum = q['schema'].get('enum')
                elif 'enum' in q:
                    enum = q.get('enum')
                
                enum_str = f" [Allowed: {', '.join(enum)}]" if enum else ""
                
                parameters.append(
                    f"{param_name}: {param_type} = None" if not required 
                    else f"{param_name}: {param_type} = None"
                )

                q_description = q.get('description', '')
                doc_parameters.append(
                    f"{param_name} (query): {q_description} "
                    f"({'required' if required else 'optional'}, {param_type}){enum_str}"
                )

            # Header parameters
            for h in endpoint['header_parameters']:
                param_name = h['name']
                param_type = get_param_type(h)
                required = h.get('required', False)
                
                parameters.append(
                    f"{param_name}: {param_type} = None" if not required 
                    else f"{param_name}: {param_type} = None"
                )

                h_description = h.get('description','')

                doc_parameters.append(
                    f"{param_name} (header): {h_description} "
                    f"({'required' if required else 'optional'}, {param_type})"
                )

            # Request body - create Pydantic model if needed
            request_model = None
            if endpoint['request_body'] is not None:
                try:
                    # Get the pre-generated model name
                    model_name = model_mapping[func_name]
                    request_model = globals()[model_name]
                    
                    # Add the model as a parameter to the function
                    parameters.append(f"body: {model_name} = None")
                    doc_parameters.append(
                        f"body (body): Request body ({model_name} instance)\n"
                        f"Example structure: {json.dumps(endpoint['request_body'], indent=2)}"
                    )
                except KeyError as e:
                    logger.error(f"Error finding model for {func_name}: {str(e)}")
                    logger.debug(f"Available models: {list(model_mapping.keys())}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error handling request body for {func_name}: {str(e)}")
                    continue

            # Generate function signature
            params_str = ', '.join(parameters)
            
            # Build docstring
            docstring = f'"""{endpoint["summary"]}\n\n{endpoint["description"]}\n\nParameters:\n'
            docstring += '\n'.join([f'- {p}' for p in doc_parameters])
            docstring += '\n"""'
            
            # Generate function code
            func_code = f'def {func_name}({params_str}):\n'
            func_code += f'    {docstring}\n'
            
            # URL construction
            func_code += f'    try:\n'
            func_code += f'        url = f"{API_BASE_URL}{path}"\n'
            func_code += f'        logger.debug(f"Base URL constructed: {{url}}")\n'
            
            for p in endpoint['path_parameters']:
                name = p['name']
                func_code += f'        url = url.replace("{{{name}}}", str({name}))\n'
            
            func_code += f'        logger.debug(f"Final URL with path parameters: {{url}}")\n'
            
            # Query parameters
            func_code += '        params = {}\n'
            for q in endpoint['query_parameters']:
                name = q['name']
                func_code += f'        if {name} is not None:\n'
                func_code += f'            params["{name}"] = {name}\n'
                func_code += f'            logger.debug(f"Added query parameter: {name}={{{name}}}")\n'
            
            # Headers
            func_code += '        headers = {"Content-Type": "application/json"}\n'
            func_code += '        # Add any custom API headers from config\n'
            func_code += '        if API_HEADERS:\n'
            func_code += '            try:\n'
            func_code += '                custom_headers = {}\n'
            func_code += '                header_pairs = API_HEADERS.split(",")\n'
            func_code += '                for pair in header_pairs:\n'
            func_code += '                    key, value = pair.split(":")\n'
            func_code += '                    custom_headers[key.strip()] = value.strip()\n'
            func_code += '                headers.update(custom_headers)\n'
            func_code += '                logger.debug(f"Added custom headers from config: {custom_headers}")\n'
            func_code += '            except json.JSONDecodeError as e:\n'
            func_code += '                logger.warning(f"Failed to parse API_HEADERS: {e}")\n'
            
            for h in endpoint['header_parameters']:
                name = h['name']
                func_code += f'        if {name} is not None:\n'
                func_code += f'            headers["{name}"] = {name}\n'
                func_code += f'            logger.debug(f"Added header: {name}={{{name}}}")\n'
            
            # Request body
            if request_model:
                # Create default model instance if needed
                func_code += f'        # Use provided body or create default\n'
                func_code += f'        if body is None:\n'
                func_code += f'            body = {model_name}(**{json.dumps(endpoint["request_body"])})\n'
                func_code += f'            logger.debug("Created default request body")\n'
                func_code += f'        # Convert Pydantic model to dict for request\n'
                func_code += f'        try:\n'
                func_code += f'            json_data = body.dict(exclude_unset=True)\n'
                func_code += f'            logger.debug(f"Request body: {{json.dumps(json_data, indent=2)}}")\n'
                func_code += f'        except AttributeError:\n'
                func_code += f'            # For Pydantic v2 compatibility\n'
                func_code += f'            json_data = body.model_dump(exclude_unset=True)\n'
                func_code += f'            logger.debug(f"Request body (v2): {{json.dumps(json_data, indent=2)}}")\n'
            else:
                func_code += '        json_data = None\n'
            
            # HTTP request
            func_code += f'        logger.info(f"Making {method} request to {{url}}")\n'
            func_code += f'        response = request("{method}", url, params=params, headers=headers, json=json_data)\n'
            func_code += f'        logger.debug(f"Response status code: {{response.status_code}}")\n'
            func_code += '        response.raise_for_status()  # Raise exception for bad status codes\n'
            func_code += '        try:\n'
            func_code += '            result = response.json()\n'
            func_code += '            logger.debug(f"Received JSON response")\n'
            func_code += '            logger.debug(result)\n'
            func_code += '            return result\n'
            func_code += '        except ValueError:\n'
            func_code += '            result = response.text\n'
            func_code += '            logger.debug(f"Received text response: {result[:100]}...")\n'
            func_code += '            return result\n'
            func_code += '    except Exception as e:\n'
            func_code += f'        error_msg = f"Error executing {func_name}: {{str(e)}}"\n'
            func_code += '        logger.error(error_msg)\n'
            func_code += '        return {"error": error_msg}\n'
            
            # Create the function in global scope
            logger.debug(f"Generated function code for {func_name}:\n{func_code}")
            try:
                exec(func_code, globals())
                logger.info(f"Successfully created function: {func_name}")
                
                # Apply decorator to the dynamically created function
                if func_name in globals():
                    globals()[func_name] = mcp.tool(name=endpoint["operationId"], description=endpoint["description"])(globals()[func_name])
                    logger.debug(f"Function {func_name} registered as tool")

            except Exception as exec_error:
                logger.error(f"Failed to create function {func_name}: {str(exec_error)}")
                logger.error(f"Function code that failed:\n{func_code}")
                
        except Exception as e:
            logger.error(f"Error generating function for endpoint: {str(e)}")
            logger.debug(f"Endpoint data: {json.dumps(endpoint, indent=2)}")
            sys.exit(1)

def main():
    """
    Entry point for the openapi_mcp_server.
    The server supports dynamic parsing of the OpenAPI document and executes API calls with the appropriate request parameters.

    Configuration is controlled via environment variables:
    - DEBUG: Enable debug logging (optional default is False)
    - OPENAPI_SPEC_PATH: Path to the OpenAPI document
    - API_BASE_URL: Base URL for the API requests
    - API_HEADERS: Headers to include in the API requests (optional)
    - API_WHITE_LIST: White Listed operationId in list format ["operationId1", "operationId2"] (optional)
    - API_BLACK_LIST: Black Listed operationId in list format ["operationId3", "operationId4"] (optional)
    - HTTP_PROXY: HTTP Proxy details
    - HTTPS_PROXY: HTTPS Proxy details
    - NO_PROXY: No Proxy details
    """
    
    try:

        print("""
              #############################################
              #       OPENAPI MCP SERVER CLI STARTING    #
              #############################################
              """)

        # Setup logging configuration
        log_configuration_setup()

        # Load environment variables
        load_environment_variables()

        # Create dynamic tools
        create_dynamic_tools()
        logger.info("Dynamic tools created successfully")

        # Start the FastMCP server
        mcp.run()
    
    except KeyboardInterrupt:
        logger.info("Server shutting down gracefully...")
    except Exception as e:
        logger.error(f"Error starting the openapi_mcp_server: {str(e)}")
        sys.exit(1)
    finally:
        logger.info("Server stopped")

if __name__ == '__main__':
    main()