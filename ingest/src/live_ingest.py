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
  SENTINEL_EMAIL          approved-access email; injected into each rtsp:// url
  SENTINEL_ACCESS_PASSWORD  access password; injected as the url password

The Sentinel grid authenticates every RTSP connection with the registered email
+ access password embedded in the URL (rtsp://email:password@...). Credentials
are read from the environment and injected at connect time — they are never
stored in the registry, logged, or committed.
"""
from __future__ import annotations

import os
import threading
import time
from urllib.parse import quote

os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    f"rtsp_transport;tcp|stimeout;{int(float(os.environ.get('INGEST_OPEN_TIMEOUT', '20')) * 1_000_000)}",
)

import cv2
import psycopg2
import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DB_DSN = os.environ.get("INGEST_DB_DSN", "host=localhost dbname=setunetra user=setunetra password=changeme")
INTERVAL = float(os.environ.get("INGEST_INTERVAL", "4.0"))  # decode+publish cadence; higher = more concurrent feeds hold on a modest host
JPEG_WIDTH = int(os.environ.get("INGEST_JPEG_WIDTH", "640"))
FRAME_TTL = int(os.environ.get("INGEST_FRAME_TTL", "90"))  # frames persist between rotation visits
SENTINEL_EMAIL = os.environ.get("SENTINEL_EMAIL", "").strip()
SENTINEL_PW = os.environ.get("SENTINEL_ACCESS_PASSWORD", "").strip()


def _with_credentials(url: str) -> str:
    """Embed the approved email + access password into an rtsp:// URL, exactly as
    the Sentinel grid requires (rtsp://email:password@host...). Both are
    percent-encoded (the '@' in an email must become %40). Non-rtsp URLs and URLs
    that already carry credentials are returned unchanged. Secrets never touch the
    DB or logs — they live only in this in-memory string handed to the decoder."""
    if not url.lower().startswith("rtsp://") or not (SENTINEL_EMAIL and SENTINEL_PW):
        return url
    rest = url[len("rtsp://"):]
    if "@" in rest.split("/", 1)[0]:  # already has userinfo
        return url
    return f"rtsp://{quote(SENTINEL_EMAIL, safe='')}:{quote(SENTINEL_PW, safe='')}@{rest}"

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


FIRST_FRAME_TIMEOUT = float(os.environ.get("INGEST_FIRST_FRAME_TIMEOUT", "25"))
LOST_TIMEOUT = float(os.environ.get("INGEST_LOST_TIMEOUT", "15"))
# The grid enforces a per-account CONCURRENT-STREAM cap; opening more than it
# allows gets the whole account temporarily rejected. So we hold at most
# MAX_CONCURRENT streams at once (well under the cap) and rotate through the rest,
# holding each live for HOLD_SECONDS before releasing its slot to the next camera.
MAX_CONCURRENT = int(os.environ.get("INGEST_MAX_CONCURRENT", "8"))
HOLD_SECONDS = float(os.environ.get("INGEST_HOLD_SECONDS", "90"))

from collections import deque  # noqa: E402

_queue: deque = deque()
_queue_lock = threading.Lock()


def _next_camera():
    with _queue_lock:
        item = _queue.popleft()
        _queue.append(item)  # round-robin
        return item


def _hold(ext_id: str, source: str) -> None:
    """Hold one feed live for up to HOLD_SECONDS, then release the slot.

    grab() keeps the stream current (paced to its own frame rate); we decode
    (retrieve) + publish only every INTERVAL. The grid replays a buffered GOP on
    connect (first frame ~15-20s), loops with a hard cut and has inter-frame gaps
    — all tolerated. On any failure the camera is marked down and the slot rotates
    to the next one, so a dead feed never wedges a slot for long."""
    cap = None
    try:
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            raise RuntimeError("open failed")
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        deadline = time.time() + FIRST_FRAME_TIMEOUT
        first = None
        while time.time() < deadline:
            if cap.grab():
                ok, f = cap.retrieve()
                if ok and f is not None:
                    first = f
                    break
            else:
                time.sleep(0.1)
        if first is None:
            raise RuntimeError("no first frame")
        _publish(ext_id, first)
        _set_status(ext_id, "live", "Frames flowing")
        end = time.time() + HOLD_SECONDS
        last_pub = time.time()
        last_ok = time.time()
        while time.time() < end:
            if cap.grab():
                last_ok = time.time()
                if time.time() - last_pub >= INTERVAL:
                    ok, f = cap.retrieve()
                    if ok and f is not None:
                        _publish(ext_id, f)
                        last_pub = time.time()
            else:
                if time.time() - last_ok > LOST_TIMEOUT:
                    raise RuntimeError("stream lost")
                time.sleep(0.1)
    except Exception:
        _set_status(ext_id, "down", "No frames — feed unavailable")
    finally:
        if cap is not None:
            cap.release()


def _slot_worker() -> None:
    while True:
        ext_id, source = _next_camera()
        _hold(ext_id, source)
        time.sleep(0.5)  # pace between opens so we never stampede the grid


def main() -> None:
    cams = _load_cameras()
    if os.environ.get("INGEST_ONLY_LOCAL") == "1":
        cams = [(e, u) for (e, u) in cams if e in LOCAL_SOURCES]
    for ext_id, url in cams:
        local = LOCAL_SOURCES.get(ext_id)
        _queue.append((ext_id, local if local is not None else _with_credentials(url)))
    pool = min(MAX_CONCURRENT, len(_queue)) or 1
    print(f"[ingest] bounded rotating pool — {pool} concurrent (cap-safe), "
          f"holding {HOLD_SECONDS:.0f}s each, cycling {len(_queue)} feeds, no-ML", flush=True)
    for _ in range(pool):
        threading.Thread(target=_slot_worker, daemon=True).start()
        time.sleep(0.5)  # gentle staggered ramp-up
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
