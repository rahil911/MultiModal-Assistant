#!/usr/bin/env python3
"""
Main application for multimodal assistant.
Orchestrates the conversation flow with text, audio, and tool calls.
"""

from typing import List, Dict, Any
from config import SYSTEM_MESSAGE
from audio_handler import AudioHandler
from gemini_client import GeminiClient


class MultimodalAssistant:
    """Main assistant class that orchestrates multimodal conversations."""
    
    def __init__(self):
        self.audio_handler = AudioHandler()
        self.gemini_client = GeminiClient()
        self.conversation_history: List[Dict[str, Any]] = []
    
    def initialize_conversation(self, user_prompt: str) -> None:
        """Initialize the conversation with system message and user prompt."""
        self.gemini_client.initialize_chat(SYSTEM_MESSAGE)
        self.conversation_history = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": user_prompt}
        ]
    
    def process_initial_message(self, user_prompt: str) -> tuple:
        """
        Process the initial message from the user.
        
        Args:
            user_prompt: The user's input
            
        Returns:
            Tuple of (response_text, function_name, function_args)
        """
        print("🤖 Assistant: ", end="", flush=True)
        
        # Send message to Gemini
        response_text, function_name, function_args = self.gemini_client.send_message_with_streaming(user_prompt)
        
        # Print the response
        if response_text:
            print(response_text)
        
        return response_text, function_name, function_args
    
    def process_tool_call(self, function_name: str, function_args: str) -> str:
        """Process and execute a tool call, then get the follow-up response."""
        try:
            # Execute the tool
            tool_result = self.gemini_client.execute_tool_call(function_name, function_args)
            
            # Send tool result back to Gemini and get final response
            final_response = self.gemini_client.send_tool_result(function_name, function_args, tool_result)
            
            print(f"🤖 {final_response}")
            
            # Add to conversation history
            self.conversation_history.extend([
                {"role": "assistant", "content": f"Used tool {function_name} with result: {tool_result}"},
                {"role": "assistant", "content": final_response}
            ])
            
            return final_response
            
        except Exception as e:
            print(f"❌ Error fetching information: {e}")
            return None
    
    def generate_and_play_audio(self, text: str) -> None:
        """
        Generate and play audio using Gemini 2.5 native TTS.
        """
        print("🎵 Generating speech...")
        
        try:
            # Generate audio using Gemini 2.5 TTS
            audio_data = self.gemini_client.generate_tts_audio(text)
            
            if audio_data:
                # Convert base64 to PCM data and play directly
                self.audio_handler.play_pcm_audio(audio_data)
            else:
                print("⚠️  Could not generate audio")
                
        except Exception as e:
            print(f"❌ Error with audio: {e}")
    
    def run_conversation(self, user_prompt: str) -> None:
        """
        Run a complete conversation cycle.
        
        Args:
            user_prompt: The user's input prompt
        """
        try:
            # Initialize conversation
            self.initialize_conversation(user_prompt)
            
            # Process initial message
            response_text, function_name, function_args = self.process_initial_message(user_prompt)
            
            # Handle tool calls if present
            if function_name and function_args:
                # Generate audio for the initial response first
                if response_text:
                    self.generate_and_play_audio(response_text)
                
                # Announce what tool will be used
                import json
                args = json.loads(function_args)
                if function_name == "get_current_weather":
                    print(f"🌤️  Fetching current weather for {args.get('location', 'the requested location')}...")
                else:
                    print(f"🔧 Using {function_name} to get the information...")
                
                final_response = self.process_tool_call(function_name, function_args)
                
                # Generate and play audio for the final response
                if final_response:
                    self.generate_and_play_audio(final_response)
            else:
                # No tool call, just generate audio for the response
                if response_text:
                    self.generate_and_play_audio(response_text)
            
            print("\n✨ Done!")
            
        except Exception as e:
            print(f"\n❌ Error in conversation: {e}")
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the current conversation history."""
        return self.conversation_history


def main():
    """Main entry point for the application."""
    print("🌟 Multimodal Assistant (Powered by Gemini)")
    print("=" * 55)
    
    assistant = MultimodalAssistant()
    
    try:
        user_prompt = input("User > ")
        assistant.run_conversation(user_prompt)
        
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main() 