from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib import error, request


API_URL = "http://10.5.30.112:9080/rd-vatjob-process/job/VATQR010JobAPIService"
NID_FILE = Path(__file__).resolve().parent / "nid.txt"
LOG_FILE = Path(__file__).resolve().parent / "tqr010.log"

logger = logging.getLogger("tqr010")


def setup_logging() -> None:
    """Configure logging to write to both file and console."""
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


def load_nids(source: Path) -> list[str]:
    """Read NIDs from file, ignoring comments and blank lines."""
    if not source.exists():
        raise FileNotFoundError(f"Cannot locate nid file: {source}")
    nids: list[str] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        nids.append(stripped)
    if not nids:
        raise ValueError("No NIDs found in nid.txt")
    return nids


def post_nid(nid: str) -> None:
    payload = json.dumps({"typePreProcess": "N", "nid": nid}).encode("utf-8")
    req = request.Request(
        API_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            logger.info("[%s] %s %s: %s", nid, resp.status, resp.reason, body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error("[%s] HTTP %s: %s", nid, exc.code, body)
    except Exception as exc:
        logger.exception("[%s] FAILED: %s", nid, exc)


def main() -> None:
    setup_logging()
    for nid in load_nids(NID_FILE):
        post_nid(nid)


if __name__ == "__main__":
    main()
