#!/usr/bin/env python3
"""
Command Bus infrastructure for multi-agent communication.
Provides an in-process event queue that decouples agents from transport.
"""

import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class BusAction:
    """Represents an action/event on the command bus."""
    action: str
    data: Dict[str, Any]
    id: str = None
    timestamp: str = None
    source: str = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class CommandBus:
    """
    In-process event queue that enables loose coupling between agents and UI.
    Agents emit actions, UI components react via WebSocket streams.
    """
    
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._subscribers: List[asyncio.Queue] = []
        self._running = False
        
    async def start(self):
        """Start the command bus processing loop."""
        self._running = True
        asyncio.create_task(self._process_actions())
        
    async def stop(self):
        """Stop the command bus."""
        self._running = False
        
    def emit(self, action: str, data: Dict[str, Any], source: str = None) -> str:
        """
        Emit an action to the command bus.
        
        Args:
            action: The action type (e.g., "speak", "add_card", "show_progress")
            data: Action payload data
            source: Source identifier (agent name, etc.)
            
        Returns:
            The action ID
        """
        bus_action = BusAction(action=action, data=data, source=source)
        
        # Convert to JSON string for transport
        action_json = json.dumps(asdict(bus_action))
        
        # Add to queue (non-blocking)
        try:
            self._queue.put_nowait(action_json)
        except asyncio.QueueFull:
            print(f"⚠️ Command bus queue full, dropping action: {action}")
            
        return bus_action.id
    
    async def get_next_action(self) -> Optional[str]:
        """Get the next action from the queue (blocking)."""
        try:
            return await self._queue.get()
        except Exception:
            return None
    
    def subscribe(self) -> asyncio.Queue:
        """
        Subscribe to command bus events.
        Returns a queue that will receive all emitted actions.
        """
        subscriber_queue = asyncio.Queue()
        self._subscribers.append(subscriber_queue)
        return subscriber_queue
    
    def unsubscribe(self, subscriber_queue: asyncio.Queue):
        """Unsubscribe from command bus events."""
        if subscriber_queue in self._subscribers:
            self._subscribers.remove(subscriber_queue)
    
    async def _process_actions(self):
        """Internal processing loop that distributes actions to subscribers."""
        while self._running:
            try:
                action = await self._queue.get()
                
                # Distribute to all subscribers
                for subscriber in self._subscribers[:]:  # Copy list to avoid modification during iteration
                    try:
                        subscriber.put_nowait(action)
                    except asyncio.QueueFull:
                        # Remove subscriber if their queue is full
                        self._subscribers.remove(subscriber)
                        print("⚠️ Removed unresponsive subscriber")
                        
            except Exception as e:
                print(f"❌ Error in command bus processing: {e}")


# Global command bus instance
_command_bus: Optional[CommandBus] = None


async def get_command_bus() -> CommandBus:
    """Get the global command bus instance, creating it if necessary."""
    global _command_bus
    if _command_bus is None:
        _command_bus = CommandBus()
        await _command_bus.start()
    return _command_bus


def emit_action(action: str, data: Dict[str, Any], source: str = None) -> str:
    """
    Convenience function to emit an action to the global command bus.
    
    Args:
        action: The action type
        data: Action payload
        source: Source identifier
        
    Returns:
        Action ID
    """
    # For sync compatibility, agents should use async emit directly
    # This is a fallback that may not work in all contexts
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context - cannot use run_until_complete
            # Create a task instead of blocking
            task = asyncio.create_task(_async_emit_action(action, data, source))
            return f"async_task_{id(task)}"
        else:
            # Not in async context, create new event loop
            async def _emit():
                bus = await get_command_bus()
                return bus.emit(action, data, source)
            return asyncio.run(_emit())
    except Exception as e:
        print(f"❌ Error emitting action: {e}")
        return ""


async def _async_emit_action(action: str, data: Dict[str, Any], source: str = None) -> str:
    """Helper for async emission."""
    try:
        bus = await get_command_bus()
        return bus.emit(action, data, source)
    except Exception as e:
        print(f"❌ Error in async emit: {e}")
        return ""


# Common action types
class ActionTypes:
    """Common action types for consistency."""
    SPEAK = "speak"
    SHOW_PROGRESS = "show_progress"
    ADD_CARD = "add_card"
    UPDATE_STATUS = "update_status"
    TOOL_START = "tool_start"
    TOOL_COMPLETE = "tool_complete"
    ERROR = "error"
    AUDIO_START = "audio_start"
    AUDIO_COMPLETE = "audio_complete"