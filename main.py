#!/usr/bin/env python3
"""
Main application for MultiModal Assistant with multi-agent architecture.
Uses workflow orchestration, command bus, and streaming capabilities.
"""

import asyncio
import sys
import argparse
from typing import Dict, Any, Optional
from workflow import create_default_workflow, TaskRouter
from websocket_server import start_websocket_streaming
from bus import get_command_bus, ActionTypes
from agents import PlannerAgent, WeatherAgent, CalendarAgent


class MultiAgentAssistant:
    """
    Main assistant class using multi-agent architecture.
    Coordinates workflow execution, WebSocket streaming, and TTS.
    """
    
    def __init__(self):
        self.workflow = create_default_workflow()
        self.task_router = TaskRouter(self.workflow.agents)
        self.command_bus = None
        self.websocket_server_started = False
        
    async def initialize(self, enable_streaming=True, enable_audio=True):
        """Initialize the assistant systems."""
        print("🌟 Initializing MultiModal Assistant (Multi-Agent)")
        print("=" * 55)
        
        # Initialize command bus
        self.command_bus = await get_command_bus()
        print("✅ Command bus initialized")
        
        # Initialize audio pipeline
        if enable_audio:
            self._setup_audio_pipeline()
            print("✅ Audio pipeline connected")
        
        # Start streaming server if enabled
        if enable_streaming:
            try:
                # Start both WebSocket and SSE streaming in background
                asyncio.create_task(self._start_streaming_server())
                # Brief delay to let server start
                await asyncio.sleep(0.5)
                self.websocket_server_started = True
                print("✅ Streaming server started on http://localhost:8000")
                print("   📡 SSE endpoint: http://localhost:8000/stream")
                print("   🔌 WebSocket: ws://localhost:8000/ws")
                print("   📱 Dashboard: http://localhost:8000/dashboard")
            except Exception as e:
                print(f"⚠️ Streaming server not started: {e}")
                print("   (CLI mode only)")
        
        print("🤖 Agents loaded:")
        for agent_name in self.workflow.list_agents():
            agent = self.workflow.get_agent(agent_name)
            print(f"   • {agent_name}: {agent.description}")
        
        print("\n✨ Ready for conversations!")
        
    def _setup_audio_pipeline(self):
        """Set up the audio pipeline to convert speech events to actual audio."""
        import bus
        from gemini_client import GeminiClient
        from audio_handler import AudioHandler
        
        # Initialize audio components
        self.gemini_client = GeminiClient()
        self.audio_handler = AudioHandler()
        self.audio_queue = asyncio.Queue()
        self.audio_worker_started = False
        
        # Store original emit_speech function
        original_emit_speech = bus.emit_speech
        
        def audio_enabled_emit_speech(text: str, source: str = "unknown"):
            # Call original function to maintain event system
            result = original_emit_speech(text, source)
            
            # Add to audio queue for sequential processing
            try:
                self.audio_queue.put_nowait({"text": text, "source": source})
                
                # Start audio worker if not already started
                if not self.audio_worker_started:
                    asyncio.create_task(self._audio_worker())
                    self.audio_worker_started = True
                    
            except Exception as e:
                print(f"⚠️ Error queuing audio: {e}")
            
            return result
        
        # Replace emit_speech with audio-enabled version
        bus.emit_speech = audio_enabled_emit_speech
    
    async def _audio_worker(self):
        """Process audio queue sequentially to prevent overlapping speech."""
        print("🎵 Audio worker started")
        
        while True:
            try:
                # Get next audio item from queue
                audio_item = await self.audio_queue.get()
                text = audio_item["text"]
                source = audio_item["source"]
                
                print(f"🔊 Processing audio: [{source}] {text[:50]}...")
                
                # Generate and play audio
                await self._generate_and_play_audio(text, source)
                
                # Mark task as done
                self.audio_queue.task_done()
                
                # Brief pause between audio items to prevent overlap
                await asyncio.sleep(0.2)
                
            except Exception as e:
                print(f"⚠️ Audio worker error: {e}")
        
    async def _generate_and_play_audio(self, text: str, source: str):
        """Generate TTS audio and play it."""
        try:
            # Generate audio using Gemini TTS
            audio_data = self.gemini_client.generate_tts_audio(text)
            
            if audio_data:
                # Play audio using AudioHandler
                self.audio_handler.play_pcm_audio(audio_data)
                print(f"✅ Audio played: [{source}] {text[:30]}...")
            else:
                print(f"❌ No audio generated for: [{source}] {text[:30]}...")
            
        except Exception as e:
            print(f"⚠️ Audio generation error for [{source}]: {e}")
        
    async def _start_streaming_server(self):
        """Start the streaming server in the background."""
        try:
            from server import StreamingServer
            server = StreamingServer(self)
            await server.start(host="127.0.0.1", port=8000)
        except Exception as e:
            print(f"❌ Error starting streaming server: {e}")
        
    async def process_input(self, user_input: str) -> Dict[str, Any]:
        """
        Process user input through the multi-agent workflow.
        
        Args:
            user_input: User's input text
            
        Returns:
            Processing result
        """
        try:
            # Initialize command bus if needed
            if self.command_bus is None:
                self.command_bus = await get_command_bus()
            
            # Emit conversation start
            self.command_bus.emit(ActionTypes.UPDATE_STATUS, {
                "conversation": "started",
                "input": user_input[:100] + "..." if len(user_input) > 100 else user_input
            })
            
            # Route to appropriate workflow
            # For now, always use star topology with planner
            result = await self.workflow(user_input)
            
            # Emit conversation complete
            self.command_bus.emit(ActionTypes.UPDATE_STATUS, {
                "conversation": "completed",
                "success": "error" not in result
            })
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing input: {str(e)}"
            print(f"\n❌ {error_msg}")
            
            # Try to emit error if command bus is available
            if self.command_bus:
                self.command_bus.emit(ActionTypes.ERROR, {
                    "conversation": "failed",
                    "error": error_msg
                })
            
            return {"error": error_msg}
    
    async def run_interactive_session(self):
        """Run an interactive CLI session."""
        print("\n💬 Interactive mode started. Type 'quit' to exit.")
        print("   Commands:")
        print("   • 'agents' - List available agents")
        print("   • 'status' - Show system status")
        print("   • 'help' - Show this help")
        
        while True:
            try:
                user_input = input("\nUser > ").strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("\n👋 Goodbye!")
                    break
                    
                elif user_input.lower() == 'agents':
                    self._show_agents_status()
                    continue
                    
                elif user_input.lower() == 'status':
                    self._show_system_status()
                    continue
                    
                elif user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                # Process the input
                print("\n🤔 Processing...")
                result = await self.process_input(user_input)
                
                if "error" in result:
                    print(f"❌ Error: {result['error']}")
                else:
                    print("\n✨ Done!")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except EOFError:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
    
    def _show_agents_status(self):
        """Show status of all agents."""
        print("\n🤖 Agent Status:")
        for agent_name in self.workflow.list_agents():
            agent = self.workflow.get_agent(agent_name)
            status = "🟢 Active" if agent.is_active else "⚪ Idle"
            print(f"   {status} {agent_name}: {agent.description}")
    
    def _show_system_status(self):
        """Show overall system status."""
        print("\n📊 System Status:")
        print(f"   🔄 Command Bus: {'✅ Active' if self.command_bus else '❌ Inactive'}")
        print(f"   🌐 WebSocket: {'✅ Running' if self.websocket_server_started else '❌ Not started'}")
        print(f"   🤖 Agents: {len(self.workflow.list_agents())} loaded")
        print(f"   🏗️ Topology: {self.workflow.topology.value}")
    
    def _show_help(self):
        """Show help information."""
        print("\n📚 MultiModal Assistant Help:")
        print("   💬 Natural conversation:")
        print("      • 'What's the weather in Tokyo?'")
        print("      • 'Tell me a joke about programming'")
        print("      • 'What's on my schedule today?'")
        print("   🤖 Agent-specific queries:")
        print("      • Weather: temperature, forecast, conditions")
        print("      • Calendar: schedule, meetings, events")
        print("   ⚙️ System commands:")
        print("      • 'agents' - List agents")
        print("      • 'status' - System status")
        print("      • 'quit' - Exit")


async def run_single_query(query: str):
    """
    Run a single query and exit (useful for scripting).
    
    Args:
        query: The query to process
    """
    assistant = MultiAgentAssistant()
    await assistant.initialize()
    
    print(f"\nUser > {query}")
    result = await assistant.process_input(query)
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        sys.exit(1)
    else:
        print("\n✨ Query completed successfully!")


async def run_demo_mode():
    """Run comprehensive multi-agent coordination demo."""
    print("🎯 MultiModal Assistant - Multi-Agent Coordination Demo")
    print("=" * 60)
    
    assistant = MultiAgentAssistant()
    await assistant.initialize()
    
    demo_scenarios = [
        {
            "name": "Complex Sequential Task",
            "query": "Plan my day - check weather for my morning run in Central Park, schedule a team meeting for 2 PM, and tell me a joke to start the day",
            "description": "Tests WeatherAgent → CalendarAgent → PlannerAgent coordination"
        },
        {
            "name": "Weather Multi-City Query", 
            "query": "What's the weather in Tokyo, London, and New York?",
            "description": "Tests parallel processing and response coordination"
        },
        {
            "name": "Calendar Management",
            "query": "What's on my schedule today and add a coffee break at 3 PM",
            "description": "Tests CalendarAgent read and write operations"
        },
        {
            "name": "Error Handling Test",
            "query": "Check weather for XYZ123InvalidCity and tell me about quantum computing",
            "description": "Tests graceful error handling and partial responses"
        }
    ]
    
    for i, scenario in enumerate(demo_scenarios, 1):
        print(f"\n🧪 Demo {i}/4: {scenario['name']}")
        print(f"📝 {scenario['description']}")
        print(f"🗣️  Query: '{scenario['query']}'")
        print("─" * 50)
        
        try:
            result = await assistant.process_input(scenario['query'])
            
            if "error" in result:
                print(f"⚠️  Demo completed with error: {result['error']}")
            else:
                print("✅ Demo scenario completed successfully")
                
            # Wait between scenarios to avoid overwhelming output
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"❌ Demo scenario failed: {e}")
    
    print("\n🎉 Multi-Agent Coordination Demo Complete!")
    print("📊 Check WebSocket dashboard at http://localhost:8000 for real-time events")


async def run_websocket_only():
    """Run only the WebSocket server for external integration."""
    print("🌐 Starting WebSocket Server Only")
    print("=" * 40)
    
    try:
        # Initialize command bus
        await get_command_bus()
        print("✅ Command bus initialized")
        
        # Start WebSocket streaming
        await start_websocket_streaming()
        print("✅ WebSocket server running on http://localhost:8000")
        print("📱 Visit http://localhost:8000 for real-time dashboard")
        print("🔌 WebSocket endpoint: ws://localhost:8000/ws")
        
        # Keep running
        print("\n⏳ Server running... Press Ctrl+C to stop")
        await asyncio.Future()  # Run forever
        
    except KeyboardInterrupt:
        print("\n👋 WebSocket server stopped")
    except Exception as e:
        print(f"❌ WebSocket server error: {e}")
        sys.exit(1)


async def run_streaming_mode():
    """Run in streaming mode with FastAPI SSE server and multi-agent coordination."""
    print("🚀 Starting MultiModal Assistant - Streaming Mode")
    print("=" * 50)
    
    try:
        # Initialize command bus
        await get_command_bus()
        print("✅ Command bus initialized")
        
        # Initialize assistant
        assistant = MultiAgentAssistant()
        await assistant.initialize()
        
        # Start FastAPI streaming server
        from server import StreamingServer
        server = StreamingServer(assistant)
        
        print("🌊 FastAPI streaming server starting...")
        print("📡 SSE endpoint: http://localhost:8000/stream")
        print("🎵 Audio WebSocket: ws://localhost:8000/ws/audio")
        print("📊 Dashboard: http://localhost:8000/dashboard")
        print("🔗 Health check: http://localhost:8000/health")
        
        # Run the FastAPI server
        await server.start()
        
    except KeyboardInterrupt:
        print("\n👋 Streaming server stopped")
    except Exception as e:
        print(f"❌ Streaming server error: {e}")
        sys.exit(1)


def create_parser():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="MultiModal Assistant - Multi-Agent Conversational AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           # Interactive mode
  python main.py "Hello world"             # Single query
  python main.py --demo                    # Multi-agent coordination demo
  python main.py --websocket-only          # WebSocket server only
  
Multi-Agent Queries:
  python main.py "Plan my day - check weather for my run, schedule a meeting, tell me a joke"
  python main.py "What's the weather in Tokyo, London, and Paris?"
  python main.py "What's on my schedule today and add a coffee break?"
        """
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--demo",
        action="store_true",
        help="Run comprehensive multi-agent coordination demo"
    )
    group.add_argument(
        "--websocket-only",
        action="store_true",
        help="Run only WebSocket server for external integration"
    )
    group.add_argument(
        "--streaming-mode",
        action="store_true", 
        help="Run in streaming mode with FastAPI SSE server"
    )
    
    parser.add_argument(
        "query",
        nargs="*",
        help="Single query to process (if no flags specified)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser


async def main():
    """Main entry point with CLI argument handling."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Configure logging if verbose
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.INFO)
    
    try:
        if args.demo:
            # Run multi-agent coordination demo
            await run_demo_mode()
            
        elif args.websocket_only:
            # Run WebSocket server only
            await run_websocket_only()
            
        elif args.streaming_mode:
            # Run in streaming mode with FastAPI SSE server
            await run_streaming_mode()
            
        elif args.query:
            # Single query mode
            query = " ".join(args.query)
            await run_single_query(query)
            
        else:
            # Interactive mode (default)
            assistant = MultiAgentAssistant()
            await assistant.initialize()
            await assistant.run_interactive_session()
            
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Handle Windows event loop policy
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())