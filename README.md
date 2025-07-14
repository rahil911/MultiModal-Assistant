# Multimodal Assistant

A modular multimodal assistant built with **Google's Gemini API** featuring structured outputs, native TTS, and intelligent function calling. Perfect foundation for multi-agent frameworks.

## 🚀 Features

### ✅ **Working Audio System**
- **Native Gemini 2.5 TTS**: Real audio generation with natural voices
- **Multiple Voices**: Kore, Puck, Zephyr, Aoede, and 30+ others
- **High Quality**: 24kHz PCM16 audio output
- **Real-time Playback**: Direct audio streaming

### 🧠 **Intelligent Function Calling**
- **Structured Outputs**: Uses Gemini's JSON schema for reliable function calls
- **Smart Routing**: AI decides when to call functions vs. respond directly
- **Weather Integration**: Example weather lookup functionality
- **Extensible**: Easy to add new functions

### 🎯 **Conversation Flow**
- **Dual Audio**: Hear both acknowledgment AND final response
- **Natural Flow**: "I'll check that for you" → *fetches data* → "Here's what I found"
- **Status Updates**: Visual progress indicators during function execution

## 🏗️ Architecture

The codebase is organized into focused, modular components:

### **Core Modules**
- **`config.py`** - Configuration settings (API keys, models, TTS voices)
- **`gemini_client.py`** - Gemini API wrapper with structured outputs
- **`audio_handler.py`** - Audio processing and playback engine
- **`tools.py`** - Function definitions and execution registry
- **`main.py`** - Main orchestration and conversation flow

### **Entry Points**
- **`main.py`** - Primary entry point
- **`multimodal.py`** - Legacy entry point

## 🚀 Quick Start

### 1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

### 2. **Set up API Key**
Create a `.env` file in the project root:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
```
Get your key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### 3. **Run the Assistant**
```bash
python3 main.py
```

### 4. **Test Examples**
- **Weather Query**: "What's the weather in Tokyo?"
- **General Query**: "Tell me a joke about programming"
- **Math Query**: "What is 25 * 4?"

## 🤖 Why This Architecture?

### **Perfect for Multi-Agent Frameworks**
- **Modular Design**: Each component is independent and replaceable
- **Structured Outputs**: JSON schemas ensure reliable agent-to-agent communication
- **Function Registry**: Easy to add new capabilities and tools
- **State Management**: Clean separation between conversation flow and execution

### **Google ADK Ready**
This codebase is specifically designed to integrate with Google's Agent Development Kit (ADK) for multi-agent systems:
- **Gemini Native**: Uses latest Gemini features (structured outputs, native TTS)
- **Extensible Tools**: Function calling system ready for complex workflows
- **Audio Integration**: Voice capabilities for natural agent interaction

## 🔧 Adding New Functions

1. **Define function in `tools.py`:**
```python
def get_stock_price(symbol: str) -> Dict[str, Any]:
    # Your implementation
    return {"symbol": symbol, "price": 150.25}

# Add to TOOLS_SPEC
TOOLS_SPEC.append({
    "type": "function", 
    "function": {
        "name": "get_stock_price",
        "description": "Get current stock price",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock symbol"}
            }
        }
    }
})
```

2. **Register in `FUNCTION_REGISTRY`:**
```python
FUNCTION_REGISTRY["get_stock_price"] = get_stock_price
```

That's it! The structured output system will automatically handle the new function.

## 📦 Dependencies

```
google-generativeai>=0.8.0  # Gemini API with structured outputs
google-genai>=0.2.0         # Gemini client with TTS support  
numpy>=1.21.0               # Audio processing
sounddevice>=0.4.0          # Audio playback
scipy>=1.7.0                # Audio resampling
python-dotenv>=1.0.0        # Environment variables
```

## 📝 Example Conversations

### **Weather Query (Function Call)**
```
User > What's the weather in London?
🤖 Assistant: I can certainly help you with that. Let me quickly check the weather in London for you.
🎵 Generating speech...
🔊 Playing audio...

🌤️  Fetching current weather for London...
🤖 The weather in London is currently partly cloudy and 23°C.
🎵 Generating speech...
🔊 Playing audio...

✨ Done!
```

### **General Query (Direct Response)**
```
User > Tell me a joke about programming
🤖 Assistant: Why don't scientists trust atoms? Because they make up everything!
🎵 Generating speech...
🔊 Playing audio...

✨ Done!
```

**You hear both responses spoken with natural voice synthesis!** 