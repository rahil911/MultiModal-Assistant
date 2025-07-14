#!/usr/bin/env python3
"""
FastAPI server with Server-Sent Events streaming for real-time updates.
Provides text streaming, WebSocket audio, and frontend integration.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from sse_starlette import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware
from bus import get_command_bus, StreamingEventTypes


class StreamingServer:
    """FastAPI server with SSE and WebSocket streaming capabilities."""
    
    def __init__(self, assistant=None):
        self.app = FastAPI(
            title="MultiModal Assistant Streaming API",
            description="Real-time streaming endpoints for multi-agent conversation"
        )
        self.audio_clients = set()
        self.command_bus = None
        self.assistant = assistant
        self._setup_routes()
        self._setup_middleware()
        
    def _setup_middleware(self):
        """Setup CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
    def _setup_routes(self):
        """Setup all API routes."""
        
        @self.app.get("/")
        async def get_dashboard():
            """Serve streaming dashboard for real-time monitoring."""
            return HTMLResponse(self._get_dashboard_html())
        
        @self.app.get("/stream")
        async def stream_events():
            """Server-Sent Events endpoint for real-time text streaming."""
            return EventSourceResponse(self._event_generator())
            
        @self.app.websocket("/ws/audio")
        async def websocket_audio(websocket: WebSocket):
            """WebSocket endpoint for real-time audio streaming."""
            await self._handle_audio_websocket(websocket)
            
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "service": "streaming_server"}
    
    async def _event_generator(self):
        """Generate Server-Sent Events from the command bus."""
        if not self.command_bus:
            self.command_bus = await get_command_bus()
        
        # Subscribe to command bus events
        subscriber_queue = self.command_bus.subscribe()
        
        try:
            while True:
                # Get next event from command bus
                event_json = await subscriber_queue.get()
                event_data = json.loads(event_json)
                
                # Filter for streaming events
                if event_data.get("type") in [
                    StreamingEventTypes.SPEECH,
                    StreamingEventTypes.TOKEN,
                    StreamingEventTypes.STATUS,
                    StreamingEventTypes.PROGRESS,
                    StreamingEventTypes.AGENT_START,
                    StreamingEventTypes.AGENT_DONE
                ]:
                    yield {
                        "event": "update",
                        "data": event_json
                    }
                    
        except Exception as e:
            logging.error(f"Error in event generator: {e}")
            yield {
                "event": "error", 
                "data": json.dumps({"error": str(e)})
            }
        finally:
            self.command_bus.unsubscribe(subscriber_queue)
    
    async def _handle_audio_websocket(self, websocket: WebSocket):
        """Handle WebSocket connections for audio streaming."""
        await websocket.accept()
        self.audio_clients.add(websocket)
        
        try:
            # Keep connection alive and listen for audio frames
            while True:
                # In a real implementation, this would receive PCM frames
                # from the audio dispatcher and forward to clients
                data = await websocket.receive_text()
                
                # Echo back for testing (replace with actual audio streaming)
                await websocket.send_text(f"Audio received: {data}")
                
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logging.error(f"Audio WebSocket error: {e}")
        finally:
            self.audio_clients.discard(websocket)
    
    async def broadcast_audio(self, audio_data: bytes):
        """Broadcast audio data to all connected audio clients."""
        if not self.audio_clients:
            return
            
        # Send to all connected audio clients
        disconnected = set()
        for client in self.audio_clients:
            try:
                await client.send_bytes(audio_data)
            except Exception:
                disconnected.add(client)
        
        # Remove disconnected clients
        self.audio_clients -= disconnected
    
    def _get_dashboard_html(self) -> str:
        """HTML dashboard for real-time streaming monitoring."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>MultiModal Assistant - Live Streaming Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                 color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .events { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .event { margin: 10px 0; padding: 15px; border-left: 4px solid #667eea; 
                background: #f8f9ff; border-radius: 5px; }
        .event.speech { border-left-color: #4CAF50; background: #f0fdf4; }
        .event.status { border-left-color: #FF9800; background: #fffbf0; }
        .event.progress { border-left-color: #2196F3; background: #f0f8ff; }
        .event.error { border-left-color: #f44336; background: #fef7f7; }
        .timestamp { font-size: 0.8em; color: #666; }
        .source { font-weight: bold; color: #333; }
        .stats { display: flex; gap: 20px; margin-bottom: 20px; }
        .stat { background: white; padding: 15px; border-radius: 10px; text-align: center; 
               box-shadow: 0 2px 10px rgba(0,0,0,0.1); flex: 1; }
        .stat-value { font-size: 2em; font-weight: bold; color: #667eea; }
        .audio-test { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        #audioStatus { margin: 10px 0; padding: 10px; border-radius: 5px; }
        .connected { background: #d4edda; color: #155724; }
        .disconnected { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 MultiModal Assistant - Live Streaming Dashboard</h1>
            <p>Real-time monitoring of multi-agent coordination and streaming events</p>
        </div>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-value" id="eventCount">0</div>
                <div>Events Received</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="speechCount">0</div>
                <div>Speech Events</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="agentCount">0</div>
                <div>Active Agents</div>
            </div>
        </div>
        
        <div class="audio-test">
            <h3>🎵 Audio Streaming Test</h3>
            <button onclick="testAudio()">Test Audio Connection</button>
            <div id="audioStatus" class="disconnected">Audio: Disconnected</div>
        </div>
        
        <div class="events">
            <h3>📡 Live Event Stream</h3>
            <div id="eventStream"></div>
        </div>
    </div>

    <script>
        let eventCount = 0;
        let speechCount = 0;
        let activeAgents = new Set();
        let audioWs = null;

        // Server-Sent Events connection
        const eventSource = new EventSource('/stream');
        
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            handleStreamEvent(data);
        };
        
        eventSource.onerror = function(event) {
            console.error('SSE error:', event);
            addEvent({
                type: 'error',
                message: 'SSE connection error',
                timestamp: new Date().toISOString()
            });
        };
        
        function handleStreamEvent(data) {
            eventCount++;
            document.getElementById('eventCount').textContent = eventCount;
            
            if (data.type === 'speech') {
                speechCount++;
                document.getElementById('speechCount').textContent = speechCount;
            }
            
            if (data.source) {
                activeAgents.add(data.source);
                document.getElementById('agentCount').textContent = activeAgents.size;
            }
            
            addEvent(data);
        }
        
        function addEvent(data) {
            const eventDiv = document.createElement('div');
            eventDiv.className = `event ${data.type || 'unknown'}`;
            
            const timestamp = new Date(data.timestamp || Date.now()).toLocaleTimeString();
            const source = data.source || 'system';
            const content = data.text || data.message || data.token || JSON.stringify(data);
            
            eventDiv.innerHTML = `
                <div class="source">${source}</div>
                <div>${content}</div>
                <div class="timestamp">${timestamp}</div>
            `;
            
            const stream = document.getElementById('eventStream');
            stream.insertBefore(eventDiv, stream.firstChild);
            
            // Keep only last 50 events
            while (stream.children.length > 50) {
                stream.removeChild(stream.lastChild);
            }
        }
        
        function testAudio() {
            if (audioWs) {
                audioWs.close();
            }
            
            audioWs = new WebSocket('ws://localhost:8000/ws/audio');
            
            audioWs.onopen = function() {
                document.getElementById('audioStatus').textContent = 'Audio: Connected ✅';
                document.getElementById('audioStatus').className = 'connected';
                audioWs.send('Test audio message');
            };
            
            audioWs.onmessage = function(event) {
                console.log('Audio message:', event.data);
            };
            
            audioWs.onclose = function() {
                document.getElementById('audioStatus').textContent = 'Audio: Disconnected ❌';
                document.getElementById('audioStatus').className = 'disconnected';
            };
            
            audioWs.onerror = function(error) {
                console.error('Audio WebSocket error:', error);
                document.getElementById('audioStatus').textContent = 'Audio: Error ⚠️';
                document.getElementById('audioStatus').className = 'disconnected';
            };
        }
        
        // Add some demo events for testing
        setTimeout(() => {
            addEvent({
                type: 'speech',
                text: 'Demo: Welcome to the streaming dashboard!',
                source: 'PlannerAgent',
                timestamp: new Date().toISOString()
            });
        }, 1000);
    </script>
</body>
</html>
        """
    
    async def start(self, host: str = "0.0.0.0", port: int = 8000):
        """Start the streaming server."""
        import uvicorn
        
        # Initialize command bus connection
        self.command_bus = await get_command_bus()
        
        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            log_level="info"
        )
        
        uvicorn_server = uvicorn.Server(config)
        await uvicorn_server.serve()


# Global server instance
_streaming_server: Optional[StreamingServer] = None


def get_streaming_server() -> StreamingServer:
    """Get the global streaming server instance."""
    global _streaming_server
    if _streaming_server is None:
        _streaming_server = StreamingServer()
    return _streaming_server


async def start_streaming_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the streaming server."""
    import uvicorn
    
    server = get_streaming_server()
    
    # Initialize command bus connection
    server.command_bus = await get_command_bus()
    
    config = uvicorn.Config(
        app=server.app,
        host=host,
        port=port,
        log_level="info"
    )
    
    uvicorn_server = uvicorn.Server(config)
    await uvicorn_server.serve()


if __name__ == "__main__":
    asyncio.run(start_streaming_server())