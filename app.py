from __future__ import annotations

import base64
import binascii
import time
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware

from chetectWebsocket.model_client import ModelApiError, ModelClient
from chetectWebsocket.settings import settings

app = FastAPI(
    title="Chetect WebSocket Gateway",
    version="1.0.0",
    description=(
        "A lightweight WebSocket gateway that forwards real-time frames, "
        "video chunks, landmarks, or extracted features to the CheatingDetector API."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=settings.allowed_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass
class ConnectionState:
    session_id: str | None = None
    binary_kind: str = "image"
    binary_content_type: str = "image/jpeg"
    binary_filename: str = "frame.jpg"
    sequence: int = 0
    include_landmarks: bool = False
    include_frame_results: bool = False
    inference_max_width: int = settings.default_inference_max_width
    sample_every_n_frames: int = settings.default_sample_every_n_frames
    max_frames: int = settings.default_max_frames
    max_alerts: int = settings.default_max_alerts
    camera_mirrored: bool = False
    force_rotate: str = "none"
    video_response_mode: str = settings.default_video_response_mode


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "name": "Chetect WebSocket Gateway",
        "health": "/health",
        "websocket": "/ws/analyze",
        "model_api_base_url": settings.model_api_base_url,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/analyze")
async def analyze_socket(websocket: WebSocket) -> None:
    if not _origin_allowed(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    state = ConnectionState(
        session_id=websocket.query_params.get("session_id") or None,
        binary_kind=websocket.query_params.get("binary_kind", "image"),
    )

    async with ModelClient(
        base_url=settings.model_api_base_url,
        timeout_seconds=settings.model_api_timeout_seconds,
    ) as model_client:
        await _send(
            websocket,
            {
                "type": "ready",
                "message": "Connected to Chetect WebSocket Gateway.",
                "model_api_base_url": settings.model_api_base_url,
            },
        )

        auto_create_session = _query_bool(
            websocket.query_params.get("auto_create_session"),
            settings.auto_create_model_session,
        )
        if auto_create_session and not state.session_id:
            await _ensure_session(websocket, model_client, state)

        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    await _handle_binary(websocket, model_client, state, message["bytes"])
                    continue
                if message.get("text") is not None:
                    await _handle_json(websocket, model_client, state, message["text"])
        except WebSocketDisconnect:
            return


async def _handle_json(
    websocket: WebSocket,
    model_client: ModelClient,
    state: ConnectionState,
    raw_message: str,
) -> None:
    import json

    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        await _send_error(websocket, "INVALID_JSON", f"Could not parse JSON: {exc.msg}")
        return

    message_type = str(payload.get("type", "")).strip().lower()
    if message_type in {"", "frame"}:
        await _handle_image_message(websocket, model_client, state, payload)
    elif message_type == "video_chunk":
        await _handle_video_message(websocket, model_client, state, payload)
    elif message_type == "landmarks":
        await _handle_landmarks_message(websocket, model_client, state, payload)
    elif message_type in {"features", "score"}:
        await _handle_features_message(websocket, model_client, state, payload)
    elif message_type == "configure":
        _apply_configuration(state, payload)
        await _send(websocket, {"type": "configured", "state": _public_state(state)})
    elif message_type == "start":
        state.session_id = payload.get("session_id") or state.session_id
        if payload.get("create_session", not state.session_id):
            await _ensure_session(websocket, model_client, state, force=True)
        else:
            await _send(websocket, {"type": "session", "session_id": state.session_id})
    elif message_type == "reset":
        await _handle_reset(websocket, model_client, state)
    elif message_type == "ping":
        await _send(websocket, {"type": "pong", "timestamp": time.time()})
    elif message_type == "close":
        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
    else:
        await _send_error(
            websocket,
            "UNKNOWN_MESSAGE_TYPE",
            f"Unsupported message type: {message_type}",
        )


async def _handle_binary(
    websocket: WebSocket,
    model_client: ModelClient,
    state: ConnectionState,
    payload_bytes: bytes,
) -> None:
    state.sequence += 1
    if len(payload_bytes) > settings.max_payload_bytes:
        await _send_error(websocket, "PAYLOAD_TOO_LARGE", "Binary payload is too large.")
        return

    if state.binary_kind == "video_chunk":
        await _analyze_video_bytes(
            websocket=websocket,
            model_client=model_client,
            state=state,
            video_bytes=payload_bytes,
            filename=state.binary_filename or "chunk.mp4",
            content_type=state.binary_content_type or "video/mp4",
            sequence=state.sequence,
            overrides={},
        )
        return

    await _analyze_image_bytes(
        websocket=websocket,
        model_client=model_client,
        state=state,
        image_bytes=payload_bytes,
        filename=state.binary_filename or "frame.jpg",
        content_type=state.binary_content_type or "image/jpeg",
        sequence=state.sequence,
        overrides={},
    )


async def _handle_image_message(
    websocket: WebSocket,
    model_client: ModelClient,
    state: ConnectionState,
    payload: dict[str, Any],
) -> None:
    image_base64 = payload.get("image_base64") or payload.get("data")
    if not image_base64:
        await _send_error(websocket, "MISSING_IMAGE", "Send image_base64 or data.")
        return

    try:
        image_bytes = _decode_base64(str(image_base64))
    except ValueError as exc:
        await _send_error(websocket, "INVALID_BASE64", str(exc))
        return

    if len(image_bytes) > settings.max_payload_bytes:
        await _send_error(websocket, "PAYLOAD_TOO_LARGE", "Image payload is too large.")
        return

    sequence = _sequence(payload, state)
    await _analyze_image_bytes(
        websocket=websocket,
        model_client=model_client,
        state=state,
        image_bytes=image_bytes,
        filename=str(payload.get("filename") or "frame.jpg"),
        content_type=str(payload.get("content_type") or "image/jpeg"),
        sequence=sequence,
        overrides=payload,
    )


async def _handle_video_message(
    websocket: WebSocket,
    model_client: ModelClient,
    state: ConnectionState,
    payload: dict[str, Any],
) -> None:
    video_base64 = payload.get("video_base64") or payload.get("data")
    if not video_base64:
        await _send_error(websocket, "MISSING_VIDEO", "Send video_base64 or data.")
        return

    try:
        video_bytes = _decode_base64(str(video_base64))
    except ValueError as exc:
        await _send_error(websocket, "INVALID_BASE64", str(exc))
        return

    if len(video_bytes) > settings.max_payload_bytes:
        await _send_error(websocket, "PAYLOAD_TOO_LARGE", "Video payload is too large.")
        return

    sequence = _sequence(payload, state)
    await _analyze_video_bytes(
        websocket=websocket,
        model_client=model_client,
        state=state,
        video_bytes=video_bytes,
        filename=str(payload.get("filename") or "chunk.mp4"),
        content_type=str(payload.get("content_type") or "video/mp4"),
        sequence=sequence,
        overrides=payload,
    )


async def _handle_landmarks_message(
    websocket: WebSocket,
    model_client: ModelClient,
    state: ConnectionState,
    payload: dict[str, Any],
) -> None:
    if not payload.get("landmarks"):
        await _send_error(websocket, "MISSING_LANDMARKS", "Send landmarks.")
        return

    sequence = _sequence(payload, state)
    request_payload = {
        "session_id": payload.get("session_id") or state.session_id,
        "face_count": payload.get("face_count", 1),
        "landmarks": payload["landmarks"],
        "classifier_output": payload.get("classifier_output"),
        "confidence": payload.get("confidence", 1.0),
    }

    started_at = time.perf_counter()
    try:
        await _ensure_session(websocket, model_client, state)
        request_payload["session_id"] = state.session_id
        result = await model_client.analyze_landmarks(request_payload)
        await _send_analysis(websocket, "landmarks", sequence, result, started_at)
    except ModelApiError as exc:
        await _send_model_error(websocket, exc, sequence)
    except Exception as exc:
        await _send_error(websocket, "GATEWAY_ERROR", str(exc), sequence=sequence)


async def _handle_features_message(
    websocket: WebSocket,
    model_client: ModelClient,
    state: ConnectionState,
    payload: dict[str, Any],
) -> None:
    if not payload.get("features"):
        await _send_error(websocket, "MISSING_FEATURES", "Send features.")
        return

    sequence = _sequence(payload, state)
    request_payload = {
        "session_id": payload.get("session_id") or state.session_id,
        "face_count": payload.get("face_count", 1),
        "features": payload["features"],
        "classifier_output": payload.get("classifier_output"),
        "confidence": payload.get("confidence", 1.0),
    }

    started_at = time.perf_counter()
    try:
        await _ensure_session(websocket, model_client, state)
        request_payload["session_id"] = state.session_id
        result = await model_client.score_features(request_payload)
        await _send_analysis(websocket, "features", sequence, result, started_at)
    except ModelApiError as exc:
        await _send_model_error(websocket, exc, sequence)
    except Exception as exc:
        await _send_error(websocket, "GATEWAY_ERROR", str(exc), sequence=sequence)


async def _handle_reset(
    websocket: WebSocket,
    model_client: ModelClient,
    state: ConnectionState,
) -> None:
    if not state.session_id:
        await _send_error(websocket, "NO_SESSION", "No model session exists yet.")
        return
    try:
        result = await model_client.reset_session(state.session_id)
        await _send(websocket, {"type": "session_reset", "session_id": state.session_id, "result": result})
    except ModelApiError as exc:
        await _send_model_error(websocket, exc)


async def _analyze_image_bytes(
    websocket: WebSocket,
    model_client: ModelClient,
    state: ConnectionState,
    image_bytes: bytes,
    filename: str,
    content_type: str,
    sequence: int,
    overrides: dict[str, Any],
) -> None:
    started_at = time.perf_counter()
    fields = {
        "session_id": overrides.get("session_id") or state.session_id,
        "classifier_output": overrides.get("classifier_output"),
        "confidence": overrides.get("confidence", 1.0),
    }

    try:
        await _ensure_session(websocket, model_client, state)
        fields["session_id"] = state.session_id
        result = await model_client.analyze_image(
            image_bytes=image_bytes,
            filename=filename,
            content_type=content_type,
            fields=fields,
        )
        await _send_analysis(websocket, "image", sequence, result, started_at)
    except ModelApiError as exc:
        await _send_model_error(websocket, exc, sequence)
    except Exception as exc:
        await _send_error(websocket, "GATEWAY_ERROR", str(exc), sequence=sequence)


async def _analyze_video_bytes(
    websocket: WebSocket,
    model_client: ModelClient,
    state: ConnectionState,
    video_bytes: bytes,
    filename: str,
    content_type: str,
    sequence: int,
    overrides: dict[str, Any],
) -> None:
    started_at = time.perf_counter()
    response_mode = str(overrides.get("response_mode") or state.video_response_mode).lower()
    if response_mode not in {"summary", "full"}:
        response_mode = "summary"

    fields = {
        "session_id": overrides.get("session_id") or state.session_id,
        "classifier_output": overrides.get("classifier_output"),
        "confidence": overrides.get("confidence", 1.0),
        "sample_every_n_frames": overrides.get("sample_every_n_frames", state.sample_every_n_frames),
        "max_frames": overrides.get("max_frames", state.max_frames),
        "include_landmarks": overrides.get("include_landmarks", state.include_landmarks),
        "inference_max_width": overrides.get("inference_max_width", state.inference_max_width),
        "include_frame_results": overrides.get("include_frame_results", state.include_frame_results),
        "max_alerts": overrides.get("max_alerts", state.max_alerts),
        "camera_mirrored": overrides.get("camera_mirrored", state.camera_mirrored),
        "force_rotate": overrides.get("force_rotate", state.force_rotate),
        "save_debug_frame": overrides.get("save_debug_frame", False),
    }

    try:
        await _ensure_session(websocket, model_client, state)
        fields["session_id"] = state.session_id
        result = await model_client.analyze_video(
            video_bytes=video_bytes,
            filename=filename,
            content_type=content_type,
            fields=fields,
            response_mode=response_mode,
        )
        await _send_analysis(websocket, "video_chunk", sequence, result, started_at)
    except ModelApiError as exc:
        await _send_model_error(websocket, exc, sequence)
    except Exception as exc:
        await _send_error(websocket, "GATEWAY_ERROR", str(exc), sequence=sequence)


async def _ensure_session(
    websocket: WebSocket,
    model_client: ModelClient,
    state: ConnectionState,
    force: bool = False,
) -> None:
    if state.session_id and not force:
        return
    state.session_id = await model_client.create_session()
    await _send(websocket, {"type": "session", "session_id": state.session_id})


def _apply_configuration(state: ConnectionState, payload: dict[str, Any]) -> None:
    state.binary_kind = str(payload.get("binary_kind", state.binary_kind)).lower()
    state.binary_content_type = str(payload.get("binary_content_type", state.binary_content_type))
    state.binary_filename = str(payload.get("binary_filename", state.binary_filename))
    state.include_landmarks = _bool(payload.get("include_landmarks"), state.include_landmarks)
    state.include_frame_results = _bool(payload.get("include_frame_results"), state.include_frame_results)
    state.inference_max_width = _int(payload.get("inference_max_width"), state.inference_max_width)
    state.sample_every_n_frames = _int(payload.get("sample_every_n_frames"), state.sample_every_n_frames)
    state.max_frames = _int(payload.get("max_frames"), state.max_frames)
    state.max_alerts = _int(payload.get("max_alerts"), state.max_alerts)
    state.camera_mirrored = _bool(payload.get("camera_mirrored"), state.camera_mirrored)
    state.force_rotate = str(payload.get("force_rotate", state.force_rotate)).lower()
    state.video_response_mode = str(payload.get("response_mode", state.video_response_mode)).lower()
    if state.binary_kind not in {"image", "video_chunk"}:
        state.binary_kind = "image"
    if state.video_response_mode not in {"summary", "full"}:
        state.video_response_mode = "summary"


def _decode_base64(value: str) -> bytes:
    payload = value.strip()
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Payload is not valid base64.") from exc


def _sequence(payload: dict[str, Any], state: ConnectionState) -> int:
    if payload.get("sequence") is not None:
        return _int(payload.get("sequence"), state.sequence + 1)
    state.sequence += 1
    return state.sequence


def _origin_allowed(websocket: WebSocket) -> bool:
    if settings.allowed_origins == ["*"]:
        return True
    origin = websocket.headers.get("origin")
    return origin in settings.allowed_origins


def _query_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return _bool(value, default)


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _public_state(state: ConnectionState) -> dict[str, Any]:
    return {
        "session_id": state.session_id,
        "binary_kind": state.binary_kind,
        "binary_content_type": state.binary_content_type,
        "binary_filename": state.binary_filename,
        "include_landmarks": state.include_landmarks,
        "include_frame_results": state.include_frame_results,
        "inference_max_width": state.inference_max_width,
        "sample_every_n_frames": state.sample_every_n_frames,
        "max_frames": state.max_frames,
        "max_alerts": state.max_alerts,
        "camera_mirrored": state.camera_mirrored,
        "force_rotate": state.force_rotate,
        "video_response_mode": state.video_response_mode,
    }


async def _send_analysis(
    websocket: WebSocket,
    kind: str,
    sequence: int,
    result: dict[str, Any],
    started_at: float,
) -> None:
    await _send(
        websocket,
        {
            "type": "analysis",
            "kind": kind,
            "sequence": sequence,
            "processing_ms": round((time.perf_counter() - started_at) * 1000),
            "session_id": result.get("session_id"),
            "result": result,
        },
    )


async def _send_model_error(
    websocket: WebSocket,
    exc: ModelApiError,
    sequence: int | None = None,
) -> None:
    await _send_error(
        websocket,
        "MODEL_API_ERROR",
        "The model API rejected the request.",
        sequence=sequence,
        detail=exc.detail,
        status_code=exc.status_code,
    )


async def _send_error(
    websocket: WebSocket,
    code: str,
    message: str,
    sequence: int | None = None,
    detail: Any = None,
    status_code: int | None = None,
) -> None:
    payload = {
        "type": "error",
        "code": code,
        "message": message,
    }
    if sequence is not None:
        payload["sequence"] = sequence
    if detail is not None:
        payload["detail"] = detail
    if status_code is not None:
        payload["status_code"] = status_code
    await _send(websocket, payload)


async def _send(websocket: WebSocket, payload: dict[str, Any]) -> None:
    await websocket.send_json(payload)

