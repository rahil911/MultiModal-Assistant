#!/usr/bin/env python3
"""
Configuration settings for the multimodal assistant.
"""

import os
from dotenv import load_dotenv
load_dotenv()

# Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")

# Audio Configuration
API_SAMPLE_RATE = 24000  # Audio sample rate for processing
CHANNELS = 1            # Mono audio
BLOCKSIZE = 1024        # Audio block size for smooth playback

# Model Configuration
MODEL_NAME = "gemini-1.5-pro"  # Gemini model for text and function calling
TTS_MODEL_NAME = "gemini-2.5-flash-preview-tts"  # Gemini TTS model for audio generation
GENERATION_CONFIG = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 40,
    "max_output_tokens": 2048,
}

# TTS Configuration
TTS_VOICE = "Kore"  # Available voices: Kore, Puck, Zephyr, Aoede, etc.
TTS_CONFIG = {
    "response_modalities": ["AUDIO"],
    "speech_config": {
        "voice_config": {
            "prebuilt_voice_config": {
                "voice_name": TTS_VOICE
            }
        }
    }
}

# System Messages
SYSTEM_MESSAGE = (
    "You are a helpful multimodal assistant.\n"
    "When you need to use tools to get information:\n"
    " • Acknowledge the request briefly (e.g., 'I'll check that for you')\n" 
    " • Use the appropriate tool to fetch the information\n"
    " • Provide the result based on the tool data\n"
    "For weather questions, use the get_current_weather function."
) 