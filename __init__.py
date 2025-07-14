#!/usr/bin/env python3
"""
Multimodal Assistant Package

A modular multimodal assistant for building multi-agent frameworks.
"""

from .main import MultimodalAssistant
from .audio_handler import AudioHandler
from .gemini_client import GeminiClient
from .tools import TOOLS_SPEC, FUNCTION_REGISTRY, execute_function
from . import config

__version__ = "1.0.0"
__author__ = "MultiModal Assistant Team"

__all__ = [
    "MultimodalAssistant",
    "AudioHandler", 
    "GeminiClient",
    "TOOLS_SPEC",
    "FUNCTION_REGISTRY",
    "execute_function",
    "config"
] 