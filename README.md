# Chetect WebSocket Gateway

This is a separate WebSocket gateway for real-time exam analysis. It does not run
MediaPipe/OpenCV itself. It receives frames, video chunks, landmarks, or extracted
features from a client and forwards them to the hosted CheatingDetector API.

## Local Run

From the repository root:

```bash
pip install -r chetectWebsocket/requirements.txt
set MODEL_API_BASE_URL=http://127.0.0.1:8000
uvicorn chetectWebsocket.app:app --reload --port 8010
```

On PowerShell:

```powershell
$env:MODEL_API_BASE_URL="https://your-ai-model-app.azurewebsites.net"
uvicorn chetectWebsocket.app:app --reload --port 8010
```

Open:

- `GET /health`
- `WS /ws/analyze`

## Required Environment Variable

```txt
MODEL_API_BASE_URL=https://your-ai-model-app.azurewebsites.net
```

Do not include a trailing slash.

## Useful Environment Variables

```txt
ALLOWED_ORIGINS=*
AUTO_CREATE_MODEL_SESSION=true
MODEL_API_TIMEOUT_SECONDS=120
MAX_PAYLOAD_BYTES=8388608
DEFAULT_INFERENCE_MAX_WIDTH=480
DEFAULT_SAMPLE_EVERY_N_FRAMES=10
DEFAULT_MAX_FRAMES=20
DEFAULT_MAX_ALERTS=3
DEFAULT_VIDEO_RESPONSE_MODE=summary
```

## Azure Startup Command

If the Web App deploys from the repository root:

```txt
gunicorn -w 1 -k uvicorn.workers.UvicornWorker chetectWebsocket.app:app --bind=0.0.0.0:8000 --timeout 180
```

If the Web App deploys only the `chetectWebsocket` folder as its root:

```txt
gunicorn -w 1 -k uvicorn.workers.UvicornWorker app:app --bind=0.0.0.0:8000 --timeout 180
```

## Message Flow

The server sends this after connection:

```json
{
  "type": "ready",
  "message": "Connected to Chetect WebSocket Gateway."
}
```

By default, the gateway creates a model session and sends:

```json
{
  "type": "session",
  "session_id": "..."
}
```

### Ping

```json
{ "type": "ping" }
```

Response:

```json
{ "type": "pong", "timestamp": 1234567890.0 }
```

### Send An Image Frame

```json
{
  "type": "frame",
  "sequence": 1,
  "filename": "frame.jpg",
  "content_type": "image/jpeg",
  "image_base64": "/9j/4AAQSkZJRgABAQ..."
}
```

Response:

```json
{
  "type": "analysis",
  "kind": "image",
  "sequence": 1,
  "processing_ms": 123,
  "session_id": "...",
  "result": {
    "detected": true,
    "label": "NORMAL",
    "score": 0
  }
}
```

### Send Binary Frames

You may send raw binary WebSocket messages. By default they are treated as JPEG
image frames. To treat binary messages as video chunks:

```json
{
  "type": "configure",
  "binary_kind": "video_chunk",
  "binary_content_type": "video/mp4",
  "binary_filename": "chunk.mp4",
  "response_mode": "summary",
  "sample_every_n_frames": 10,
  "max_frames": 20,
  "inference_max_width": 480
}
```

### Send A Video Chunk As Base64

```json
{
  "type": "video_chunk",
  "sequence": 2,
  "filename": "chunk.mp4",
  "content_type": "video/mp4",
  "response_mode": "summary",
  "sample_every_n_frames": 10,
  "max_frames": 20,
  "inference_max_width": 480,
  "video_base64": "AAAAIGZ0eXBpc29t..."
}
```

### Send Landmarks

```json
{
  "type": "landmarks",
  "sequence": 3,
  "face_count": 1,
  "landmarks": [
    { "id": 1, "x": 0.5, "y": 0.48, "z": 0, "pixel_x": 500, "pixel_y": 480 }
  ]
}
```

### Send Extracted Features

```json
{
  "type": "features",
  "sequence": 4,
  "face_count": 1,
  "features": {
    "gaze_x": 0.1,
    "gaze_y": 0.0,
    "blink_rate": 12.0,
    "head_yaw": 3.0,
    "head_pitch": 1.0,
    "head_roll": 0.5,
    "ear": 0.24
  }
}
```

## Error Response

```json
{
  "type": "error",
  "code": "MODEL_API_ERROR",
  "message": "The model API rejected the request.",
  "status_code": 422,
  "detail": {}
}
```

