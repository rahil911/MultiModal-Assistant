#!/usr/bin/env python3
"""
Weather Agent for the MultiModal Assistant.
Specialized agent for weather-related queries and data retrieval.
"""

from typing import Dict, Any
import json
from .base_agent import BaseAgent
from tools import get_current_weather
from bus import ActionTypes


class WeatherAgent(BaseAgent):
    """
    Specialized agent for weather information retrieval.
    Demonstrates domain-specific agent pattern.
    """
    
    def __init__(self):
        super().__init__(
            name="WeatherAgent", 
            description="Specialized agent for weather data retrieval and analysis"
        )
        
    async def run(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a weather-related task.
        
        Args:
            task: Weather query or location
            context: Additional context (may contain location, query type, etc.)
            
        Returns:
            Weather data and formatted response
        """
        await self.notify_start(f"Getting weather for: {task}")
        
        try:
            # Extract location from task or context
            location = self._extract_location(task, context)
            
            if not location:
                error_msg = "No location specified for weather query"
                await self.notify_error(error_msg)
                return {"error": error_msg}
            
            # Show progress
            await self.notify_progress(f"Fetching weather data for {location}")
            await self.emit(ActionTypes.SHOW_PROGRESS, {
                "message": f"🌤️ Fetching current weather for {location}...",
                "location": location
            })
            
            # Get weather data
            weather_data = get_current_weather(location)
            
            # Format the response
            formatted_response = self._format_weather_response(weather_data)
            
            # Emit weather update
            await self.emit("weather_update", {
                "location": location,
                "weather_data": weather_data,
                "formatted_response": formatted_response
            })
            
            await self.notify_complete({
                "location": location,
                "weather_data": weather_data
            })
            
            return {
                "success": True,
                "location": location,
                "weather_data": weather_data,
                "formatted_response": formatted_response
            }
            
        except Exception as e:
            error_msg = f"Error retrieving weather: {str(e)}"
            await self.notify_error(error_msg)
            return {"error": error_msg}
    
    def _extract_location(self, task: str, context: Dict[str, Any] = None) -> str:
        """
        Extract location from task string or context.
        
        Args:
            task: Task description
            context: Additional context data
            
        Returns:
            Extracted location string
        """
        # Check context first
        if context and "location" in context:
            return context["location"]
        
        # Check if task contains location info
        if context and "arguments" in context:
            args = context["arguments"]
            if isinstance(args, dict) and "location" in args:
                return args["location"]
            elif isinstance(args, str):
                try:
                    args_dict = json.loads(args)
                    if "location" in args_dict:
                        return args_dict["location"]
                except json.JSONDecodeError:
                    pass
        
        # Fallback: treat entire task as location
        # This is a simple approach - in production, you might use NLP to extract location
        return task.strip()
    
    def _format_weather_response(self, weather_data: Dict[str, Any]) -> str:
        """
        Format weather data into a human-readable response.
        
        Args:
            weather_data: Raw weather data from API
            
        Returns:
            Formatted response string
        """
        location = weather_data.get("location", "Unknown")
        temp = weather_data.get("temperature_c", "N/A")
        condition = weather_data.get("condition", "Unknown")
        
        return f"The weather in {location} is currently {condition} and {temp}°C."
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return capabilities of this agent."""
        return {
            **super().get_capabilities(),
            "functions": [
                "get_current_weather",
                "format_weather_data",
                "extract_location_from_text"
            ],
            "supported_queries": [
                "current weather",
                "temperature",
                "weather conditions"
            ],
            "data_sources": ["demo_stub"]  # In production: weather APIs
        }