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
INTERVAL = float(os.environ.get("INGEST_INTERVAL", "2.0"))
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


FIRST_FRAME_TIMEOUT = float(os.environ.get("INGEST_FIRST_FRAME_TIMEOUT", "20"))
MAX_CONCURRENT = int(os.environ.get("INGEST_MAX_CONCURRENT", "8"))
DWELL = float(os.environ.get("INGEST_DWELL", "2.5"))


def _capture_once(ext_id: str, source: str) -> bool:
    """Open a feed, wait patiently for the first frame (the grid replays a
    buffered GOP on connect, so it can take 15-20s), publish the freshest frame
    seen over a short dwell window, then CLOSE — freeing the slot for the next
    camera. This bounds concurrent streams (and CPU/bandwidth) to the pool size
    while still refreshing every feed in rotation."""
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
        latest = None
        while time.time() < deadline:
            ok, f = cap.read()
            if ok and f is not None:
                latest = f
                break
            time.sleep(0.2)
        if latest is None:
            raise RuntimeError("no first frame")
        # dwell so we publish a current frame, not the replayed GOP head
        end = time.time() + DWELL
        while time.time() < end:
            ok, f = cap.read()
            if ok and f is not None:
                latest = f
            time.sleep(0.2)
        _publish(ext_id, latest)
        _set_status(ext_id, "live", "Frames flowing")
        return True
    except Exception:
        _set_status(ext_id, "down", "No frames — feed unreachable")
        return False
    finally:
        if cap is not None:
            cap.release()


_rot_lock = threading.Lock()


def _pool_worker(rotation) -> None:
    while True:
        with _rot_lock:
            ext_id, source = next(rotation)
        _capture_once(ext_id, source)
        time.sleep(0.15)


def main() -> None:
    import itertools
    cams = _load_cameras()
    if os.environ.get("INGEST_ONLY_LOCAL") == "1":
        cams = [(e, u) for (e, u) in cams if e in LOCAL_SOURCES]
    prepared = []
    for ext_id, url in cams:
        local = LOCAL_SOURCES.get(ext_id)
        prepared.append((ext_id, local if local is not None else _with_credentials(url)))
    pool = min(MAX_CONCURRENT, len(prepared)) or 1
    print(f"[ingest] rotating pool — {len(prepared)} feeds, {pool} concurrent, "
          f"dwell={DWELL}s, no-ML", flush=True)
    rotation = itertools.cycle(prepared)
    for _ in range(pool):
        threading.Thread(target=_pool_worker, args=(rotation,), daemon=True).start()
        time.sleep(0.3)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
