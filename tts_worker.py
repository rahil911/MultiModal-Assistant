#!/usr/bin/env python3
"""
TTS Worker with Piper integration for local, streaming text-to-speech.
Provides low-latency audio generation as an alternative to Gemini TTS.
"""

import asyncio
import websockets
import json
import logging
from typing import Optional, AsyncGenerator
import wave
import io
from bus import get_command_bus, ActionTypes

# Note: Piper TTS integration will require actual piper-tts installation
# For now, we'll create the infrastructure and use a mock implementation


class PiperTTSWorker:
    """
    Local TTS worker using Piper for high-quality, low-latency speech synthesis.
    Streams PCM audio chunks over WebSocket for real-time playback.
    """
    
    def __init__(self, model_path: str = "en_US-libritts_r-medium", host: str = "localhost", port: int = 8766):
        self.model_path = model_path
        self.host = host
        self.port = port
        self.model = None
        self.clients = set()
        self.sentence_buffer = ""
        self.command_bus = None
        
    async def start(self):
        """Start the TTS worker server."""
        try:
            # Initialize Piper model (mock for now)
            await self._load_model()
            
            # Connect to command bus
            self.command_bus = await get_command_bus()
            
            # Start WebSocket server
            server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port
            )
            
            print(f"🎵 TTS Worker started on ws://{self.host}:{self.port}")
            
            # Start command bus listener
            asyncio.create_task(self._listen_for_speech_requests())
            
            return server
            
        except Exception as e:
            print(f"❌ Error starting TTS worker: {e}")
            raise
    
    async def _load_model(self):
        """Load the Piper TTS model."""
        try:
            # Mock implementation - in production, use actual Piper
            print(f"📦 Loading Piper model: {self.model_path}")
            
            # Actual Piper integration would look like:
            # import piper
            # self.model = piper.load(self.model_path)
            
            # For now, use mock
            self.model = MockPiperModel()
            print("✅ Piper model loaded successfully")
            
        except Exception as e:
            print(f"❌ Error loading Piper model: {e}")
            # Fallback to mock
            self.model = MockPiperModel()
    
    async def handle_client(self, websocket, path):
        """Handle WebSocket client connections."""
        self.clients.add(websocket)
        client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        print(f"🔌 TTS client connected: {client_addr}")
        
        try:
            async for message in websocket:
                await self._process_client_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            print(f"🔌 TTS client disconnected: {client_addr}")
        finally:
            self.clients.discard(websocket)
    
    async def _process_client_message(self, websocket, message: str):
        """Process incoming messages from TTS clients."""
        try:
            data = json.loads(message)
            action = data.get("action")
            
            if action == "synthesize":
                text = data.get("text", "")
                await self._synthesize_and_stream(text, websocket)
                
            elif action == "stop":
                # Stop current synthesis
                pass
                
        except json.JSONDecodeError:
            print(f"⚠️ Invalid JSON from TTS client: {message}")
        except Exception as e:
            print(f"❌ Error processing TTS client message: {e}")
    
    async def _listen_for_speech_requests(self):
        """Listen for speech requests from the command bus."""
        if not self.command_bus:
            return
            
        subscriber_queue = self.command_bus.subscribe()
        
        try:
            while True:
                action_json = await subscriber_queue.get()
                action_data = json.loads(action_json)
                
                if action_data.get("action") == ActionTypes.SPEAK:
                    text = action_data.get("data", {}).get("text", "")
                    if text:
                        await self._synthesize_and_broadcast(text)
                        
        except Exception as e:
            print(f"❌ Error in TTS command bus listener: {e}")
        finally:
            self.command_bus.unsubscribe(subscriber_queue)
    
    async def _synthesize_and_broadcast(self, text: str):
        """Synthesize text and broadcast to all connected clients."""
        if not self.clients:
            return
            
        clients_copy = list(self.clients)
        await asyncio.gather(
            *[self._synthesize_and_stream(text, client) for client in clients_copy],
            return_exceptions=True
        )
    
    async def _synthesize_and_stream(self, text: str, websocket):
        """
        Synthesize text to speech and stream PCM chunks.
        
        Args:
            text: Text to synthesize
            websocket: WebSocket to stream to
        """
        try:
            # Send synthesis start notification
            await websocket.send(json.dumps({
                "type": "synthesis_start",
                "text": text[:100] + "..." if len(text) > 100 else text
            }))
            
            # Process text sentence by sentence for lower latency
            sentences = self._split_into_sentences(text)
            
            for sentence in sentences:
                if sentence.strip():
                    # Generate audio for this sentence
                    async for audio_chunk in self._synthesize_sentence(sentence):
                        # Send PCM audio chunk
                        await websocket.send(audio_chunk)
            
            # Send completion notification
            await websocket.send(json.dumps({
                "type": "synthesis_complete",
                "text": text
            }))
            
        except websockets.exceptions.ConnectionClosed:
            self.clients.discard(websocket)
        except Exception as e:
            print(f"❌ Error in TTS synthesis: {e}")
    
    def _split_into_sentences(self, text: str) -> list:
        """Split text into sentences for streaming synthesis."""
        import re
        # Simple sentence splitting - in production, use more sophisticated methods
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    async def _synthesize_sentence(self, sentence: str) -> AsyncGenerator[bytes, None]:
        """
        Synthesize a single sentence and yield audio chunks.
        
        Args:
            sentence: Sentence to synthesize
            
        Yields:
            PCM audio chunks as bytes
        """
        if not self.model:
            return
            
        try:
            # Use Piper model to generate audio chunks
            # This would be the actual Piper integration:
            # for audio_chunk in self.model.stream(sentence):
            #     yield audio_chunk
            
            # Mock implementation for now
            async for chunk in self.model.stream(sentence):
                yield chunk
                
        except Exception as e:
            print(f"❌ Error synthesizing sentence '{sentence}': {e}")


class MockPiperModel:
    """Mock Piper model for testing without actual Piper installation."""
    
    def __init__(self):
        self.sample_rate = 22050
        self.chunk_size = 1024  # ~46ms at 22kHz
        
    async def stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Mock streaming synthesis - generates silence."""
        # Calculate approximate duration (assume 150 WPM reading speed)
        words = len(text.split())
        duration_seconds = max(0.5, words / 2.5)  # Minimum 0.5s
        
        # Generate chunks of silence as placeholder
        total_samples = int(duration_seconds * self.sample_rate)
        chunks_needed = (total_samples + self.chunk_size - 1) // self.chunk_size
        
        for i in range(chunks_needed):
            # Generate chunk of silence (16-bit PCM)
            chunk_samples = min(self.chunk_size, total_samples - (i * self.chunk_size))
            silence_chunk = b'\x00\x00' * chunk_samples  # 16-bit silence
            
            # Simulate processing time (~40ms per chunk)
            await asyncio.sleep(0.04)
            yield silence_chunk


class TTSConfig:
    """Configuration for TTS worker."""
    
    # Piper model configurations
    MODELS = {
        "fast": "en_US-amy-low",           # ~25MB, very fast
        "medium": "en_US-libritts_r-medium",  # ~40MB, good quality
        "high": "en_US-libritts_r-high"    # ~100MB, best quality
    }
    
    # Audio settings
    SAMPLE_RATE = 22050
    CHANNELS = 1
    SAMPLE_WIDTH = 2  # 16-bit
    
    # Streaming settings
    CHUNK_DURATION_MS = 50  # 50ms chunks for low latency
    SENTENCE_BUFFER_SIZE = 1000  # Max characters before forcing synthesis


async def main():
    """Main entry point for TTS worker."""
    logging.basicConfig(level=logging.INFO)
    
    # Create and start TTS worker
    tts_worker = PiperTTSWorker(
        model_path=TTSConfig.MODELS["medium"],
        host="0.0.0.0",
        port=8766
    )
    
    try:
        server = await tts_worker.start()
        print("🎵 TTS Worker is running. Press Ctrl+C to stop.")
        
        # Keep running
        await asyncio.Future()  # Run forever
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down TTS Worker...")
    except Exception as e:
        print(f"❌ TTS Worker error: {e}")


if __name__ == "__main__":
    asyncio.run(main())