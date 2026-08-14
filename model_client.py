from __future__ import annotations

from typing import Any

import httpx


class ModelApiError(RuntimeError):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Model API returned {status_code}: {detail}")


class ModelClient:
    def __init__(self, base_url: str, timeout_seconds: float = 120.0):
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
        )

    async def __aenter__(self) -> "ModelClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def create_session(self) -> str:
        response = await self._client.post("/api/v1/sessions")
        body = self._json_or_text(response)
        if response.is_error:
            raise ModelApiError(response.status_code, body)
        return str(body["session_id"])

    async def reset_session(self, session_id: str) -> dict[str, Any]:
        response = await self._client.post(f"/api/v1/sessions/{session_id}/reset")
        body = self._json_or_text(response)
        if response.is_error:
            raise ModelApiError(response.status_code, body)
        return body

    async def analyze_image(
        self,
        image_bytes: bytes,
        filename: str,
        content_type: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        data = self._form_fields(fields)
        files = {"image": (filename, image_bytes, content_type)}
        response = await self._client.post(
            "/api/v1/analyze/image",
            data=data,
            files=files,
        )
        return self._checked_json(response)

    async def analyze_video(
        self,
        video_bytes: bytes,
        filename: str,
        content_type: str,
        fields: dict[str, Any],
        response_mode: str = "summary",
    ) -> dict[str, Any]:
        data = self._form_fields(fields)
        endpoint = (
            "/api/v1/analyze/video/summary"
            if response_mode == "summary"
            else "/api/v1/analyze/video"
        )
        files = {"video": (filename, video_bytes, content_type)}
        response = await self._client.post(endpoint, data=data, files=files)
        return self._checked_json(response)

    async def analyze_landmarks(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post("/api/v1/analyze/landmarks", json=payload)
        return self._checked_json(response)

    async def score_features(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post("/api/v1/score", json=payload)
        return self._checked_json(response)

    @staticmethod
    def _form_fields(fields: dict[str, Any]) -> dict[str, str]:
        output = {}
        for key, value in fields.items():
            if value is None:
                continue
            if isinstance(value, bool):
                output[key] = "true" if value else "false"
            else:
                output[key] = str(value)
        return output

    @staticmethod
    def _json_or_text(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text

    @classmethod
    def _checked_json(cls, response: httpx.Response) -> dict[str, Any]:
        body = cls._json_or_text(response)
        if response.is_error:
            raise ModelApiError(response.status_code, body)
        return body

