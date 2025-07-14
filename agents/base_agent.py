#!/usr/bin/env python3
"""
Base agent class for the MultiModal Assistant multi-agent system.
Provides common functionality and command bus integration.
"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from bus import emit_action, ActionTypes


class BaseAgent(ABC):
    """
    Base class for all agents in the MultiModal Assistant system.
    Provides command bus integration and common functionality.
    """
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.is_active = False
        
    async def emit(self, action: str, data: Dict[str, Any]) -> str:
        """
        Emit an action to the command bus with this agent as the source.
        
        Args:
            action: Action type
            data: Action data
            
        Returns:
            Action ID
        """
        from bus import get_command_bus
        try:
            bus = await get_command_bus()
            return bus.emit(action, data, source=self.name)
        except Exception as e:
            print(f"❌ Error emitting from {self.name}: {e}")
            return ""
    
    async def notify_start(self, task: str):
        """Notify that this agent is starting a task."""
        self.is_active = True
        await self.emit(ActionTypes.UPDATE_STATUS, {
            "agent": self.name,
            "status": "active",
            "task": task
        })
        
    async def notify_progress(self, message: str, progress: float = None):
        """Notify progress on current task."""
        data = {
            "agent": self.name,
            "message": message
        }
        if progress is not None:
            data["progress"] = progress
            
        await self.emit(ActionTypes.SHOW_PROGRESS, data)
        
    async def notify_complete(self, result: Any = None):
        """Notify that the current task is complete."""
        self.is_active = False
        await self.emit(ActionTypes.UPDATE_STATUS, {
            "agent": self.name,
            "status": "idle",
            "result": result
        })
        
    async def notify_error(self, error: str, details: Dict[str, Any] = None):
        """Notify that an error occurred."""
        self.is_active = False
        error_data = {
            "agent": self.name,
            "error": error
        }
        if details:
            error_data.update(details)
            
        await self.emit(ActionTypes.ERROR, error_data)
        
    async def speak(self, text: str, priority: str = "normal"):
        """
        Request text-to-speech for the given text.
        
        Args:
            text: Text to speak
            priority: Priority level ("high", "normal", "low")
        """
        await self.emit(ActionTypes.SPEAK, {
            "text": text,
            "priority": priority,
            "agent": self.name
        })
        
    @abstractmethod
    async def run(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a task assigned to this agent.
        
        Args:
            task: Task description or instruction
            context: Additional context data
            
        Returns:
            Task result as dictionary
        """
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return a description of this agent's capabilities.
        
        Returns:
            Dictionary describing capabilities, tools, and parameters
        """
        return {
            "name": self.name,
            "description": self.description,
            "active": self.is_active
        }