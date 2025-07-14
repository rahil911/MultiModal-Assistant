#!/usr/bin/env python3
"""
Audio dispatcher for real-time TTS streaming.
Bridges the command bus to TTS worker with sentence-boundary chunking.
"""

import asyncio
import json
import re
import logging
import websockets
from typing import Optional, Set
from bus import get_command_bus, StreamingEventTypes, split_into_sentences
from server import get_streaming_server


class AudioDispatcher:
    """
    Bridges command bus speech events to TTS worker for real-time audio streaming.
    Handles sentence boundary detection and streaming coordination.
    """
    
    def __init__(self, tts_worker_url: str = "ws://localhost:8766"):
        self.tts_worker_url = tts_worker_url
        self.command_bus = None
        self.tts_connection = None
        self.streaming_server = None
        self.text_buffer = ""
        self.running = False
        
        # Sentence boundary pattern for chunking
        self.sentence_pattern = re.compile(r'[.!?]\s+')
        
    async def start(self):
        """Start the audio dispatcher."""
        self.running = True
        
        # Initialize connections
        self.command_bus = await get_command_bus()
        self.streaming_server = get_streaming_server()
        
        # Start main processing loop
        await asyncio.gather(
            self._connect_to_tts_worker(),
            self._process_speech_events(),
            return_exceptions=True
        )
    
    async def stop(self):
        """Stop the audio dispatcher."""
        self.running = False
        
        if self.tts_connection:
            await self.tts_connection.close()
    
    async def _connect_to_tts_worker(self):
        """Maintain connection to TTS worker with auto-reconnect."""
        while self.running:
            try:
                print(f"🎵 Connecting to TTS worker at {self.tts_worker_url}")
                
                async with websockets.connect(self.tts_worker_url) as websocket:
                    self.tts_connection = websocket
                    print("✅ Connected to TTS worker")
                    
                    # Listen for audio frames from TTS worker
                    await self._handle_audio_frames(websocket)
                    
            except websockets.exceptions.ConnectionClosed:
                print("🔌 TTS worker connection closed")
            except Exception as e:
                print(f"❌ TTS worker connection error: {e}")
            
            if self.running:
                print("⏳ Retrying TTS worker connection in 5 seconds...")
                await asyncio.sleep(5)
    
    async def _handle_audio_frames(self, websocket):
        """Handle incoming audio frames from TTS worker."""
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    # Received PCM audio frame, broadcast to clients
                    if self.streaming_server:
                        await self.streaming_server.broadcast_audio(message)
                else:
                    # Received text message (status/control)
                    try:
                        data = json.loads(message)
                        if data.get("type") == "synthesis_complete":
                            print(f"🎵 TTS completed: {data.get('text', '')[:50]}...")
                    except json.JSONDecodeError:
                        pass
                        
        except websockets.exceptions.ConnectionClosed:
            print("🔌 TTS worker audio stream closed")
        except Exception as e:
            print(f"❌ Error handling audio frames: {e}")
    
    async def _process_speech_events(self):
        """Process speech events from command bus and send to TTS worker."""
        if not self.command_bus:
            return
        
        # Subscribe to command bus events
        subscriber_queue = self.command_bus.subscribe()
        
        try:
            while self.running:
                # Get next event from command bus
                event_json = await subscriber_queue.get()
                event_data = json.loads(event_json)
                
                # Process speech events for TTS
                if event_data.get("type") == StreamingEventTypes.SPEECH:
                    text = event_data.get("text", "")
                    if text:
                        await self._process_speech_text(text)
                        
        except Exception as e:
            print(f"❌ Error processing speech events: {e}")
        finally:
            self.command_bus.unsubscribe(subscriber_queue)
    
    async def _process_speech_text(self, text: str):
        """
        Process speech text with sentence boundary detection for streaming TTS.
        
        Args:
            text: Text to convert to speech
        """
        # Add text to buffer
        self.text_buffer += text + " "
        
        # Split buffer into sentences
        sentences = split_into_sentences(self.text_buffer)
        
        # Send complete sentences to TTS worker
        for i, sentence in enumerate(sentences[:-1]):  # Keep last partial sentence in buffer
            await self._send_to_tts_worker(sentence.strip())
        
        # Update buffer with remaining text
        if sentences:
            self.text_buffer = sentences[-1] if len(sentences) == 1 else ""
        
        # If we have a substantial amount of remaining text, send it anyway
        # This handles cases where text doesn't end with proper punctuation
        if len(self.text_buffer) > 100:  # Arbitrary threshold
            await self._send_to_tts_worker(self.text_buffer.strip())
            self.text_buffer = ""
    
    async def _send_to_tts_worker(self, text: str):
        """
        Send text clause to TTS worker for streaming synthesis.
        
        Args:
            text: Text clause to synthesize
        """
        if not text.strip() or not self.tts_connection:
            return
        
        try:
            # Send text to TTS worker
            await self.tts_connection.send(text)
            print(f"🎵 Sent to TTS: {text[:50]}...")
            
        except websockets.exceptions.ConnectionClosed:
            print("🔌 TTS connection lost while sending text")
            self.tts_connection = None
        except Exception as e:
            print(f"❌ Error sending to TTS worker: {e}")
    
    async def flush_buffer(self):
        """Flush any remaining text in the buffer to TTS."""
        if self.text_buffer.strip():
            await self._send_to_tts_worker(self.text_buffer.strip())
            self.text_buffer = ""


class BatchAudioDispatcher(AudioDispatcher):
    """
    Alternative dispatcher that batches speech events before sending to TTS.
    Useful for reducing TTS worker load with rapid speech events.
    """
    
    def __init__(self, tts_worker_url: str = "ws://localhost:8766", batch_delay: float = 0.5):
        super().__init__(tts_worker_url)
        self.batch_delay = batch_delay
        self.pending_texts = []
        self.batch_timer = None
    
    async def _process_speech_text(self, text: str):
        """Batch speech texts before processing."""
        self.pending_texts.append(text)
        
        # Reset batch timer
        if self.batch_timer:
            self.batch_timer.cancel()
        
        self.batch_timer = asyncio.create_task(self._batch_timer_expired())
    
    async def _batch_timer_expired(self):
        """Process batched texts when timer expires."""
        await asyncio.sleep(self.batch_delay)
        
        if self.pending_texts:
            # Combine all pending texts
            combined_text = " ".join(self.pending_texts)
            self.pending_texts.clear()
            
            # Process combined text using parent method
            await super()._process_speech_text(combined_text)


# Global audio dispatcher instance
_audio_dispatcher: Optional[AudioDispatcher] = None


def get_audio_dispatcher() -> AudioDispatcher:
    """Get the global audio dispatcher instance."""
    global _audio_dispatcher
    if _audio_dispatcher is None:
        _audio_dispatcher = AudioDispatcher()
    return _audio_dispatcher


async def start_audio_dispatcher():
    """Start the global audio dispatcher."""
    dispatcher = get_audio_dispatcher()
    await dispatcher.start()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Start audio dispatcher
    asyncio.run(start_audio_dispatcher())