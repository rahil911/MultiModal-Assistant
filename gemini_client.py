#!/usr/bin/env python3
"""
Gemini client wrapper for multimodal assistant.
"""

import json
import base64
import google.generativeai as genai
from google import genai as google_genai
from google.genai import types
from typing import List, Dict, Any, Tuple, Optional
from config import GEMINI_API_KEY, MODEL_NAME, TTS_MODEL_NAME, GENERATION_CONFIG, TTS_CONFIG
from tools import TOOLS_SPEC, execute_function
from bus import emit_token, emit_speech, emit_status, StreamingEventTypes


class GeminiClient:
    """Wrapper for Gemini API interactions."""
    
    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(MODEL_NAME)
        # Create client for TTS  
        self.genai_client = google_genai.Client(api_key=GEMINI_API_KEY)
        self.chat = None
        self.function_call_schema = self._create_function_call_schema()
    
    def _create_function_call_schema(self) -> Dict[str, Any]:
        """Create structured output schema for function calls."""
        # Get available functions from TOOLS_SPEC
        available_functions = []
        function_schemas = {}
        
        for tool in TOOLS_SPEC:
            if tool["type"] == "function":
                func_def = tool["function"]
                func_name = func_def["name"]
                available_functions.append(func_name)
                
                # Create parameter schema for this function
                parameters = func_def["parameters"]
                function_schemas[func_name] = {
                    "type": "object",
                    "properties": parameters.get("properties", {}),
                    "required": parameters.get("required", [])
                }
        
        # Define the structured output schema
        schema = {
            "type": "object",
            "properties": {
                "needs_function_call": {
                    "type": "boolean",
                    "description": "Whether a function call is needed to answer the user's question"
                },
                "response": {
                    "type": "string", 
                    "description": "Your direct response to the user (always provide this)"
                },
                "function_call": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "enum": available_functions,
                            "description": f"Function to call. Available: {', '.join(available_functions)}"
                        },
                        "arguments": {
                            "type": "object",
                            "properties": {
                                "location": {
                                    "type": "string",
                                    "description": "Location for weather query"
                                }
                            }
                        }
                    },
                    "required": ["name", "arguments"]
                }
            },
            "required": ["needs_function_call", "response"]
        }
        
        return schema
    
    def initialize_chat(self, system_message: str) -> None:
        """Initialize chat (not needed for structured outputs, kept for compatibility)."""
        # With structured outputs, we don't need persistent chat sessions
        # System message is included in each request
        pass
    
    async def send_message_with_token_streaming(self, message: str, source: str = "GeminiClient") -> Tuple[str, Optional[str], Optional[str]]:
        """
        Send a message with real-time token streaming.
        
        Args:
            message: User message to send
            source: Source identifier for streaming events
            
        Returns:
            Tuple of (response_text, function_name, function_args)
        """
        try:
            # Emit status that we're starting to think
            emit_status("Processing your request...", source=source)
            
            # Create system prompt with available functions info
            available_functions = [tool["function"]["name"] for tool in TOOLS_SPEC if tool["type"] == "function"]
            function_descriptions = []
            for tool in TOOLS_SPEC:
                if tool["type"] == "function":
                    func = tool["function"]
                    function_descriptions.append(f"- {func['name']}: {func['description']}")
            
            system_context = f"""You are a helpful AI assistant.

Available functions:
{chr(10).join(function_descriptions)}

Instructions:
- ALWAYS provide a response in the "response" field
- If the user's question requires external data (like weather), set needs_function_call to true and specify the function call
- If you can answer directly (like jokes, general questions), set needs_function_call to false
- Be helpful and conversational in your responses"""
            
            full_prompt = f"{system_context}\n\nUser: {message}"
            
            # Use streaming with structured output
            response_stream = self.model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=self.function_call_schema,
                    **GENERATION_CONFIG
                ),
                stream=True
            )
            
            # Collect streaming tokens
            full_text = ""
            for chunk in response_stream:
                if chunk.text:
                    # Emit individual tokens for real-time rendering
                    emit_token(chunk.text, source=source)
                    full_text += chunk.text
            
            # Parse the complete structured JSON response
            try:
                result = json.loads(full_text)
                
                # Always get the response text
                response_text = result.get("response", "")
                needs_function_call = result.get("needs_function_call", False)
                
                # Emit the complete speech for TTS
                if response_text:
                    emit_speech(response_text, source=source)
                
                if needs_function_call and "function_call" in result:
                    function_call = result["function_call"]
                    function_name = function_call.get("name")
                    function_args = json.dumps(function_call.get("arguments", {}))
                    return response_text, function_name, function_args
                else:
                    # No function call needed, just return the response
                    return response_text, None, None
                    
            except json.JSONDecodeError as e:
                print(f"Error parsing structured response: {e}")
                return f"Error parsing response: {full_text}", None, None
            
        except Exception as e:
            print(f"Error in Gemini API streaming call: {e}")
            return f"Error: {str(e)}", None, None

    def send_message_with_streaming(self, message: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Send a message and get structured response.
        
        Args:
            message: User message to send
            
        Returns:
            Tuple of (response_text, function_name, function_args)
        """
        try:
            # Create system prompt with available functions info
            available_functions = [tool["function"]["name"] for tool in TOOLS_SPEC if tool["type"] == "function"]
            function_descriptions = []
            for tool in TOOLS_SPEC:
                if tool["type"] == "function":
                    func = tool["function"]
                    function_descriptions.append(f"- {func['name']}: {func['description']}")
            
            system_context = f"""You are a helpful AI assistant.

Available functions:
{chr(10).join(function_descriptions)}

Instructions:
- ALWAYS provide a response in the "response" field
- If the user's question requires external data (like weather), set needs_function_call to true and specify the function call
- If you can answer directly (like jokes, general questions), set needs_function_call to false
- Be helpful and conversational in your responses"""
            
            full_prompt = f"{system_context}\n\nUser: {message}"
            
            # Use structured output with schema
            response = self.model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=self.function_call_schema,
                    **GENERATION_CONFIG
                )
            )
            
            # Parse the structured JSON response
            try:
                result = json.loads(response.text)
                
                # Always get the response text
                response_text = result.get("response", "")
                needs_function_call = result.get("needs_function_call", False)
                
                if needs_function_call and "function_call" in result:
                    function_call = result["function_call"]
                    function_name = function_call.get("name")
                    function_args = json.dumps(function_call.get("arguments", {}))
                    return response_text, function_name, function_args
                else:
                    # No function call needed, just return the response
                    return response_text, None, None
                    
            except json.JSONDecodeError as e:
                print(f"Error parsing structured response: {e}")
                return f"Error parsing response: {response.text}", None, None
            
        except Exception as e:
            print(f"Error in Gemini API call: {e}")
            return f"Error: {str(e)}", None, None
    
    def execute_tool_call(self, function_name: str, function_args: str) -> Any:
        """
        Execute a tool call and return the result.
        
        Args:
            function_name: Name of the function to call
            function_args: JSON string of function arguments
            
        Returns:
            Result of the function execution
        """
        args_dict = json.loads(function_args or "{}")
        return execute_function(function_name, **args_dict)
    
    def send_tool_result(self, function_name: str, function_args: str, tool_result: Any) -> str:
        """
        Generate final response based on tool result.
        
        Args:
            function_name: Name of the function that was called
            function_args: Arguments that were passed
            tool_result: Result from the function
            
        Returns:
            Final response text from the model
        """
        try:
            # Parse function arguments
            args_dict = json.loads(function_args or "{}")
            
            # Create prompt with tool result
            prompt = f"""I called the function '{function_name}' with arguments {args_dict} and got this result:
{json.dumps(tool_result, indent=2)}

Please provide a helpful response to the user based on this information. Be natural and conversational."""
            
            # Generate response without structured output (just normal text)
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(**GENERATION_CONFIG)
            )
            
            return response.text.strip()
            
        except Exception as e:
            print(f"Error generating final response: {e}")
            return f"I received the data but encountered an error: {str(e)}"
    
    def get_chat_history(self) -> List[Dict[str, Any]]:
        """Get the current chat history (not used with structured outputs)."""
        # With structured outputs, we don't maintain persistent chat history
        # Each request is independent
        return []
    
    def generate_tts_audio(self, text: str) -> bytes:
        """
        Generate audio from text using Gemini 2.5 TTS.
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Audio data as bytes
        """
        try:
            response = self.genai_client.models.generate_content(
                model=TTS_MODEL_NAME,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=TTS_CONFIG["speech_config"]["voice_config"]["prebuilt_voice_config"]["voice_name"]
                            )
                        )
                    )
                )
            )
            
            # Extract audio data from response
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data'):
                                # The data is already binary audio data, not base64
                                return part.inline_data.data
            
            print(f"⚠️  No audio data found in TTS response for: '{text[:50]}...'")
            return None
            
        except Exception as e:
            print(f"❌ Error generating audio: {e}")
            return None 