# MultiModal Assistant - Multi-Agent Architecture

A sophisticated **multi-agent conversational AI system** built with **Google's Gemini API**, featuring **real-time coordination**, **streaming audio**, and **intelligent agent orchestration**. Perfect for production-grade AI applications requiring multiple specialized agents working in harmony.

## 🚀 Key Features

### ⚡ **Multi-Agent Coordination**
- **PlannerAgent**: Main orchestrator handling conversations and tool routing
- **WeatherAgent**: Specialized weather data retrieval and analysis  
- **CalendarAgent**: Calendar management and scheduling operations
- **Extensible**: Add new domain-specific agents in minutes

### 🔄 **Real-Time Command Bus**
- **Event-Driven**: Agents communicate via centralized command bus
- **WebSocket Streaming**: Live action updates for web frontends
- **Async Architecture**: Non-blocking agent coordination
- **Progress Tracking**: Real-time status and progress indicators

### 🎵 **Advanced Audio System**
- **Dual TTS**: Native Gemini 2.5 TTS + Local Piper streaming
- **Smart Sequencing**: No overlapping audio during multi-agent responses
- **Low Latency**: Sub-second response times with sentence streaming
- **High Quality**: 24kHz PCM16 audio output with natural voices

### 🧠 **Intelligent Function Calling**
- **Structured Outputs**: JSON schema-based reliable function calls
- **Smart Routing**: AI-driven task delegation to appropriate agents
- **Tool Integration**: Extensible function registry for new capabilities
- **Error Handling**: Graceful degradation and retry mechanisms

### 🌐 **Web Integration**
- **Real-Time UI**: WebSocket streaming at http://localhost:8000
- **Live Dashboard**: Monitor agent activity and command bus events
- **REST API**: FastAPI-based endpoints for external integration
- **Cross-Platform**: Works on macOS, Linux, Windows

## 🏗️ Architecture

### **Multi-Agent System**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   PlannerAgent  │    │   WeatherAgent   │    │  CalendarAgent  │
│   (Orchestrator)│    │   (Specialized)  │    │  (Specialized)  │
└─────────┬───────┘    └─────────┬────────┘    └─────────┬───────┘
          │                      │                       │
          └──────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Command Bus         │
                    │   (Event Coordination)  │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   WebSocket Server      │
                    │   (Real-time Updates)   │
                    └─────────────────────────┘
```

### **Core Components**
- **`agents/`** - Multi-agent system with base classes and specialized agents
- **`bus.py`** - Command bus for event-driven agent communication
- **`workflow.py`** - ADK-compatible workflow orchestration engine
- **`websocket_server.py`** - Real-time WebSocket streaming server
- **`tts_worker.py`** - Local TTS worker with Piper integration
- **`main.py`** - Single entry point with CLI and demo modes

## 🚀 Quick Start

### 1. **Install Dependencies**
```bash
# System dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio libasound2-dev

# System dependencies (macOS)  
brew install portaudio

# Python dependencies
pip install -r requirements.txt
```

### 2. **Configure API Key**
```bash
# Create .env file
echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env
```
Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### 3. **Run the Assistant**
```bash
# Interactive mode with all agents
python main.py

# Single query mode
python main.py "What's the weather in Tokyo?"

# Comprehensive demo (tests multi-agent coordination)
python main.py --demo

# WebSocket server only
python main.py --websocket-only
```

### 4. **Test Multi-Agent Coordination**
```bash
# Complex query that uses multiple agents
python main.py "Plan my day - check weather for my morning run in Central Park, schedule a team meeting for 2 PM, and tell me a joke to start the day"
```

## 🎯 Demo Mode - Multi-Agent Coordination Test

The `--demo` flag runs sophisticated tests that demonstrate:

### **Sequential Agent Coordination**
1. **Weather Query** → WeatherAgent fetches data
2. **Calendar Operation** → CalendarAgent manages schedule  
3. **General Response** → PlannerAgent provides context

### **Parallel Processing Test**
- Simultaneous weather checks for multiple cities
- Command bus message ordering verification
- Audio sequencing validation (no overlaps)

### **Error Handling Scenarios**
- Agent failure recovery
- Partial response handling
- Graceful degradation testing

### **Real-Time Monitoring**
- Live command bus events via WebSocket
- Agent status and progress tracking
- Performance metrics and timing analysis

## 📊 Example Usage

### **Weather Queries**
```bash
python main.py "What's the weather in London?"
# → WeatherAgent: Fetches current conditions
# → PlannerAgent: Formats natural response  
# → Audio: "Let me check that for you... It's currently 23°C and partly cloudy in London."
```

### **Calendar Management**
```bash
python main.py "What's on my schedule today?"
# → CalendarAgent: Retrieves today's events
# → PlannerAgent: Formats schedule summary
# → Audio: "You have 2 events today: Team standup at 9 AM and code review at 2:30 PM."
```

### **Complex Multi-Agent Query**
```bash
python main.py "Check weather for my 6 AM run, then schedule a 10 AM meeting, and give me a motivational quote"
# → WeatherAgent: Morning weather check
# → CalendarAgent: Meeting scheduling  
# → PlannerAgent: Motivational response
# → Audio: Coordinated responses without overlap
```

## 🔧 Development

### **Adding New Agents**
1. Create agent class inheriting from `BaseAgent`
2. Implement `async def run(task, context)` method
3. Add to workflow in `workflow.py`
4. Update task routing in `TaskRouter`

```python
from agents.base_agent import BaseAgent

class EmailAgent(BaseAgent):
    def __init__(self):
        super().__init__("EmailAgent", "Email management and communication")
    
    async def run(self, task: str, context: Dict[str, Any] = None):
        await self.notify_start(f"Processing email: {task}")
        # Implementation here
        await self.notify_complete(result)
        return result
```

### **Extending Workflows**
- **Star Topology**: Central planner delegates (default)
- **Chain Topology**: Sequential agent processing
- **Parallel Topology**: Concurrent agent execution

### **WebSocket Integration**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => {
    const action = JSON.parse(event.data);
    console.log(`Agent ${action.source}: ${action.action}`, action.data);
};
```

## 📈 Performance & Scalability

### **Latency Optimizations**
- **Command Bus**: Eliminates direct coupling, enables async processing
- **Streaming TTS**: Sub-600ms response time with sentence boundaries
- **Agent Pooling**: Concurrent agent execution where applicable
- **WebSocket**: Real-time updates without polling overhead

### **Production Deployment**
- **Docker Support**: Container-ready with multi-service orchestration
- **Horizontal Scaling**: Agent services can run as separate containers
- **Load Balancing**: WebSocket connections distributable across instances
- **Monitoring**: Built-in event tracking and performance metrics

## 🛡️ Error Handling

### **Graceful Degradation**
- Agent failures don't crash the system
- Partial responses when some agents fail
- Automatic retry mechanisms with backoff
- Comprehensive error propagation via command bus

### **Monitoring & Debugging**
- Real-time agent status via WebSocket dashboard
- Command bus event logging and replay
- Performance timing and bottleneck identification
- Health checks for all system components

## 🤝 Contributing

This architecture is designed for extensibility:

1. **Agent Development**: Add specialized agents for new domains
2. **Integration**: Connect external APIs and services
3. **UI Development**: Build web frontends using WebSocket streams
4. **Performance**: Optimize agent coordination and response times

## 📝 Technical Specifications

### **Dependencies**
- **Python 3.9+** with asyncio support
- **Google Gemini API** for LLM and TTS
- **WebSockets** for real-time communication  
- **FastAPI** for web server and REST endpoints
- **Piper TTS** for local audio generation (optional)

### **System Requirements**
- **Memory**: 4GB+ RAM for multiple agents
- **Network**: Stable internet for Gemini API calls
- **Audio**: PortAudio for audio playback
- **Ports**: 8000 (WebSocket), 8766 (TTS Worker)

## 🔮 Roadmap

### **Immediate Enhancements**
- [ ] Voice input with speech recognition
- [ ] Multi-language agent support
- [ ] Agent memory and conversation persistence
- [ ] Advanced scheduling and workflow automation

### **Future Integrations**
- [ ] Integration with popular productivity tools
- [ ] Custom agent marketplace and plugin system
- [ ] Enterprise authentication and permissions
- [ ] Advanced analytics and usage insights

---

**Built with ❤️ for the future of conversational AI**

*Ready for production deployment, extensible for your specific needs, and designed to scale with your ambitions.*