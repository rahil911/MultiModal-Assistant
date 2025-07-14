/**
 * Frontend React hooks for streaming integration with MultiModal Assistant.
 * Provides real-time text and audio streaming capabilities.
 */

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Hook for Server-Sent Events streaming connection.
 * Provides real-time event updates from the backend.
 */
export function useEventBus(serverUrl = 'http://localhost:8000') {
  const [events, setEvents] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [lastEvent, setLastEvent] = useState(null);
  const eventSourceRef = useRef(null);

  useEffect(() => {
    const connectEventSource = () => {
      setConnectionStatus('connecting');
      
      const eventSource = new EventSource(`${serverUrl}/stream`);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        setConnectionStatus('connected');
        console.log('✅ SSE connection established');
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastEvent(data);
          setEvents(prev => [...prev.slice(-99), data]); // Keep last 100 events
        } catch (error) {
          console.error('❌ Error parsing SSE event:', error);
        }
      };

      eventSource.onerror = (error) => {
        console.error('❌ SSE connection error:', error);
        setConnectionStatus('error');
        
        // Auto-reconnect after 3 seconds
        setTimeout(() => {
          if (eventSourceRef.current?.readyState === EventSource.CLOSED) {
            connectEventSource();
          }
        }, 3000);
      };
    };

    connectEventSource();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [serverUrl]);

  const clearEvents = useCallback(() => {
    setEvents([]);
    setLastEvent(null);
  }, []);

  return {
    events,
    lastEvent,
    connectionStatus,
    clearEvents
  };
}

/**
 * Hook for filtering events by type.
 * Useful for separating speech, status, progress events.
 */
export function useEventsByType(events, eventType) {
  return events.filter(event => event.type === eventType);
}

/**
 * Hook for progressive text rendering with streaming tokens.
 * Accumulates token events into complete text.
 */
export function useStreamingText(events) {
  const [currentText, setCurrentText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const timeoutRef = useRef(null);

  useEffect(() => {
    const tokenEvents = events.filter(event => event.type === 'token');
    const speechEvents = events.filter(event => event.type === 'speech');

    if (tokenEvents.length > 0) {
      setIsStreaming(true);
      
      // Accumulate tokens
      const text = tokenEvents.map(event => event.token).join('');
      setCurrentText(text);

      // Clear streaming state after tokens stop coming
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => {
        setIsStreaming(false);
      }, 500);
    }

    // Handle complete speech events (fallback for non-streaming)
    if (speechEvents.length > 0 && tokenEvents.length === 0) {
      const latestSpeech = speechEvents[speechEvents.length - 1];
      setCurrentText(latestSpeech.text);
      setIsStreaming(false);
    }

  }, [events]);

  return {
    text: currentText,
    isStreaming
  };
}

/**
 * Hook for WebSocket audio streaming.
 * Handles real-time PCM audio playback.
 */
export function useAudioStreaming(serverUrl = 'ws://localhost:8000') {
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [isPlaying, setIsPlaying] = useState(false);
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioQueueRef = useRef([]);
  const sourceNodeRef = useRef(null);

  // Initialize Web Audio API
  useEffect(() => {
    const initAudioContext = async () => {
      try {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({
          sampleRate: 22050
        });
        console.log('✅ Audio context initialized');
      } catch (error) {
        console.error('❌ Error initializing audio context:', error);
      }
    };

    initAudioContext();

    return () => {
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  // WebSocket connection for audio streaming
  useEffect(() => {
    const connectAudioWebSocket = () => {
      setConnectionStatus('connecting');
      
      const ws = new WebSocket(`${serverUrl}/ws/audio`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionStatus('connected');
        console.log('✅ Audio WebSocket connected');
      };

      ws.onmessage = async (event) => {
        if (event.data instanceof Blob) {
          // Received PCM audio data
          const arrayBuffer = await event.data.arrayBuffer();
          playAudioChunk(arrayBuffer);
        } else {
          // Received text message (control/status)
          try {
            const data = JSON.parse(event.data);
            console.log('🎵 Audio status:', data);
          } catch (error) {
            // Not JSON, ignore
          }
        }
      };

      ws.onclose = () => {
        setConnectionStatus('disconnected');
        console.log('🔌 Audio WebSocket disconnected');
      };

      ws.onerror = (error) => {
        console.error('❌ Audio WebSocket error:', error);
        setConnectionStatus('error');
      };
    };

    const playAudioChunk = async (arrayBuffer) => {
      if (!audioContextRef.current) return;

      try {
        setIsPlaying(true);

        // Convert PCM data to AudioBuffer
        const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer);
        
        // Create audio source and play
        const source = audioContextRef.current.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContextRef.current.destination);
        
        source.onended = () => {
          setIsPlaying(false);
        };
        
        source.start();
        sourceNodeRef.current = source;

      } catch (error) {
        console.error('❌ Error playing audio chunk:', error);
        setIsPlaying(false);
      }
    };

    connectAudioWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (sourceNodeRef.current) {
        sourceNodeRef.current.stop();
      }
    };
  }, [serverUrl]);

  const sendTextToTTS = useCallback((text) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(text);
    }
  }, []);

  return {
    connectionStatus,
    isPlaying,
    sendTextToTTS
  };
}

/**
 * Hook for agent status monitoring.
 * Tracks which agents are active and their current tasks.
 */
export function useAgentStatus(events) {
  const [agentStates, setAgentStates] = useState({});

  useEffect(() => {
    const statusEvents = events.filter(event => 
      event.type === 'status' || 
      event.type === 'agent_start' || 
      event.type === 'agent_done'
    );

    const newStates = { ...agentStates };

    statusEvents.forEach(event => {
      const source = event.source || 'unknown';
      
      if (event.type === 'agent_start') {
        newStates[source] = {
          status: 'active',
          task: event.message || event.data?.task,
          lastUpdate: event.timestamp
        };
      } else if (event.type === 'agent_done') {
        newStates[source] = {
          status: 'idle',
          task: null,
          lastUpdate: event.timestamp
        };
      } else if (event.type === 'status') {
        newStates[source] = {
          ...newStates[source],
          status: 'active',
          message: event.message,
          lastUpdate: event.timestamp
        };
      }
    });

    setAgentStates(newStates);
  }, [events]);

  return agentStates;
}

/**
 * Hook for progress tracking across all agents.
 * Provides aggregated progress information.
 */
export function useProgressTracking(events) {
  const [progressData, setProgressData] = useState({});

  useEffect(() => {
    const progressEvents = events.filter(event => event.type === 'progress');
    
    const newProgress = {};
    
    progressEvents.forEach(event => {
      const source = event.source || 'system';
      newProgress[source] = {
        message: event.message,
        percentage: event.percentage || null,
        timestamp: event.timestamp
      };
    });

    setProgressData(newProgress);
  }, [events]);

  return progressData;
}

/**
 * Complete integration hook that combines all streaming features.
 * One-stop solution for full streaming integration.
 */
export function useMultiAgentStreaming(serverUrl = 'http://localhost:8000') {
  const { events, lastEvent, connectionStatus: sseStatus, clearEvents } = useEventBus(serverUrl);
  const { text, isStreaming } = useStreamingText(events);
  const { 
    connectionStatus: audioStatus, 
    isPlaying, 
    sendTextToTTS 
  } = useAudioStreaming(serverUrl.replace('http', 'ws'));
  const agentStates = useAgentStatus(events);
  const progressData = useProgressTracking(events);

  const speechEvents = useEventsByType(events, 'speech');
  const statusEvents = useEventsByType(events, 'status');
  const errorEvents = useEventsByType(events, 'error');

  return {
    // Connection status
    sseStatus,
    audioStatus,
    
    // Event data
    events,
    lastEvent,
    speechEvents,
    statusEvents,
    errorEvents,
    
    // Text streaming
    text,
    isStreaming,
    
    // Audio streaming
    isPlaying,
    sendTextToTTS,
    
    // Agent monitoring
    agentStates,
    progressData,
    
    // Utilities
    clearEvents
  };
}

/**
 * Example React component demonstrating usage.
 */
export function StreamingAssistantDemo() {
  const {
    sseStatus,
    audioStatus,
    text,
    isStreaming,
    isPlaying,
    agentStates,
    progressData,
    speechEvents,
    sendTextToTTS
  } = useMultiAgentStreaming();

  return (
    <div className="streaming-assistant-demo">
      <div className="connection-status">
        <div className={`status-indicator ${sseStatus}`}>
          SSE: {sseStatus}
        </div>
        <div className={`status-indicator ${audioStatus}`}>
          Audio: {audioStatus}
        </div>
      </div>

      <div className="streaming-text">
        <h3>Live Response {isStreaming && <span className="streaming-indicator">●</span>}</h3>
        <div className="text-content">
          {text}
        </div>
      </div>

      <div className="agent-states">
        <h3>Agent Status</h3>
        {Object.entries(agentStates).map(([agentName, state]) => (
          <div key={agentName} className={`agent-status ${state.status}`}>
            <strong>{agentName}</strong>: {state.status}
            {state.message && <span> - {state.message}</span>}
          </div>
        ))}
      </div>

      <div className="progress-tracking">
        <h3>Progress</h3>
        {Object.entries(progressData).map(([source, progress]) => (
          <div key={source} className="progress-item">
            <div>{source}: {progress.message}</div>
            {progress.percentage && (
              <div className="progress-bar">
                <div 
                  className="progress-fill" 
                  style={{ width: `${progress.percentage}%` }}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="audio-controls">
        <button 
          onClick={() => sendTextToTTS('Test audio streaming')}
          disabled={audioStatus !== 'connected'}
        >
          Test Audio {isPlaying && '🔊'}
        </button>
      </div>

      <div className="recent-events">
        <h3>Recent Speech Events</h3>
        {speechEvents.slice(-5).map((event, index) => (
          <div key={index} className="speech-event">
            <strong>{event.source}</strong>: {event.text}
          </div>
        ))}
      </div>
    </div>
  );
}