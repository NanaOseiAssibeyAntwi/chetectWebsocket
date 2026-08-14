import base64
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

try:
    from chetectWebsocket.app import app
except ModuleNotFoundError:
    from app import app


class FakeModelClient:
    def __init__(self, *args, **kwargs):
        self.session_id = "test-session"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def create_session(self):
        return self.session_id

    async def reset_session(self, session_id):
        return {"reset": True, "session_id": session_id}

    async def analyze_image(self, image_bytes, filename, content_type, fields):
        return {
            "detected": True,
            "face_count": 1,
            "session_id": fields["session_id"],
            "features": {
                "gaze_x": 0.0,
                "gaze_y": 0.0,
                "blink_rate": 12.0,
                "head_yaw": 0.0,
                "head_pitch": 0.0,
                "head_roll": 0.0,
                "ear": 0.24,
            },
            "score": 0,
            "label": "NORMAL",
            "label_color": [0, 200, 0],
            "observations": ["ok"],
            "signals": [],
        }


class WebSocketGatewayTests(unittest.TestCase):
    def test_ping_and_image_frame(self):
        image_payload = base64.b64encode(b"fake-jpeg").decode("ascii")

        with patch(f"{app.__module__}.ModelClient", FakeModelClient):
            client = TestClient(app)
            with client.websocket_connect("/ws/analyze") as websocket:
                ready = websocket.receive_json()
                self.assertEqual(ready["type"], "ready")

                session = websocket.receive_json()
                self.assertEqual(session["type"], "session")
                self.assertEqual(session["session_id"], "test-session")

                websocket.send_json({"type": "ping"})
                pong = websocket.receive_json()
                self.assertEqual(pong["type"], "pong")

                websocket.send_json(
                    {
                        "type": "frame",
                        "sequence": 7,
                        "filename": "frame.jpg",
                        "content_type": "image/jpeg",
                        "image_base64": image_payload,
                    }
                )
                analysis = websocket.receive_json()
                self.assertEqual(analysis["type"], "analysis")
                self.assertEqual(analysis["kind"], "image")
                self.assertEqual(analysis["sequence"], 7)
                self.assertEqual(analysis["result"]["label"], "NORMAL")


if __name__ == "__main__":
    unittest.main()
