# Chetect WebSocket Gateway

Real-time WebSocket gateway for streaming exam analysis data between mobile clients and the AI backend. This service acts as the communication layer of the Chetect system, managing live connections, handling multipart data uploads, and broadcasting alerts to invigilators.

## 📋 Overview

The ChetectWebsocket Gateway provides:

- 🔌 **WebSocket Connections**: Persistent real-time connections for students and invigilators
- 📡 **Data Streaming**: Efficient frame and video chunk transmission from mobile clients
- 🔄 **API Routing**: Forwards analysis requests to the CheatingDetector backend
- 📊 **Event Broadcasting**: Real-time alerts and suspicious event notifications
- 🔐 **Connection Management**: Automatic reconnection, heartbeat, and session tracking
- 📈 **Load Balancing**: Handles concurrent sessions efficiently
- 🎯 **Data Transformation**: Converts between WebSocket and HTTP protocols

## 📁 Project Structure

```
chetectWebsocket/
├── chetectWebsocket/            # Main application package
│   ├── __init__.py
│   ├── app.py                   # Main WebSocket application
│   ├── model_client.py          # CheatingDetector API client
│   ├── settings.py              # Configuration
│   ├── tests/                   # Test suite
│   │   ├── __init__.py
│   │   └── test_websocket_gateway.py
│   └── README.md
├── requirements.txt             # Python dependencies
├── startup.txt                  # Startup configuration
└── README.md                    # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- pip
- CheatingDetector API running on port 8000
- (Optional) myApp development server for client testing

### Installation

```bash
# Navigate to project directory
cd chetectWebsocket

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
# Unix/macOS:
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Running the Gateway

#### Basic Start

```bash
uvicorn app:app --reload
```

#### With Custom Configuration

```bash
# Specify host and port
uvicorn app:app --host 0.0.0.0 --port 8001 --reload

# Production mode (no auto-reload)
uvicorn app:app --host 0.0.0.0 --port 8001 --workers 2
```

#### With Environment Variables

```bash
# Windows PowerShell
$env:MODEL_API_BASE_URL="http://127.0.0.1:8000"
$env:ALLOWED_ORIGINS="*"
$env:WEBSOCKET_PORT="8001"
uvicorn app:app --reload

# Unix/macOS Bash
export MODEL_API_BASE_URL="http://127.0.0.1:8000"
export ALLOWED_ORIGINS="*"
export WEBSOCKET_PORT="8001"
uvicorn app:app --reload
```

#### Full Startup Example (Windows)

```powershell
# Set environment variables
$env:MODEL_API_BASE_URL="http://127.0.0.1:8000"
$env:ALLOWED_ORIGINS="http://localhost:8081,http://192.168.1.x:8081"
$env:WEBSOCKET_PORT="8001"
$env:LOG_LEVEL="INFO"

# Run with uvicorn
uvicorn chetectWebsocket.app:app --host 0.0.0.0 --port 8001 --reload
```

#### Full Startup Example (Unix/macOS)

```bash
# Set environment variables
export MODEL_API_BASE_URL="http://127.0.0.1:8000"
export ALLOWED_ORIGINS="*"
export WEBSOCKET_PORT="8001"
export LOG_LEVEL="INFO"

# Run with uvicorn
uvicorn chetectWebsocket.app:app --host 0.0.0.0 --port 8001 --reload
```

## ⚙️ Configuration

### Environment Variables

```bash
# API Configuration
MODEL_API_BASE_URL=http://127.0.0.1:8000        # CheatingDetector API endpoint
WEBSOCKET_PORT=8001                              # WebSocket server port
WEBSOCKET_HOST=0.0.0.0                          # WebSocket server host

# CORS Configuration
ALLOWED_ORIGINS=*                                 # Allowed client origins
ALLOWED_METHODS=GET,POST,OPTIONS,DELETE          # Allowed HTTP methods

# Connection Settings
MAX_CONNECTIONS=100                              # Maximum concurrent connections
CONNECTION_TIMEOUT=30                            # Connection timeout in seconds
HEARTBEAT_INTERVAL=30                            # Heartbeat interval in seconds
MESSAGE_QUEUE_SIZE=100                           # Per-connection message queue size

# Performance
WORKER_COUNT=2                                   # Number of worker processes
LOG_LEVEL=INFO                                   # Logging level
DEBUG_MODE=false                                 # Debug mode (never set to true in production)
```

### Configuration File

Edit `chetectWebsocket/settings.py`:

```python
# Settings class for gateway configuration
class Settings:
    MODEL_API_BASE_URL: str = "http://127.0.0.1:8000"
    WEBSOCKET_PORT: int = 8001
    WEBSOCKET_HOST: str = "0.0.0.0"
    MAX_CONNECTIONS: int = 100
    HEARTBEAT_INTERVAL: int = 30
    CONNECTION_TIMEOUT: int = 30
    MESSAGE_QUEUE_SIZE: int = 100
    ALLOWED_ORIGINS: List[str] = ["*"]
    LOG_LEVEL: str = "INFO"
```

## 🔌 WebSocket Protocol

### Connection

```javascript
// Client connects to gateway
const ws = new WebSocket('ws://localhost:8001/ws?session_id=session-123&user_role=invigilator');

// Connection established
ws.onopen = () => {
  console.log('Connected to gateway');
  // Send heartbeat
  ws.send(JSON.stringify({ type: 'ping' }));
};
```

### Message Types

#### Client → Gateway

**Frame Data**
```json
{
  "type": "frame",
  "session_id": "session-123",
  "timestamp": 1694184000000,
  "frame_data": "base64_encoded_image",
  "format": "jpeg"
}
```

**Video Chunk**
```json
{
  "type": "video_chunk",
  "session_id": "session-123",
  "chunk_index": 0,
  "timestamp": 1694184000000,
  "video_data": "base64_encoded_chunk"
}
```

**Heartbeat (Keep-alive)**
```json
{
  "type": "ping"
}
```

**Session Control**
```json
{
  "type": "session_control",
  "action": "start",  // or "stop", "pause", "resume"
  "session_id": "session-123"
}
```

#### Gateway → Client

**Frame Analysis Result**
```json
{
  "type": "frame_analysis",
  "session_id": "session-123",
  "timestamp": 1694184000000,
  "analysis": {
    "face_detected": true,
    "gaze_direction": [0.5, 0.3],
    "head_pose": { "pitch": 5.2, "yaw": -2.1, "roll": 0.8 },
    "blink_rate": 0.45,
    "suspicion_score": 0.32,
    "alert": false
  }
}
```

**Alert / Suspicious Event**
```json
{
  "type": "alert",
  "severity": "medium",  // low, medium, high, critical
  "session_id": "session-123",
  "timestamp": 1694184000000,
  "message": "Excessive gaze direction changes detected",
  "event_details": {
    "feature": "gaze_tracking",
    "threshold_exceeded": 0.75,
    "confidence": 0.89
  }
}
```

**Connection Acknowledgment**
```json
{
  "type": "ack",
  "message_id": "msg-123",
  "status": "received"
}
```

**Error**
```json
{
  "type": "error",
  "code": "INVALID_SESSION",
  "message": "Session not found",
  "details": {}
}
```

### Error Codes

| Code | Description |
|------|-------------|
| `INVALID_SESSION` | Session ID not found or invalid |
| `UNAUTHORIZED` | User not authorized for this session |
| `INVALID_MESSAGE` | Message format is invalid |
| `API_ERROR` | Error from CheatingDetector API |
| `CONNECTION_TIMEOUT` | Connection idle for too long |
| `QUEUE_FULL` | Message queue at capacity |

## 📡 API Endpoints

### Health Check

```bash
GET /health
# Response: { "status": "healthy", "timestamp": "2024-01-01T12:00:00Z" }
```

### WebSocket Endpoint

```
WS /ws[?session_id=<id>&user_role=<role>&client_id=<id>]
```

**Query Parameters:**
- `session_id` (required): Unique exam session identifier
- `user_role` (optional): "student" or "invigilator" (default: "student")
- `client_id` (optional): Unique client identifier

### REST Endpoints (for debugging/admin)

```bash
GET /sessions
# Get all active sessions

GET /sessions/<session_id>
# Get specific session details

POST /sessions/<session_id>/broadcast
# Send message to all clients in session

DELETE /sessions/<session_id>
# Close session and disconnect all clients
```

## 🔄 Data Flow

```
┌────────────────┐
│   myApp Client │  Connects to WebSocket
│  (Student or   │  ws://localhost:8001/ws
│  Invigilator)  │
└────────┬────────┘
         │
         │ WebSocket: Frame/Video Data
         ↓
┌─────────────────────────────┐
│  ChetectWebsocket Gateway   │
│  (This service)             │
│                             │
│  • Connection manager       │
│  • Message router           │
│  • Data transformer         │
└────────┬────────────────────┘
         │
         │ HTTP Multipart: Frame → API
         ↓
┌──────────────────────────────┐
│  CheatingDetector API        │
│  (Port 8000)                 │
│                              │
│  • Face detection            │
│  • Feature extraction        │
│  • Suspicion scoring         │
└────────┬─────────────────────┘
         │
         │ JSON Response: Analysis Result
         ↓
┌─────────────────────────────┐
│  ChetectWebsocket Gateway   │
│  (This service)             │
│                             │
│  • Format conversion        │
│  • Event generation         │
│  • Broadcasting             │
└────────┬────────────────────┘
         │
         │ WebSocket: Analysis + Alerts
         ↓
┌────────────────────┐
│  Invigilator Client│
│  (Real-time        │
│   monitoring view) │
└────────────────────┘
```

## 🧪 Testing

### Run Tests

```bash
# Basic test run
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=chetectWebsocket --cov-report=html

# Specific test file
python -m pytest tests/test_websocket_gateway.py -v
```

### Manual Testing with WebSocket

```javascript
// Browser console testing
const ws = new WebSocket('ws://localhost:8001/ws?session_id=test-session&user_role=student');

ws.onopen = () => {
  console.log('Connected');
  // Send test frame
  ws.send(JSON.stringify({
    type: 'frame',
    session_id: 'test-session',
    timestamp: Date.now(),
    frame_data: 'base64_image_data',
    format: 'jpeg'
  }));
};

ws.onmessage = (event) => {
  console.log('Received:', JSON.parse(event.data));
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected');
};
```

### Testing with curl/PostMan

```bash
# Health check
curl http://localhost:8001/health

# List active sessions
curl http://localhost:8001/sessions

# Get session details
curl http://localhost:8001/sessions/session-123
```

### Load Testing

```bash
# Using Apache Bench (ab)
ab -n 1000 -c 10 http://localhost:8001/health

# Using wrk (WebSocket load testing requires custom setup)
# See performance/wrk-websocket-test.lua
```

## 🚢 Deployment

### Docker

```bash
# Build image
docker build -t chetect-websocket:latest .

# Run container
docker run -p 8001:8001 \
  -e MODEL_API_BASE_URL="http://cheating-detector:8000" \
  -e ALLOWED_ORIGINS="*" \
  chetect-websocket:latest
```

### Docker Compose (with other services)

```yaml
version: '3.8'
services:
  cheating-detector:
    image: cheating-detector:latest
    ports:
      - "8000:8000"

  chetect-websocket:
    image: chetect-websocket:latest
    ports:
      - "8001:8001"
    environment:
      MODEL_API_BASE_URL: http://cheating-detector:8000
      ALLOWED_ORIGINS: "*"
    depends_on:
      - cheating-detector

  myapp:
    image: myapp:latest
    ports:
      - "8081:8081"
    environment:
      WEBSOCKET_URL: ws://chetect-websocket:8001
    depends_on:
      - chetect-websocket
```

### Heroku

```bash
# Install Heroku CLI
# Login to Heroku
heroku login

# Create app
heroku create chetect-websocket

# Set environment variables
heroku config:set MODEL_API_BASE_URL="https://cheating-detector.herokuapp.com" --app chetect-websocket
heroku config:set ALLOWED_ORIGINS="*" --app chetect-websocket

# Deploy
git push heroku main
```

### Manual Server Deployment

```bash
# On your server
git clone <repository>
cd chetectWebsocket

# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create systemd service
sudo tee /etc/systemd/system/chetect-websocket.service > /dev/null <<EOF
[Unit]
Description=Chetect WebSocket Gateway
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/path/to/chetectWebsocket
Environment="MODEL_API_BASE_URL=http://127.0.0.1:8000"
Environment="ALLOWED_ORIGINS=*"
ExecStart=/path/to/.venv/bin/uvicorn chetectWebsocket.app:app --host 0.0.0.0 --port 8001
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable chetect-websocket
sudo systemctl start chetect-websocket
```

### Nginx Reverse Proxy Configuration

```nginx
upstream websocket_backend {
    server localhost:8001;
}

server {
    listen 80;
    server_name api.chetect.com;

    location /ws {
        proxy_pass http://websocket_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket specific timeouts
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    location / {
        proxy_pass http://websocket_backend;
    }
}
```

## 🔍 Monitoring & Logging

### Logging

```python
# Configure logging in settings.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Health Monitoring

```bash
# Simple monitoring script
while true; do
  curl -s http://localhost:8001/health | jq .
  echo "---"
  sleep 5
done
```

### Metrics & Statistics

```bash
# View active sessions
curl http://localhost:8001/sessions | jq '.[]'

# Monitor connection count
watch -n 1 'curl -s http://localhost:8001/sessions | jq ". | length"'
```

## 🛠️ Troubleshooting

### Port Already in Use

```bash
# Find and kill process using port 8001
lsof -i :8001  # Unix/macOS
netstat -ano | findstr :8001  # Windows

kill -9 <PID>  # Unix/macOS
taskkill /PID <PID> /F  # Windows
```

### Connection Refused to CheatingDetector

```bash
# Check CheatingDetector is running
curl http://127.0.0.1:8000/health

# Update MODEL_API_BASE_URL if needed
export MODEL_API_BASE_URL="http://your-api-server:8000"
```

### Memory Leaks

```bash
# Monitor memory usage
# Linux
watch -n 1 'ps aux | grep uvicorn'

# Windows (PowerShell)
Get-Process | Where-Object {$_.ProcessName -like "*python*"}
```

### WebSocket Connection Timeout

```bash
# Increase connection timeout in settings
CONNECTION_TIMEOUT=60  # Increase from 30 seconds
```

### Too Many Open Files

```bash
# Increase file descriptor limit (Linux)
ulimit -n 4096

# Or in systemd service
[Service]
LimitNOFILE=4096
```

## 📖 Integration Examples

### React Client

```typescript
import { useEffect, useRef } from 'react';

export function ExamMonitor({ sessionId }: { sessionId: string }) {
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    ws.current = new WebSocket(`ws://localhost:8001/ws?session_id=${sessionId}`);

    ws.current.onopen = () => {
      console.log('Connected to gateway');
    };

    ws.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'alert') {
        // Handle alert
        console.log('Alert:', message.message);
      } else if (message.type === 'frame_analysis') {
        // Update UI with analysis results
        console.log('Analysis:', message.analysis);
      }
    };

    return () => {
      ws.current?.close();
    };
  }, [sessionId]);

  return <div>Exam Monitor</div>;
}
```

### Python Client

```python
import asyncio
import websockets
import json

async def connect_to_gateway():
    uri = "ws://localhost:8001/ws?session_id=test-session&user_role=student"
    
    async with websockets.connect(uri) as websocket:
        # Send frame
        message = {
            "type": "frame",
            "session_id": "test-session",
            "timestamp": int(time.time() * 1000),
            "frame_data": "base64_encoded_image",
            "format": "jpeg"
        }
        
        await websocket.send(json.dumps(message))
        
        # Receive analysis
        response = await websocket.recv()
        analysis = json.loads(response)
        print(f"Analysis: {analysis}")

asyncio.run(connect_to_gateway())
```

## 📚 Related Documentation

- [CheatingDetector API](../../CheatingDetector/README.md)
- [MyApp Documentation](../../chetect/myApp/README.md)
- [Main Project README](../../chetect/README.md)

## 📝 License

[Add your license information here]

## 👥 Contributors

Developed as part of the Chetect final year project at KNUST

## 📞 Support

For issues or questions, please refer to the project's issue tracker or contact the development team.
