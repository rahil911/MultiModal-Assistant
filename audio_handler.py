#!/usr/bin/env python3
"""
Audio handling module for multimodal assistant.
Manages audio streaming, processing, and playback.
"""

import base64
import math
import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly
from typing import List
from config import API_SAMPLE_RATE, CHANNELS


class AudioHandler:
    """Handles audio streaming, processing, and playback."""
    
    def __init__(self):
        self.all_audio_data: List[np.ndarray] = []
        self.device_sample_rate = None
    
    def detect_device_sample_rate(self) -> None:
        """Detect the actual sample rate the device will use."""
        print(f"Requested sample rate: {API_SAMPLE_RATE} Hz")
        
        try:
            with sd.OutputStream(
                samplerate=API_SAMPLE_RATE,
                channels=CHANNELS,
                dtype=np.float32
            ) as test_stream:
                self.device_sample_rate = test_stream.samplerate
                print(f"Device actual sample rate: {self.device_sample_rate} Hz")
                
                if self.device_sample_rate != API_SAMPLE_RATE:
                    print(f"⚠️  SAMPLE RATE MISMATCH DETECTED!")
                    print(f"   API provides: {API_SAMPLE_RATE} Hz")
                    print(f"   Device uses: {self.device_sample_rate} Hz")
                    print(f"   Speed factor: {self.device_sample_rate/API_SAMPLE_RATE:.2f}x")
                    print(f"   Will apply automatic resampling...")
                else:
                    print("✅ Sample rates match - no resampling needed")
                    
        except Exception as e:
            print(f"Error detecting sample rate: {e}")
            self.device_sample_rate = 48000  # Default fallback
            print(f"Using fallback rate: {self.device_sample_rate} Hz")
    
    def resample_audio_if_needed(self, audio_data: np.ndarray) -> np.ndarray:
        """Resample audio data if device sample rate differs from API rate."""
        if self.device_sample_rate == API_SAMPLE_RATE:
            return audio_data
        
        # Calculate resampling factors
        up_factor = int(self.device_sample_rate)
        down_factor = int(API_SAMPLE_RATE)
        
        # Simplify the fraction to avoid huge numbers
        gcd = math.gcd(up_factor, down_factor)
        up_factor //= gcd
        down_factor //= gcd
        
        # Apply resampling using scipy
        resampled = resample_poly(audio_data, up_factor, down_factor)
        
        return resampled
    
    def accumulate_audio_chunk(self, audio_data: bytes) -> None:
        """Convert PCM16 audio data and accumulate for later playback."""
        if len(audio_data) == 0:
            return
        
        # Detect sample rate first time
        if self.device_sample_rate is None:
            self.detect_device_sample_rate()
        
        # Convert PCM16 bytes to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # Convert to float32 for processing (range -1.0 to 1.0)
        audio_float = audio_array.astype(np.float32) / 32768.0
        
        # Apply resampling if needed
        if self.device_sample_rate != API_SAMPLE_RATE:
            audio_float = self.resample_audio_if_needed(audio_float)
        
        # Simply accumulate - no overlapping playback
        self.all_audio_data.append(audio_float)
        print(f"Accumulated audio chunk: {len(audio_float)} samples")
    
    def play_accumulated_audio(self) -> None:
        """Play all accumulated audio as one continuous stream."""
        if not self.all_audio_data:
            print("No audio data to play")
            return
        
        # Concatenate all chunks into one array
        complete_audio = np.concatenate(self.all_audio_data)
        duration = len(complete_audio) / self.device_sample_rate
        
        print(f"Playing complete audio: {len(complete_audio)} samples, {duration:.2f} seconds")
        
        # Play the complete audio once
        sd.play(complete_audio, samplerate=self.device_sample_rate)
        sd.wait()  # Wait for playback to complete
        
        print("Audio playback completed")
    
    def process_audio_delta(self, delta) -> None:
        """Process audio delta from OpenAI stream."""
        if hasattr(delta, 'audio') and delta.audio:
            # Handle audio data based on the current library structure
            if hasattr(delta.audio, 'data') and delta.audio.data:
                audio_chunk = base64.b64decode(delta.audio.data)
                self.accumulate_audio_chunk(audio_chunk)
            elif isinstance(delta.audio, dict) and delta.audio.get('data'):
                audio_chunk = base64.b64decode(delta.audio['data'])
                self.accumulate_audio_chunk(audio_chunk)
    
    def clear_audio_data(self) -> None:
        """Clear accumulated audio data."""
        self.all_audio_data.clear()
    
    def play_audio_file(self, file_path: str) -> None:
        """
        Play an audio file directly.
        
        Args:
            file_path: Path to the audio file to play
        """
        try:
            import wave
            
            # Read the wave file
            with wave.open(file_path, 'rb') as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                frames = wf.readframes(wf.getnframes())
                
                # Convert to numpy array
                audio_data = np.frombuffer(frames, dtype=np.int16)
                
                # Convert to float32 for sounddevice
                if audio_data.dtype == np.int16:
                    audio_float = audio_data.astype(np.float32) / 32768.0
                else:
                    audio_float = audio_data.astype(np.float32)
                
                # Reshape for stereo if needed
                if channels == 2:
                    audio_float = audio_float.reshape(-1, 2)
                
                print(f"🔊 Playing audio: {len(audio_float)} samples at {sample_rate}Hz")
                
                # Play the audio
                sd.play(audio_float, samplerate=sample_rate)
                sd.wait()  # Wait for playback to complete
                
        except Exception as e:
            print(f"Error playing audio file: {e}")
    
    def play_pcm_audio(self, pcm_data: bytes) -> None:
        """
        Play PCM16 audio data directly from Gemini TTS.
        
        Args:
            pcm_data: PCM16 audio data bytes
        """
        try:
            if not pcm_data:
                print("⚠️  No audio data to play")
                return
                
            # Convert PCM16 bytes to numpy array
            # Ensure data length is even (for int16)
            if len(pcm_data) % 2 != 0:
                pcm_data = pcm_data[:-1]
            
            audio_array = np.frombuffer(pcm_data, dtype=np.int16)
            
            if len(audio_array) == 0:
                print("⚠️  Empty audio data")
                return
            
            # Convert to float32 for sounddevice (range -1.0 to 1.0)
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # Gemini TTS outputs at 24kHz mono
            sample_rate = 24000
            
            print("🔊 Playing audio...")
            
            # Play the audio 
            sd.play(audio_float, samplerate=sample_rate)
            sd.wait()  # Wait for playback to complete
            
        except Exception as e:
            print(f"❌ Error processing audio data: {e}") 