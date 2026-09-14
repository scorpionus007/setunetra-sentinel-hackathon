"""SetuNetra live ingest — CPU-light, NO ML.

Reads the camera registry from Postgres, connects to each camera's real RTSP
url, decodes one frame every INGEST_INTERVAL seconds (nothing more — no
inference), publishes a small JPEG to Redis `latest_frame:{external_id}`, and
writes truthful health/status back to the registry. Cameras that cannot be
reached are marked offline; frames are never fabricated.

Env:
  REDIS_URL                redis connection (default redis://localhost:6379/0)
  INGEST_DB_DSN            psycopg2 DSN (default local setunetra/changeme)
  INGEST_INTERVAL         seconds between grabbed frames per camera (default 2.0)
  INGEST_JPEG_WIDTH       downscale width for published frames (default 640)
  INGEST_OPEN_TIMEOUT     per-connection open timeout, seconds (default 8)
  INGEST_LOCAL_SOURCES    "extid=path;extid=path" — use a local file as a
                          camera's source instead of its RTSP url (for demo /
                          pipeline verification when the live grid is unreachable)
"""
from __future__ import annotations

import os
import threading
import time

os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    f"rtsp_transport;tcp|stimeout;{int(float(os.environ.get('INGEST_OPEN_TIMEOUT', '8')) * 1_000_000)}",
)

import cv2
import psycopg2
import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DB_DSN = os.environ.get("INGEST_DB_DSN", "host=localhost dbname=setunetra user=setunetra password=changeme")
INTERVAL = float(os.environ.get("INGEST_INTERVAL", "2.0"))
JPEG_WIDTH = int(os.environ.get("INGEST_JPEG_WIDTH", "640"))
FRAME_TTL = 12

r = redis.Redis.from_url(REDIS_URL)
_db_lock = threading.Lock()
_db = psycopg2.connect(DB_DSN)
_db.autocommit = True


def _parse_local_sources() -> dict[str, str]:
    out: dict[str, str] = {}
    raw = os.environ.get("INGEST_LOCAL_SOURCES", "").strip()
    for pair in raw.split(";"):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            out[k.strip()] = v.strip()
    return out


LOCAL_SOURCES = _parse_local_sources()


def _load_cameras() -> list[tuple[str, str]]:
    with _db_lock, _db.cursor() as cur:
        cur.execute("SELECT external_id, rtsp_url FROM cameras ORDER BY external_id")
        return [(str(x[0]), x[1]) for x in cur.fetchall()]


def _set_status(ext_id: str, status: str, note: str | None = None) -> None:
    with _db_lock, _db.cursor() as cur:
        cur.execute("UPDATE cameras SET status=%s, last_seen=now() WHERE external_id=%s", (status, ext_id))
        cur.execute(
            "INSERT INTO camera_health (camera_id, status, last_frame_ts, note) "
            "SELECT id, %s, now(), %s FROM cameras WHERE external_id=%s",
            (status, note, ext_id),
        )


def _publish(ext_id: str, frame) -> bool:
    h, w = frame.shape[:2]
    if w > JPEG_WIDTH:
        frame = cv2.resize(frame, (JPEG_WIDTH, int(h * JPEG_WIDTH / w)))
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
    if not ok:
        return False
    r.setex(f"latest_frame:{ext_id}", FRAME_TTL, buf.tobytes())
    return True


def _worker(ext_id: str, rtsp_url: str) -> None:
    source = LOCAL_SOURCES.get(ext_id, rtsp_url)
    is_local = not str(source).lower().startswith(("rtsp://", "http://", "https://"))
    cap = None
    online = None
    fail = 0
    while True:
        try:
            if cap is None or not cap.isOpened():
                if cap is not None:
                    cap.release()
                cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                if not cap.isOpened():
                    raise RuntimeError("open failed")
            ok, frame = cap.read()
            if not ok or frame is None:
                if is_local:  # loop the file
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = cap.read()
                if not ok or frame is None:
                    raise RuntimeError("read failed")
            if _publish(ext_id, frame):
                fail = 0
                if online is not True:
                    online = True
                    _set_status(ext_id, "live", "Local sample source" if is_local else "Frames flowing")
            time.sleep(INTERVAL)
        except Exception:
            fail += 1
            if cap is not None:
                cap.release()
                cap = None
            if online is not False and fail >= 2:
                online = False
                _set_status(ext_id, "down", "No frames — source unreachable")
            time.sleep(min(15, 3 * fail))


def main() -> None:
    cams = _load_cameras()
    # In an environment that cannot reach the live grid, INGEST_ONLY_LOCAL=1
    # runs just the locally-sourced cameras — so the pipeline is verifiable
    # without churning on unreachable feeds or writing misleading 'down' status.
    if os.environ.get("INGEST_ONLY_LOCAL") == "1":
        cams = [(e, u) for (e, u) in cams if e in LOCAL_SOURCES]
    print(f"[ingest] starting {len(cams)} camera workers "
          f"({len(LOCAL_SOURCES)} local source(s)), interval={INTERVAL}s, no-ML")
    threads = []
    for ext_id, url in cams:
        t = threading.Thread(target=_worker, args=(ext_id, url), daemon=True, name=f"cam-{ext_id}")
        t.start()
        threads.append(t)
        time.sleep(0.08)  # stagger connection setup
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("[ingest] stopping")


if __name__ == "__main__":
    main()
