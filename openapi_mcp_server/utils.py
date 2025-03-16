import sys
import logging
import copy
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

def setup_logging(debug=False)  -> logging.Logger:
    """
    Setup the logging configuration for the application. 
    """          
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    # Remove all existing handlers to prevent accumulation
    for handler in logger.handlers:
        logger.removeHandler(handler)
    
    handlers = []
           
    # Create a new handler
    try:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG if debug else logging.INFO)
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        handlers.append(handler)
    except Exception as e:
        logger.error(f"Failed to create stdout log handler: {e}", file=sys.stderr)

    # Add the handlers to the logger
    for handler in handlers:
        logger.addHandler(handler)
    
    return logger

def load_swagger_spec(spec: Dict[Any, Any]) -> str:
    """
    Load the Swagger/OpenAPI specification file
    
    :param spec: Swagger/OpenAPI specification file
    :return: version
    """
    try:
        logger.debug("Loading Swagger/OpenAPI specification")
        
        # Determine Swagger/OpenAPI version
        if 'swagger' in spec:
            version = '2.0'
            logger.info(f"Detected Swagger version {version}")
        elif 'openapi' in spec:
            version = '3.0'
            logger.info(f"Detected OpenAPI version {version}")
        else:
            logger.error("Unable to detect Swagger/OpenAPI version")
            raise ValueError("Unable to detect Swagger/OpenAPI version")
            
        return version
    except Exception as e:
        logger.error(f"Error loading swagger spec: {str(e)}")
        raise

def resolve_ref(spec: Dict[Any, Any], ref: str) -> Dict[Any, Any]:
    """
    Resolve JSON reference
    
    :param spec: The OpenAPI specification
    :param ref: Reference path
    :return: Resolved schema
    """
    try:
        logger.debug(f"Resolving reference: {ref}")
        # Remove leading '#/' if present
        if ref.startswith('#/'):
            ref = ref[2:]
        
        # Split reference path
        ref_parts = ref.split('/')
        
        # Traverse the spec to find the referenced object
        current = spec
        for part in ref_parts:
            if part not in current:
                logger.error(f"Reference part '{part}' not found in spec")
                raise ValueError(f"Reference part '{part}' not found in spec")
            current = current[part]
        
        logger.debug(f"Successfully resolved reference: {ref}")
        return current
    except Exception as e:
        logger.error(f"Error resolving reference '{ref}': {str(e)}")
        raise

def generate_sample_request(spec: Dict[Any, Any], version: str, path: str, method: str) -> Optional[Dict[Any, Any]]:
    """
    Generate a sample request for a specific path and HTTP method
    
    :param spec: The OpenAPI specification
    :param version: Spec version ('2.0' or '3.0')
    :param path: API endpoint path
    :param method: HTTP method (get, post, put, etc.)
    :return: Sample request dictionary or None
    """
    try:
        logger.debug(f"Generating sample request for {method.upper()} {path}")
        
        # Detect correct spec location based on version
        if version == '2.0':
            paths = spec.get('paths', {})
            path_spec = paths.get(path, {})
            method_spec = path_spec.get(method.lower(), {})

            # Check for JSON request body
            parameters = method_spec.get('parameters', [])
            body_param = next((p for p in parameters 
                            if p.get('in') == 'body'), 
                            None)
            
            if body_param:
                # Handle reference in body parameter schema
                schema = body_param.get('schema', {})
                
                # Resolve reference if exists
                if '$ref' in schema:
                    schema = resolve_ref(spec, schema['$ref'])
                
                return generate_sample_from_schema(spec, schema)
        
        elif version == '3.0':
            paths = spec.get('paths', {})
            path_spec = paths.get(path, {})
            method_spec = path_spec.get(method.lower(), {})
            
            # Find JSON request body for OpenAPI 3
            request_body = method_spec.get('requestBody', {})
            content = request_body.get('content', {})
            json_content = content.get('application/json', {})
            schema = json_content.get('schema', {})
            
            if schema:
                return generate_sample_from_schema(spec, schema)
        
        logger.debug(f"No request body found for {method.upper()} {path}")
        return None
    except Exception as e:
        logger.error(f"Error generating sample request for {method.upper()} {path}: {str(e)}")
        return None

def resolve_full_schema(spec: Dict[Any, Any], schema: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Recursively resolve all references in a schema
    
    :param spec: The OpenAPI specification
    :param schema: Original schema
    :return: Fully resolved schema
    """
    try:
        # Create a deep copy to avoid modifying original
        resolved_schema = copy.deepcopy(schema)

        # Resolve top-level reference
        if '$ref' in resolved_schema:
            ref = resolved_schema['$ref']
            logger.debug(f"Resolving top-level reference: {ref}")
            resolved_schema = resolve_ref(spec, ref)

        # Resolve nested references in properties
        if resolved_schema.get('type') == 'object':
            properties = resolved_schema.get('properties', {})
            for prop_name, prop_schema in properties.items():
                # Resolve reference in property
                if '$ref' in prop_schema:
                    logger.debug(f"Resolving reference in property '{prop_name}': {prop_schema['$ref']}")
                    properties[prop_name] = resolve_ref(spec, prop_schema['$ref'])
                # Recursively resolve nested object references
                elif prop_schema.get('type') == 'object':
                    logger.debug(f"Resolving nested object in property '{prop_name}'")
                    properties[prop_name] = resolve_full_schema(spec, prop_schema)

        # Resolve array items reference
        if resolved_schema.get('type') == 'array':
            items = resolved_schema.get('items', {})
            if '$ref' in items:
                logger.debug(f"Resolving reference in array items: {items['$ref']}")
                resolved_schema['items'] = resolve_ref(spec, items['$ref'])
            # Recursively resolve nested references in array items
            elif isinstance(items, dict):
                logger.debug("Resolving nested schema in array items")
                resolved_schema['items'] = resolve_full_schema(spec, items)

        return resolved_schema
    except Exception as e:
        logger.error(f"Error resolving schema: {str(e)}")
        raise

def generate_array_sample(spec: Dict[Any, Any], schema: Dict[Any, Any]) -> list:
    """
    Generate a sample array based on schema
    
    :param spec: The OpenAPI specification
    :param schema: Array schema
    :return: Sample array
    """
    try:
        logger.debug("Generating sample array")
        
        # Get items schema
        items_schema = schema.get('items', {})
        
        # Determine number of items (use minItems or default to 1)
        min_items = schema.get('minItems', 1)
        
        # Generate array of sample items
        sample_array = [generate_default_value(spec, items_schema) for _ in range(min_items)]
        logger.debug(f"Generated sample array with {len(sample_array)} items")
        return sample_array
    except Exception as e:
        logger.error(f"Error generating array sample: {str(e)}")
        return []

def generate_default_value(spec: Dict[Any, Any], schema: Dict[Any, Any]) -> Any:
    """
    Generate a default value based on schema type
    
    :param spec: The OpenAPI specification
    :param schema: Property schema
    :return: Default value
    """
    try:
        # Resolve any references
        schema = resolve_full_schema(spec, schema)

        # Check for default value first
        if 'default' in schema:
            logger.debug(f"Using default value from schema")
            return schema['default']
        
        # Check for example value
        if 'example' in schema:
            logger.debug(f"Using example value from schema")
            return schema['example']

        # Handle different types
        schema_type = schema.get('type')
        if schema_type == 'string':
            return ''
        elif schema_type == 'integer':
            return 0
        elif schema_type == 'number':
            return 0.0
        elif schema_type == 'boolean':
            return False
        elif schema_type == 'array':
            return generate_array_sample(spec, schema)
        elif schema_type == 'object':
            return generate_sample_from_schema(spec, schema)
        
        logger.debug(f"No type specified, returning None")
        return None
    except Exception as e:
        logger.error(f"Error generating default value: {str(e)}")
        return None

def generate_sample_from_schema(spec: Dict[Any, Any], schema: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Generate a sample request from a JSON schema
    
    :param spec: The OpenAPI specification
    :param schema: JSON schema definition
    :return: Sample request dictionary
    """
    try:
        logger.debug("Generating sample from schema")
        
        # Resolve references recursively
        schema = resolve_full_schema(spec, schema)

        # Handle object type schemas
        if schema.get('type') == 'object':
            sample = {}
            properties = schema.get('properties', {})

            for prop_name, prop_schema in properties.items():
                # Only add required fields or fields with default values
                if 'default' in prop_schema or 'example' in prop_schema:
                    # Use default value if provided
                    if 'default' in prop_schema:
                        logger.debug(f"Using default value for property '{prop_name}'")
                        sample[prop_name] = prop_schema['default']
                    elif 'example' in prop_schema:
                        logger.debug(f"Using example value for property '{prop_name}'")
                        sample[prop_name] = prop_schema['example']
                else:
                    # Generate sample based on property schema
                    logger.debug(f"Generating sample value for property '{prop_name}'")
                    sample[prop_name] = generate_default_value(spec, prop_schema)

            return sample
        
        # Handle array type
        elif schema.get('type') == 'array':
            return generate_array_sample(spec, schema)
        
        logger.debug("Schema is not object or array, returning empty dict")
        return {}
    except Exception as e:
        logger.error(f"Error generating sample from schema: {str(e)}")
        return {}

def extract_api_metadata(API_WHITE_LIST, API_BLACK_LIST, spec: Dict[Any, Any], version: str) -> list:
    """
    Extract API metadata from the OpenAPI specification
    
    :param API_WHITE_LIST: List of operationIds to include (if provided)
    :param API_BLACK_LIST: List of operationIds to exclude
    :param spec: The OpenAPI specification
    :param version: Spec version
    :return: List of API metadata dictionaries
    """
    try:
        logger.info("Extracting API metadata")
        api_metadata = []
        paths = spec.get('paths', {})

        for path, methods in paths.items():
            for method, method_info in methods.items():
                operation_id = method_info.get('operationId', '')
                
                # Skip if the function is not in the white list
                if API_WHITE_LIST and operation_id not in API_WHITE_LIST:
                    logger.debug(f"Skipping {operation_id} - not in white list")
                    continue

                # Skip if the function is in the black list
                if API_BLACK_LIST and operation_id in API_BLACK_LIST:
                    logger.debug(f"Skipping {operation_id} - in black list")
                    continue
                    
                logger.debug(f"Processing API endpoint: {method.upper()} {path} ({operation_id})")
                
                # Determine if we need to include a request body sample
                request_body = None
                if method.lower() in ['post', 'put', 'patch']:
                    request_body = generate_sample_request(spec, version, path, method)
                
                # Separate parameters by type
                header_params = []
                path_params = []
                query_params = []
                
                if method_info.get('parameters'):
                    for param in method_info.get('parameters', []):
                        param_in = param.get('in', '')
                        if param_in == 'header':
                            header_params.append(param)
                        elif param_in == 'path':
                            path_params.append(param)
                        elif param_in == 'query':
                            query_params.append(param)
                
                metadata = {
                    'path': path,
                    'method': method,
                    'summary': method_info.get('summary', ''),
                    'description': method_info.get('description', ''),
                    'operationId': operation_id,
                    'header_parameters': header_params,
                    'path_parameters': path_params,
                    'query_parameters': query_params,
                    'request_body': request_body
                }
                
                api_metadata.append(metadata)
                logger.debug(f"Added metadata for {operation_id}")
        
        logger.info(f"Extracted {len(api_metadata)} API endpoints")
        return api_metadata
    except Exception as e:
        logger.error(f"Error extracting API metadata: {str(e)}")
        raise

# Converting Swagger to Python Models
def get_py_type(json_type):
    """Convert JSON schema types to Python/Pydantic types"""
    type_map = {
        'integer': int,
        'number': float,
        'string': str,
        'boolean': bool,
        'array': List,
        'object': Dict[str, Any]
    }
    return type_map.get(json_type, Any)

