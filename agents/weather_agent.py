#!/usr/bin/env python3
"""
Weather Agent for the MultiModal Assistant.
Specialized agent for weather-related queries and data retrieval.
"""

from typing import Dict, Any
import json
from .base_agent import BaseAgent
from tools import get_current_weather
from bus import ActionTypes, emit_speech, emit_status, emit_progress, emit_token


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
            
            # Emit immediate progress for streaming
            emit_speech(f"I'll check the weather in {location} for you...", source=self.name)
            emit_status(f"Connecting to weather service for {location}", source=self.name)
            emit_progress("Initializing weather lookup...", 10, source=self.name)
            
            # The get_current_weather function now emits its own progress
            # Get weather data (this will emit progress internally)
            weather_data = get_current_weather(location)
            
            # Format the response
            formatted_response = self._format_weather_response(weather_data)
            
            # Emit completion and results
            emit_progress("Weather data processed successfully", 100, source=self.name)
            emit_speech(f"Here's the weather update: {formatted_response}", source=self.name)
            emit_status("Weather lookup completed", source=self.name)
            
            # Emit weather update event
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
        
        # Fallback: extract location from task string
        # Handle cases like "Get weather information for Seattle"
        import re
        
        # Look for location patterns in the task
        location_patterns = [
            r'(?:get\s+weather\s+information\s+for\s+)([A-Z][a-z\s]+)',  # "Get weather information for Seattle"
            r'(?:weather\s+in\s+)([A-Z][a-z\s]+)',  # "weather in Seattle"
            r'(?:weather\s+for\s+)([A-Z][a-z\s]+)',  # "weather for Seattle"
            r'(?:forecast\s+for\s+)([A-Z][a-z\s]+)',  # "forecast for Seattle"
            r'(?:temperature\s+in\s+)([A-Z][a-z\s]+)',  # "temperature in Seattle"
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, task, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If no pattern matches, treat entire task as location
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