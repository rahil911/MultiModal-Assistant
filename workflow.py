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
    Analyzes tasks and routes to the best-suited agent.
    """
    
    def __init__(self, agents: Dict[str, BaseAgent]):
        self.agents = agents
        
    def route_task(self, task: str) -> str:
        """
        Route a task to the most appropriate agent.
        
        Args:
            task: Task description
            
        Returns:
            Name of the best-suited agent
        """
        task_lower = task.lower()
        
        # Simple keyword-based routing
        # In production, use ML models for better routing
        if any(word in task_lower for word in ["weather", "temperature", "forecast", "climate"]):
            return "WeatherAgent"
        
        elif any(word in task_lower for word in ["calendar", "schedule", "meeting", "appointment", "event"]):
            return "CalendarAgent"
        
        else:
            # Default to planner for general queries
            return "PlannerAgent"


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