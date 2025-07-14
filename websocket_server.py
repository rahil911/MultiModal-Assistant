#!/usr/bin/env python3
"""
WebSocket server for streaming command bus actions to the frontend.
Provides real-time communication between agents and UI components.
"""

import asyncio
import json
import logging
from typing import Set, Dict, Any
import websockets
from websockets.server import WebSocketServerProtocol
from bus import get_command_bus, CommandBus


class WebSocketActionStreamer:
    """WebSocket server that streams command bus actions to connected clients."""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self.command_bus: CommandBus = None
        self.server = None
        
    async def start(self):
        """Start the WebSocket server and connect to command bus."""
        self.command_bus = await get_command_bus()
        
        # Start WebSocket server
        self.server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port
        )
        
        # Start action streaming task
        asyncio.create_task(self.stream_actions())
        
        print(f"🌐 WebSocket server started on ws://{self.host}:{self.port}")
        
    async def stop(self):
        """Stop the WebSocket server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Close all client connections
        if self.clients:
            await asyncio.gather(
                *[client.close() for client in self.clients],
                return_exceptions=True
            )
            
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle a new WebSocket client connection."""
        self.clients.add(websocket)
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        
        print(f"🔌 Client connected: {client_id}")
        
        try:
            # Send welcome message
            welcome_action = {
                "action": "connection_established",
                "data": {
                    "message": "Connected to MultiModal Assistant",
                    "client_id": client_id
                },
                "id": "welcome",
                "timestamp": asyncio.get_event_loop().time()
            }
            await websocket.send(json.dumps(welcome_action))
            
            # Keep connection alive and handle client messages
            async for message in websocket:
                await self.handle_client_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            print(f"🔌 Client disconnected: {client_id}")
        except Exception as e:
            print(f"❌ Error handling client {client_id}: {e}")
        finally:
            self.clients.discard(websocket)
            
    async def handle_client_message(self, websocket: WebSocketServerProtocol, message: str):
        """Handle incoming messages from clients."""
        try:
            data = json.loads(message)
            action_type = data.get("action")
            
            if action_type == "ping":
                # Respond to ping with pong
                pong_response = {
                    "action": "pong",
                    "data": {"timestamp": asyncio.get_event_loop().time()},
                    "id": "pong"
                }
                await websocket.send(json.dumps(pong_response))
                
            elif action_type == "subscribe_actions":
                # Client wants to subscribe to specific action types
                # For now, all clients get all actions
                pass
                
        except json.JSONDecodeError:
            print(f"⚠️ Received invalid JSON from client: {message}")
        except Exception as e:
            print(f"❌ Error processing client message: {e}")
            
    async def stream_actions(self):
        """Stream command bus actions to all connected WebSocket clients."""
        # Subscribe to command bus
        subscriber_queue = self.command_bus.subscribe()
        
        try:
            while True:
                # Get next action from command bus
                action_json = await subscriber_queue.get()
                
                # Broadcast to all connected clients
                if self.clients:
                    # Create list copy to avoid modification during iteration
                    clients_copy = list(self.clients)
                    
                    await asyncio.gather(
                        *[self.send_to_client(client, action_json) for client in clients_copy],
                        return_exceptions=True
                    )
                    
        except Exception as e:
            print(f"❌ Error in action streaming: {e}")
        finally:
            self.command_bus.unsubscribe(subscriber_queue)
            
    async def send_to_client(self, client: WebSocketServerProtocol, action_json: str):
        """Send an action to a specific client, handling connection errors."""
        try:
            await client.send(action_json)
        except websockets.exceptions.ConnectionClosed:
            # Client disconnected, remove from set
            self.clients.discard(client)
        except Exception as e:
            print(f"❌ Error sending to client: {e}")
            self.clients.discard(client)


# FastAPI integration for full-featured web server
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse


class FastAPIWebSocketStreamer:
    """Alternative WebSocket implementation using FastAPI for easier integration."""
    
    def __init__(self):
        self.app = FastAPI(title="MultiModal Assistant WebSocket API")
        self.clients: Set[WebSocket] = set()
        self.command_bus: CommandBus = None
        
        # Add WebSocket endpoint
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.handle_websocket(websocket)
            
        # Add simple test page
        @self.app.get("/")
        async def get_test_page():
            return HTMLResponse(self.get_test_html())
            
    async def start_command_bus_streaming(self):
        """Initialize command bus connection and start streaming."""
        self.command_bus = await get_command_bus()
        asyncio.create_task(self.stream_actions())
        
    async def handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connections."""
        await websocket.accept()
        self.clients.add(websocket)
        
        try:
            # Send welcome message
            welcome = {
                "action": "connection_established",
                "data": {"message": "Connected to MultiModal Assistant"},
                "id": "welcome"
            }
            await websocket.send_json(welcome)
            
            # Listen for client messages
            while True:
                data = await websocket.receive_json()
                await self.handle_client_message(websocket, data)
                
        except WebSocketDisconnect:
            self.clients.discard(websocket)
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
            self.clients.discard(websocket)
            
    async def handle_client_message(self, websocket: WebSocket, data: Dict[str, Any]):
        """Handle messages from WebSocket clients."""
        action = data.get("action")
        
        if action == "ping":
            await websocket.send_json({
                "action": "pong",
                "data": {"timestamp": asyncio.get_event_loop().time()}
            })
            
    async def stream_actions(self):
        """Stream command bus actions to WebSocket clients."""
        if not self.command_bus:
            return
            
        subscriber_queue = self.command_bus.subscribe()
        
        try:
            while True:
                action_json = await subscriber_queue.get()
                action_data = json.loads(action_json)
                
                # Send to all connected clients
                if self.clients:
                    clients_copy = list(self.clients)
                    await asyncio.gather(
                        *[self.send_to_client(client, action_data) for client in clients_copy],
                        return_exceptions=True
                    )
                    
        except Exception as e:
            print(f"❌ Error streaming actions: {e}")
        finally:
            self.command_bus.unsubscribe(subscriber_queue)
            
    async def send_to_client(self, client: WebSocket, action_data: Dict[str, Any]):
        """Send action to specific client."""
        try:
            await client.send_json(action_data)
        except Exception:
            self.clients.discard(client)
            
    def get_test_html(self) -> str:
        """Simple test page for WebSocket functionality."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>MultiModal Assistant WebSocket Test</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #messages { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; margin: 10px 0; }
        .message { margin: 5px 0; padding: 5px; background: #f5f5f5; border-radius: 3px; }
        .action-speak { background: #e3f2fd; }
        .action-progress { background: #fff3e0; }
        .action-error { background: #ffebee; }
    </style>
</head>
<body>
    <h1>MultiModal Assistant - Real-time Actions</h1>
    <div id="status">Connecting...</div>
    <div id="messages"></div>
    
    <script>
        const ws = new WebSocket('ws://localhost:8000/ws');
        const messages = document.getElementById('messages');
        const status = document.getElementById('status');
        
        ws.onopen = function() {
            status.textContent = 'Connected';
            status.style.color = 'green';
        };
        
        ws.onmessage = function(event) {
            const action = JSON.parse(event.data);
            const div = document.createElement('div');
            div.className = `message action-${action.action}`;
            div.innerHTML = `
                <strong>${action.action}</strong> - ${action.timestamp || 'now'}<br>
                <small>Source: ${action.source || 'unknown'}</small><br>
                <pre>${JSON.stringify(action.data, null, 2)}</pre>
            `;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        };
        
        ws.onclose = function() {
            status.textContent = 'Disconnected';
            status.style.color = 'red';
        };
        
        ws.onerror = function(error) {
            status.textContent = 'Error';
            status.style.color = 'red';
        };
        
        // Send ping every 30 seconds
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({action: 'ping'}));
            }
        }, 30000);
    </script>
</body>
</html>
        """


# Global WebSocket streamer instance
_websocket_streamer: FastAPIWebSocketStreamer = None


def get_websocket_app() -> FastAPI:
    """Get the FastAPI app with WebSocket streaming."""
    global _websocket_streamer
    if _websocket_streamer is None:
        _websocket_streamer = FastAPIWebSocketStreamer()
    return _websocket_streamer.app


async def start_websocket_streaming():
    """Start the command bus streaming for WebSocket clients."""
    global _websocket_streamer
    if _websocket_streamer:
        await _websocket_streamer.start_command_bus_streaming()


if __name__ == "__main__":
    import uvicorn
    
    async def main():
        # Start WebSocket streaming
        await start_websocket_streaming()
        
        # Run FastAPI server
        config = uvicorn.Config(
            app=get_websocket_app(),
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
        
    asyncio.run(main())