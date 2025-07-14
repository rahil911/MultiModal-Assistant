#!/usr/bin/env python3
"""
Workflow orchestration system compatible with Google ADK patterns.
Provides multi-agent coordination and task routing.
"""

import asyncio
from typing import Dict, Any, List, Optional, Type
from abc import ABC, abstractmethod
from enum import Enum
from agents import BaseAgent, PlannerAgent, WeatherAgent, CalendarAgent
from bus import get_command_bus, ActionTypes


class WorkflowTopology(Enum):
    """Supported workflow topologies."""
    STAR = "star"          # Central planner delegates to specialists
    CHAIN = "chain"        # Sequential agent processing
    PARALLEL = "parallel"  # All agents process simultaneously


class Agent(ABC):
    """
    ADK-compatible agent interface.
    Wrapper around our BaseAgent to match ADK patterns.
    """
    
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.tools = []
        
    @abstractmethod
    async def run(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute the agent's task."""
        pass


class Workflow:
    """
    Multi-agent workflow orchestrator following ADK patterns.
    Coordinates agent execution based on topology and routing rules.
    """
    
    def __init__(self, agents: List[BaseAgent], topology: str = "star"):
        self.agents = {agent.name: agent for agent in agents}
        self.topology = WorkflowTopology(topology)
        self.command_bus = None
        self.planner = None
        
        # Find planner agent
        for agent in agents:
            if isinstance(agent, PlannerAgent):
                self.planner = agent
                break
    
    async def __call__(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute the workflow with the given task.
        
        Args:
            task: Task description or user input
            context: Additional context data
            
        Returns:
            Final result from workflow execution
        """
        # Initialize command bus if needed
        if self.command_bus is None:
            self.command_bus = await get_command_bus()
        
        # Create task router to analyze the task
        router = TaskRouter(self.agents)
        
        # Check if this is a complex multi-agent task
        if router.should_use_parallel_execution(task):
            return await self._execute_complex_task(task, context, router)
        
        # Emit workflow start
        self.command_bus.emit(ActionTypes.UPDATE_STATUS, {
            "workflow": "started",
            "task": task[:100] + "..." if len(task) > 100 else task,
            "topology": self.topology.value,
            "agents": list(self.agents.keys())
        })
        
        try:
            if self.topology == WorkflowTopology.STAR:
                return await self._execute_star_topology(task, context)
            elif self.topology == WorkflowTopology.CHAIN:
                return await self._execute_chain_topology(task, context)
            elif self.topology == WorkflowTopology.PARALLEL:
                return await self._execute_parallel_topology(task, context)
            else:
                raise ValueError(f"Unsupported topology: {self.topology}")
                
        except Exception as e:
            error_result = {"error": f"Workflow execution failed: {str(e)}"}
            self.command_bus.emit(ActionTypes.ERROR, {
                "workflow": "failed",
                "error": str(e)
            })
            return error_result
        finally:
            self.command_bus.emit(ActionTypes.UPDATE_STATUS, {
                "workflow": "completed"
            })
    
    async def _execute_complex_task(self, task: str, context: Dict[str, Any], router: 'TaskRouter') -> Dict[str, Any]:
        """
        Execute complex multi-agent tasks with intelligent distribution.
        
        Args:
            task: Complex task description
            context: Additional context
            router: TaskRouter instance for parsing tasks
            
        Returns:
            Combined results from all agents
        """
        from bus import emit_speech, emit_status, emit_progress
        
        # Emit start of complex coordination
        emit_speech("I'll coordinate multiple agents to handle your request.", source="WorkflowOrchestrator")
        emit_status("Analyzing complex task for multi-agent coordination", source="WorkflowOrchestrator")
        
        # Parse the task into agent-specific sub-tasks
        agent_tasks = router.parse_complex_task(task)
        
        emit_progress(f"Task parsed: {len(agent_tasks)} agents will work in parallel", 20, source="WorkflowOrchestrator")
        
        # Execute tasks in parallel
        parallel_tasks = []
        for agent_name, sub_tasks in agent_tasks.items():
            if agent_name in self.agents:
                # Execute each sub-task individually for this agent
                for sub_task in sub_tasks:
                    parallel_tasks.append(self._execute_agent_task(agent_name, sub_task, context))
        
        emit_progress("Executing parallel agent tasks...", 50, source="WorkflowOrchestrator")
        
        # Wait for all agents to complete - this allows individual agent speech events to be heard
        results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
        
        # Process and combine results
        combined_result = await self._combine_agent_results(parallel_tasks, results)
        
        emit_progress("All agents completed, combining results", 90, source="WorkflowOrchestrator")
        
        # Don't generate final coordinated response immediately - let individual agent responses be heard first
        await asyncio.sleep(1.0)  # Brief pause to let agent audio complete
        
        # Generate final coordinated response
        final_response = await self._generate_final_response(combined_result, task)
        
        emit_progress("Multi-agent coordination complete", 100, source="WorkflowOrchestrator")
        
        return final_response
    
    async def _execute_agent_task(self, agent_name: str, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task on a specific agent."""
        try:
            agent = self.agents[agent_name]
            result = await agent.run(task, context)
            return {"agent": agent_name, "task": task, "result": result, "success": True}
        except Exception as e:
            return {"agent": agent_name, "task": task, "error": str(e), "success": False}
    
    async def _combine_agent_results(self, parallel_tasks: List, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine results from multiple agents."""
        combined = {
            "agent_results": {},
            "successful_agents": [],
            "failed_agents": [],
            "total_agents": len(results),
            "success_rate": 0
        }
        
        successful_count = 0
        for result in results:
            if isinstance(result, Exception):
                combined["failed_agents"].append({
                    "agent": "unknown",
                    "error": str(result)
                })
            elif result.get("success"):
                agent_name = result["agent"]
                
                # Handle multiple results from the same agent type
                if agent_name not in combined["agent_results"]:
                    combined["agent_results"][agent_name] = []
                    
                combined["agent_results"][agent_name].append(result["result"])
                
                if agent_name not in combined["successful_agents"]:
                    combined["successful_agents"].append(agent_name)
                successful_count += 1
            else:
                combined["failed_agents"].append({
                    "agent": result.get("agent", "unknown"),
                    "error": result.get("error", "Unknown error")
                })
        
        combined["success_rate"] = successful_count / len(results) if results else 0
        return combined
    
    async def _generate_final_response(self, combined_result: Dict[str, Any], original_task: str) -> Dict[str, Any]:
        """Generate a coordinated final response from all agent results."""
        from bus import emit_token
        
        # Extract key information from each agent's results
        responses = []
        
        for agent_name, agent_results in combined_result["agent_results"].items():
            # Handle both single results and lists of results
            if not isinstance(agent_results, list):
                agent_results = [agent_results]
            
            for agent_result in agent_results:
                if isinstance(agent_result, dict):
                    # Extract meaningful response text
                    if "formatted_response" in agent_result:
                        responses.append(f"{agent_name}: {agent_result['formatted_response']}")
                    elif "final_response" in agent_result:
                        responses.append(f"{agent_name}: {agent_result['final_response']}")
                    elif "response_text" in agent_result:
                        responses.append(f"{agent_name}: {agent_result['response_text']}")
                    elif agent_name == "WeatherAgent" and "weather_data" in agent_result:
                        weather = agent_result["weather_data"]
                        location = weather.get("location", "your location")
                        temp = weather.get("temperature_c", "unknown")
                        condition = weather.get("condition", "unknown")
                        responses.append(f"Weather: {location} is {condition} at {temp}°C")
        
        # Create comprehensive response
        if responses:
            final_text = "Here's everything you requested: " + " | ".join(responses)
        else:
            final_text = "I've processed your request across multiple agents, though some may not have returned detailed responses."
        
        # Stream the final coordinated response as tokens
        words = final_text.split()
        for i, word in enumerate(words):
            token = word if i == 0 else f" {word}"
            emit_token(token, source="WorkflowOrchestrator")
            await asyncio.sleep(0.03)  # Brief delay for streaming effect
        
        return {
            "type": "complex_coordination",
            "original_task": original_task,
            "agent_results": combined_result["agent_results"],
            "successful_agents": combined_result["successful_agents"],
            "failed_agents": combined_result["failed_agents"],
            "success_rate": combined_result["success_rate"],
            "final_response": final_text,
            "streaming_complete": True
        }
    
    async def _execute_star_topology(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute star topology: planner delegates to specialists.
        
        Args:
            task: Task to execute
            context: Additional context
            
        Returns:
            Result from planner agent
        """
        if not self.planner:
            raise ValueError("Star topology requires a PlannerAgent")
        
        # In star topology, the planner orchestrates everything
        # It may delegate to other agents internally
        return await self.planner.run(task, context)
    
    async def _execute_chain_topology(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute chain topology: sequential agent processing.
        
        Args:
            task: Task to execute
            context: Additional context
            
        Returns:
            Final result from chain execution
        """
        current_task = task
        current_context = context or {}
        
        for agent in self.agents.values():
            result = await agent.run(current_task, current_context)
            
            # Update context with result for next agent
            current_context.update(result)
            
            # If agent produced formatted response, use it as next task
            if "formatted_response" in result:
                current_task = result["formatted_response"]
        
        return current_context
    
    async def _execute_parallel_topology(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute parallel topology: all agents process simultaneously.
        
        Args:
            task: Task to execute
            context: Additional context
            
        Returns:
            Combined results from all agents
        """
        # Run all agents concurrently
        tasks = [
            agent.run(task, context) 
            for agent in self.agents.values()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        combined_result = {
            "parallel_results": {},
            "success": True,
            "errors": []
        }
        
        for agent_name, result in zip(self.agents.keys(), results):
            if isinstance(result, Exception):
                combined_result["errors"].append({
                    "agent": agent_name,
                    "error": str(result)
                })
                combined_result["success"] = False
            else:
                combined_result["parallel_results"][agent_name] = result
        
        return combined_result
    
    def add_agent(self, agent: BaseAgent):
        """Add an agent to the workflow."""
        self.agents[agent.name] = agent
    
    def remove_agent(self, agent_name: str):
        """Remove an agent from the workflow."""
        if agent_name in self.agents:
            del self.agents[agent_name]
    
    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """Get an agent by name."""
        return self.agents.get(agent_name)
    
    def list_agents(self) -> List[str]:
        """List all agent names."""
        return list(self.agents.keys())


class TaskRouter:
    """
    Intelligent task routing to appropriate agents.
    Analyzes complex tasks and routes to multiple agents for parallel execution.
    """
    
    def __init__(self, agents: Dict[str, BaseAgent]):
        self.agents = agents
        
    def route_task(self, task: str) -> str:
        """
        Route a task to the most appropriate agent (legacy single-agent routing).
        
        Args:
            task: Task description
            
        Returns:
            Name of the best-suited agent
        """
        task_lower = task.lower()
        
        # Simple keyword-based routing
        if any(word in task_lower for word in ["weather", "temperature", "forecast", "climate"]):
            return "WeatherAgent"
        elif any(word in task_lower for word in ["calendar", "schedule", "meeting", "appointment", "event"]):
            return "CalendarAgent"
        else:
            return "PlannerAgent"
    
    def parse_complex_task(self, task: str) -> Dict[str, List[str]]:
        """
        Parse complex tasks that require multiple agents.
        
        Args:
            task: Complex task description (e.g., "Plan my day - check weather, schedule meeting, tell joke")
            
        Returns:
            Dictionary mapping agent names to their specific sub-tasks
        """
        task_lower = task.lower()
        agent_tasks = {}
        
        # Special handling for multi-location weather queries
        if self._is_multi_location_weather_query(task):
            locations = self._extract_multiple_locations(task)
            agent_tasks["WeatherAgent"] = [f"Get weather information for {loc}" for loc in locations]
            return agent_tasks
        
        # Split on common delimiters for multi-part tasks
        parts = self._split_task_parts(task)
        
        for part in parts:
            part_lower = part.lower().strip()
            if not part_lower:
                continue
                
            # Route each part to appropriate agent
            if any(word in part_lower for word in ["weather", "temperature", "forecast", "climate"]):
                if "WeatherAgent" not in agent_tasks:
                    agent_tasks["WeatherAgent"] = []
                agent_tasks["WeatherAgent"].append(self._extract_weather_task(part, task))
                
            elif any(word in part_lower for word in ["calendar", "schedule", "meeting", "appointment", "event"]):
                if "CalendarAgent" not in agent_tasks:
                    agent_tasks["CalendarAgent"] = []
                agent_tasks["CalendarAgent"].append(self._extract_calendar_task(part, task))
                
            else:
                # General planning tasks go to PlannerAgent
                if "PlannerAgent" not in agent_tasks:
                    agent_tasks["PlannerAgent"] = []
                agent_tasks["PlannerAgent"].append(part.strip())
        
        # If no specific agents were identified, route everything to PlannerAgent
        if not agent_tasks:
            agent_tasks["PlannerAgent"] = [task]
            
        return agent_tasks
    
    def _is_multi_location_weather_query(self, task: str) -> bool:
        """Check if task is a multi-location weather query."""
        task_lower = task.lower()
        
        # Must contain weather keywords
        has_weather = any(word in task_lower for word in ["weather", "temperature", "forecast", "climate"])
        if not has_weather:
            return False
        
        # Must have multiple locations (comma-separated or 'and' separated)
        has_multiple_locations = (',' in task and 
                                 any(word in task_lower for word in [' and ', ' or ']))
        
        return has_multiple_locations
    
    def _extract_multiple_locations(self, task: str) -> List[str]:
        """Extract multiple locations from a weather query."""
        import re
        
        # Remove weather keywords to focus on locations
        task_cleaned = task
        for word in ["what's", "weather", "temperature", "forecast", "climate", "check", "in", "for", "at"]:
            task_cleaned = re.sub(r'\b' + word + r'\b', ' ', task_cleaned, flags=re.IGNORECASE)
        
        # Split on common delimiters
        parts = re.split(r'[,;]|(?:\s+and\s+)|(?:\s+or\s+)', task_cleaned, flags=re.IGNORECASE)
        
        # Clean and filter locations
        locations = []
        for part in parts:
            location = part.strip().rstrip('?').strip()
            if location and len(location) > 1:
                # Remove common articles, prepositions, and extra whitespace
                location = re.sub(r'^\s*(the|a|an)\s+', '', location, flags=re.IGNORECASE)
                location = re.sub(r'\s+', ' ', location).strip()  # Normalize whitespace
                if location and location[0].isupper():  # Likely a proper noun (city name)
                    locations.append(location)
        
        return locations
    
    def _split_task_parts(self, task: str) -> List[str]:
        """Split task into individual parts for multi-agent processing."""
        import re
        
        # Split on common delimiters: -, and, comma, semicolon
        # Also split on phrases like "and then", "also", "plus"
        delimiters = r'[-,;]|(?:\s+and\s+)|(?:\s+also\s+)|(?:\s+plus\s+)|(?:\s+then\s+)'
        parts = re.split(delimiters, task, flags=re.IGNORECASE)
        
        # Clean up parts
        cleaned_parts = []
        for part in parts:
            cleaned = part.strip()
            if cleaned and len(cleaned) > 3:  # Ignore very short parts
                cleaned_parts.append(cleaned)
        
        return cleaned_parts
    
    def _extract_weather_task(self, part: str, full_task: str) -> str:
        """Extract and enhance weather-related task."""
        # Look for location mentions in both the part and full task
        import re
        
        # First, check if the part itself is just a location name (common in comma-separated lists)
        part_cleaned = part.strip().rstrip('?').strip()
        if part_cleaned and len(part_cleaned.split()) <= 3:  # Simple location name
            # Check if it looks like a city name (starts with capital)
            if part_cleaned[0].isupper():
                return f"Get weather information for {part_cleaned}"
        
        # Common location patterns
        location_patterns = [
            r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "in Seattle", "in New York"
            r'\bfor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', # "for Seattle"
            r'\bat\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',   # "at Seattle"
            r'(?:from|in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', # "from Seattle"
        ]
        
        location = None
        for pattern in location_patterns:
            match = re.search(pattern, full_task + " " + part)
            if match:
                location = match.group(1)
                break
        
        if location:
            return f"Get weather information for {location}"
        else:
            return f"Get current weather information"
    
    def _extract_calendar_task(self, part: str, full_task: str) -> str:
        """Extract and enhance calendar-related task."""
        part_lower = part.lower()
        
        if "schedule" in part_lower and ("meeting" in part_lower or "appointment" in part_lower):
            return f"Schedule a new meeting or appointment"
        elif "schedule" in part_lower:
            return f"Check my schedule and calendar"
        elif "meeting" in part_lower:
            return f"Handle meeting-related request: {part}"
        else:
            return f"Calendar task: {part}"
    
    def should_use_parallel_execution(self, task: str) -> bool:
        """
        Determine if a task should use parallel execution across multiple agents.
        
        Args:
            task: Task description
            
        Returns:
            True if task should be executed in parallel across multiple agents
        """
        task_lower = task.lower()
        
        # Indicators of multi-part tasks
        multi_indicators = ['-', ',', ';', ' and ', ' also ', ' plus ', ' then ']
        has_multiple_parts = any(indicator in task_lower for indicator in multi_indicators)
        
        # Multiple agent keywords
        agent_keywords = {
            'weather': ['weather', 'temperature', 'forecast', 'climate'],
            'calendar': ['calendar', 'schedule', 'meeting', 'appointment', 'event'],
            'general': ['plan', 'help', 'tell', 'joke', 'story', 'advice']
        }
        
        detected_categories = []
        for category, keywords in agent_keywords.items():
            if any(keyword in task_lower for keyword in keywords):
                detected_categories.append(category)
        
        # Use parallel if multiple categories detected or multiple parts
        return len(detected_categories) > 1 or has_multiple_parts


def create_default_workflow() -> Workflow:
    """
    Create the default multi-agent workflow for the MultiModal Assistant.
    
    Returns:
        Configured workflow with all available agents
    """
    # Create agent instances
    agents = [
        PlannerAgent(),
        WeatherAgent(),
        CalendarAgent()
    ]
    
    # Create workflow with star topology (planner orchestrates)
    workflow = Workflow(agents, topology="star")
    
    return workflow


# ADK-compatible helper functions
def create_workflow(agents: List[BaseAgent], topology: str = "star") -> Workflow:
    """Create a workflow with the specified agents and topology."""
    return Workflow(agents, topology)


async def execute_workflow(workflow: Workflow, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Execute a workflow with the given task."""
    return await workflow(task, context)