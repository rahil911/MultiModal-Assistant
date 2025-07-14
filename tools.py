#!/usr/bin/env python3
"""
Tools and function definitions for the multimodal assistant.
"""

from typing import Dict, Any, List


def get_current_weather(location: str) -> Dict[str, Any]:
    """
    Stand-in for an external REST/GraphQL/database call.
    Returns deterministic fake data so the demo works offline.
    
    Args:
        location: The city/location to get weather for
        
    Returns:
        Dictionary containing weather information
    """
    return {
        "location": location,
        "temperature_c": 23,
        "condition": "Partly cloudy",
        "source": "demo_stub"
    }


# Tool specifications for OpenAI API
TOOLS_SPEC: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Fetch the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }
    }
]

# Function registry for dynamic calling
FUNCTION_REGISTRY = {
    "get_current_weather": get_current_weather
}


def execute_function(function_name: str, **kwargs) -> Any:
    """
    Execute a function from the registry.
    
    Args:
        function_name: Name of the function to execute
        **kwargs: Arguments to pass to the function
        
    Returns:
        Result of the function execution
        
    Raises:
        ValueError: If function is not found in registry
    """
    if function_name not in FUNCTION_REGISTRY:
        raise ValueError(f"Function '{function_name}' not found in registry")
    
    return FUNCTION_REGISTRY[function_name](**kwargs) 