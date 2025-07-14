#!/usr/bin/env python3
"""
Calendar Agent for the MultiModal Assistant.
Example domain agent for calendar and scheduling operations.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from .base_agent import BaseAgent
from bus import ActionTypes, emit_speech, emit_status, emit_progress, emit_token


class CalendarAgent(BaseAgent):
    """
    Example agent for calendar and scheduling operations.
    Demonstrates how to add new domain-specific agents.
    """
    
    def __init__(self):
        super().__init__(
            name="CalendarAgent",
            description="Agent for calendar management and scheduling tasks"
        )
        # Mock calendar data for demo
        self.mock_events = [
            {
                "id": "1",
                "title": "Team Standup",
                "start": datetime.now().replace(hour=9, minute=0, second=0, microsecond=0),
                "duration": 30,
                "type": "meeting"
            },
            {
                "id": "2", 
                "title": "Code Review",
                "start": datetime.now().replace(hour=14, minute=30, second=0, microsecond=0),
                "duration": 60,
                "type": "work"
            }
        ]
        
    async def run(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a calendar-related task.
        
        Args:
            task: Calendar query or command
            context: Additional context
            
        Returns:
            Calendar data and response
        """
        await self.notify_start(f"Calendar task: {task[:50]}...")
        
        try:
            # Determine task type
            task_lower = task.lower()
            
            if "today" in task_lower or "schedule" in task_lower:
                result = await self._get_today_schedule()
            elif "add" in task_lower or "create" in task_lower:
                result = await self._add_event(task, context)
            elif "next" in task_lower:
                result = await self._get_next_event()
            else:
                result = {"error": f"Unknown calendar task: {task}"}
            
            await self.notify_complete(result)
            return result
            
        except Exception as e:
            error_msg = f"Error in calendar operation: {str(e)}"
            await self.notify_error(error_msg)
            return {"error": error_msg}
    
    async def _get_today_schedule(self) -> Dict[str, Any]:
        """Get today's schedule."""
        await self.notify_progress("Fetching today's schedule...")
        
        today = datetime.now().date()
        today_events = [
            event for event in self.mock_events
            if event["start"].date() == today
        ]
        
        # Format response
        if not today_events:
            response = "You have no events scheduled for today."
        else:
            event_list = []
            for event in sorted(today_events, key=lambda x: x["start"]):
                time_str = event["start"].strftime("%I:%M %p")
                event_list.append(f"• {time_str}: {event['title']}")
            
            response = f"Your schedule for today:\n{chr(10).join(event_list)}"
        
        # Emit calendar update
        await self.emit("calendar_update", {
            "type": "daily_schedule",
            "date": today.isoformat(),
            "events": today_events,
            "count": len(today_events)
        })
        
        return {
            "success": True,
            "events": today_events,
            "formatted_response": response
        }
    
    async def _get_next_event(self) -> Dict[str, Any]:
        """Get the next upcoming event."""
        await self.notify_progress("Finding next event...")
        
        now = datetime.now()
        upcoming_events = [
            event for event in self.mock_events
            if event["start"] > now
        ]
        
        if not upcoming_events:
            response = "No upcoming events found."
            next_event = None
        else:
            next_event = min(upcoming_events, key=lambda x: x["start"])
            time_str = next_event["start"].strftime("%I:%M %p on %A")
            response = f"Your next event is '{next_event['title']}' at {time_str}."
        
        return {
            "success": True,
            "next_event": next_event,
            "formatted_response": response
        }
    
    async def _add_event(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Add a new event (mock implementation)."""
        await self.notify_progress("Adding event...")
        
        # This is a mock implementation
        # In production, you would parse the task to extract event details
        new_event = {
            "id": str(len(self.mock_events) + 1),
            "title": "New Event",
            "start": datetime.now() + timedelta(hours=1),
            "duration": 60,
            "type": "user_created"
        }
        
        self.mock_events.append(new_event)
        
        response = f"Added event '{new_event['title']}' to your calendar."
        
        # Emit event creation
        await self.emit("calendar_event_created", {
            "event": new_event
        })
        
        return {
            "success": True,
            "event": new_event,
            "formatted_response": response
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return capabilities of this agent."""
        return {
            **super().get_capabilities(),
            "functions": [
                "get_today_schedule",
                "get_next_event", 
                "add_event",
                "find_free_time"
            ],
            "supported_queries": [
                "today's schedule",
                "next meeting",
                "add event",
                "free time"
            ],
            "event_count": len(self.mock_events)
        }