#!/usr/bin/env python3
"""
Planner Agent for the MultiModal Assistant.
Refactored from main.py to use ADK and command bus architecture.
"""

from typing import Dict, Any, Optional
import json
from .base_agent import BaseAgent
from gemini_client import GeminiClient
from audio_handler import AudioHandler
from bus import ActionTypes


class PlannerAgent(BaseAgent):
    """
    Main planner agent that orchestrates conversations and delegates to other agents.
    This agent contains the core conversation logic from the original main.py.
    """
    
    def __init__(self):
        super().__init__(
            name="PlannerAgent",
            description="Main orchestrator for conversations, tool routing, and audio generation"
        )
        self.gemini_client = GeminiClient()
        self.audio_handler = AudioHandler()
        self.conversation_history = []
        
    async def run(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a conversation task.
        
        Args:
            task: User's input/prompt
            context: Additional context for the conversation
            
        Returns:
            Result dictionary with response and any function calls
        """
        await self.notify_start(f"Processing: {task[:50]}...")
        
        try:
            # Initialize conversation
            self._initialize_conversation(task)
            
            # Process initial message 
            response_data = await self._process_initial_message(task)
            
            # Handle tool calls if present
            if response_data.get("function_name") and response_data.get("function_args"):
                tool_result = await self._process_tool_call(
                    response_data["function_name"],
                    response_data["function_args"],
                    response_data["response_text"]
                )
                response_data.update(tool_result)
            else:
                # No tool call, generate audio for direct response
                if response_data.get("response_text"):
                    await self._generate_and_announce_audio(response_data["response_text"])
            
            await self.notify_complete(response_data)
            return response_data
            
        except Exception as e:
            error_msg = f"Error in conversation: {str(e)}"
            await self.notify_error(error_msg)
            return {"error": error_msg}
    
    def _initialize_conversation(self, user_prompt: str):
        """Initialize the conversation with system message and user prompt."""
        from config import SYSTEM_MESSAGE
        
        self.gemini_client.initialize_chat(SYSTEM_MESSAGE)
        self.conversation_history = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": user_prompt}
        ]
        
    async def _process_initial_message(self, user_prompt: str) -> Dict[str, Any]:
        """
        Process the initial message from the user.
        
        Args:
            user_prompt: The user's input
            
        Returns:
            Dictionary with response_text, function_name, function_args
        """
        await self.notify_progress("Thinking...")
        
        # Emit that we're starting to process
        await self.emit(ActionTypes.UPDATE_STATUS, {
            "message": "Processing your request...",
            "stage": "thinking"
        })
        
        # Send message to Gemini
        response_text, function_name, function_args = self.gemini_client.send_message_with_streaming(user_prompt)
        
        # Emit the assistant's response
        if response_text:
            await self.emit(ActionTypes.SPEAK, {
                "text": response_text,
                "priority": "high",
                "stage": "initial_response"
            })
        
        return {
            "response_text": response_text,
            "function_name": function_name,
            "function_args": function_args
        }
    
    async def _process_tool_call(self, function_name: str, function_args: str, initial_response: str) -> Dict[str, Any]:
        """Process and execute a tool call, then get the follow-up response."""
        try:
            # Generate audio for initial response first
            if initial_response:
                await self._generate_and_announce_audio(initial_response)
            
            # Announce what tool will be used
            args = json.loads(function_args)
            if function_name == "get_current_weather":
                tool_message = f"Fetching current weather for {args.get('location', 'the requested location')}..."
                await self.emit(ActionTypes.SHOW_PROGRESS, {
                    "message": tool_message,
                    "tool": function_name,
                    "args": args
                })
            else:
                tool_message = f"Using {function_name} to get the information..."
                await self.emit(ActionTypes.SHOW_PROGRESS, {
                    "message": tool_message,
                    "tool": function_name
                })
            
            await self.notify_progress(tool_message)
            
            # Emit tool start event
            await self.emit(ActionTypes.TOOL_START, {
                "function_name": function_name,
                "arguments": args
            })
            
            # Execute the tool
            tool_result = self.gemini_client.execute_tool_call(function_name, function_args)
            
            # Emit tool completion
            await self.emit(ActionTypes.TOOL_COMPLETE, {
                "function_name": function_name,
                "result": tool_result
            })
            
            # Send tool result back to Gemini and get final response
            final_response = self.gemini_client.send_tool_result(function_name, function_args, tool_result)
            
            # Emit final response
            if final_response:
                await self.emit(ActionTypes.SPEAK, {
                    "text": final_response,
                    "priority": "high",
                    "stage": "final_response"
                })
            
            # Generate and announce audio for final response
            if final_response:
                await self._generate_and_announce_audio(final_response)
            
            # Add to conversation history
            self.conversation_history.extend([
                {"role": "assistant", "content": f"Used tool {function_name} with result: {tool_result}"},
                {"role": "assistant", "content": final_response}
            ])
            
            return {
                "final_response": final_response,
                "tool_result": tool_result
            }
            
        except Exception as e:
            error_msg = f"Error executing tool {function_name}: {str(e)}"
            await self.notify_error(error_msg)
            await self.emit(ActionTypes.ERROR, {
                "message": error_msg,
                "tool": function_name
            })
            return {"error": error_msg}
    
    async def _generate_and_announce_audio(self, text: str):
        """
        Generate and announce audio generation for the given text.
        
        Args:
            text: Text to convert to speech
        """
        # Emit audio generation start
        await self.emit(ActionTypes.AUDIO_START, {
            "text": text[:100] + "..." if len(text) > 100 else text
        })
        
        try:
            # Generate audio using Gemini 2.5 TTS
            audio_data = self.gemini_client.generate_tts_audio(text)
            
            if audio_data:
                # Convert and play audio
                self.audio_handler.play_pcm_audio(audio_data)
                
                # Emit audio completion
                await self.emit(ActionTypes.AUDIO_COMPLETE, {
                    "text": text[:100] + "..." if len(text) > 100 else text,
                    "success": True
                })
            else:
                await self.emit(ActionTypes.ERROR, {
                    "message": "Could not generate audio",
                    "context": "tts_generation"
                })
                
        except Exception as e:
            error_msg = f"Error with audio generation: {str(e)}"
            await self.emit(ActionTypes.ERROR, {
                "message": error_msg,
                "context": "audio_processing"
            })
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return capabilities of this agent."""
        return {
            **super().get_capabilities(),
            "functions": [
                "process_conversations",
                "generate_audio",
                "execute_tool_calls",
                "manage_conversation_history"
            ],
            "tools": ["gemini_api", "tts", "function_calling"],
            "conversation_length": len(self.conversation_history)
        }
    
    def get_conversation_history(self):
        """Get the current conversation history."""
        return self.conversation_history