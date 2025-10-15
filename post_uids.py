#!/usr/bin/env python3
"""
Post UID status updates to the TCL service.

Usage examples:
  python post_uids.py 0000900025680613139000041
  python post_uids.py --uids-file uids.txt
  python post_uids.py --environment uat --insecure --uids-file uids.txt
"""
import argparse
import datetime
import json
import ssl
import sys
import time
from pathlib import Path
from typing import List, Optional
import urllib.error
import urllib.request

ENDPOINTS = {
    "prod": "https://vsintra.rd.go.th/rd-common-tcl-service/tcl/setFormStatusRESTful/vatpos",
    "uat": "https://vsintra-uat.rd.go.th/rd-common-tcl-service/tcl/setFormStatusRESTful/vatpos",
}
PAYLOAD_TEMPLATE = {
    "DLN": None,
    "newStatusCode": "LA",
    "numberType": "U",
}
LOG_DIR = Path("log")
TIMESTAMP_FMT = "%Y-%m-%d-%H.%M.%S.%f"


def read_uids_from_file(path: Path) -> List[str]:
    if not path.exists():
        return []
    lines = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            lines.append(line)
    return lines


def build_payload(uid: str) -> dict:
    payload = dict(PAYLOAD_TEMPLATE)
    payload["UID"] = uid
    return payload


def build_ssl_context(skip_verify: bool, cafile: Optional[Path]) -> ssl.SSLContext:
    if skip_verify:
        return ssl._create_unverified_context()
    context = ssl.create_default_context()
    if cafile:
        context.load_verify_locations(cafile=str(cafile))
    return context


def post_uid(uid: str, timeout: float, url: str, context: ssl.SSLContext) -> tuple[int, str]:
    payload = build_payload(uid)
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            return response.status, response_body
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, error_body
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Failed to reach server for UID {uid!r}: {exc}") from exc


def write_log(log_handle, environment: str, uid: str, status: str, response_body: str) -> None:
    entry = {
        "timestamp": datetime.datetime.now().strftime(TIMESTAMP_FMT),
        "environment": environment,
        "uid": uid,
        "status": status,
        "response": response_body,
    }
    log_handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    log_handle.flush()


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Post UID status updates to the TCL service.")
    parser.add_argument("uids", nargs="*", help="UIDs to send. If omitted, use --uids-file contents.")
    parser.add_argument(
        "--uids-file",
        default="uids.txt",
        help="Path to a file containing one UID per line (default: uids.txt).",
    )
    parser.add_argument(
        "--environment",
        choices=sorted(ENDPOINTS),
        default="prod",
        help="Endpoint environment to call (default: prod).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds (default: 10).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without sending requests.",
    )
    parser.add_argument(
        "--cafile",
        type=Path,
        help="Path to a custom CA bundle for SSL verification.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip SSL certificate verification (use only for trusted test environments).",
    )
    args = parser.parse_args(argv)

    if args.cafile and args.insecure:
        parser.error("--cafile and --insecure cannot be used together.")
    if args.cafile and not args.cafile.exists():
        parser.error(f"CA file not found: {args.cafile}")

    uids: List[str] = []
    if args.uids:
        uids.extend(uid.strip() for uid in args.uids if uid.strip())

    if not uids:
        file_uids = read_uids_from_file(Path(args.uids_file))
        if file_uids:
            uids.extend(file_uids)

    if not uids:
        parser.error("No UIDs provided. Supply them as arguments or in --uids-file.")

    endpoint_url = ENDPOINTS[args.environment]
    ssl_context = build_ssl_context(args.insecure, args.cafile)

    seen = set()
    ordered_uids = []
    for uid in uids:
        if uid not in seen:
            seen.add(uid)
            ordered_uids.append(uid)

    log_handle = None
    log_path: Optional[Path] = None
    if not args.dry_run:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"{datetime.datetime.now().strftime(TIMESTAMP_FMT)}.log"
        log_handle = log_path.open("a", encoding="utf-8")

    try:
        for index, uid in enumerate(ordered_uids):
            payload = build_payload(uid)
            if args.dry_run:
                print(f"DRY-RUN {args.environment} {uid}: {json.dumps(payload, ensure_ascii=False)}")
                continue
            try:
                status_code, response_body = post_uid(uid, args.timeout, endpoint_url, ssl_context)
                print(f"{args.environment} {uid}: {status_code} -> {response_body}")
                if log_handle is not None:
                    write_log(log_handle, args.environment, uid, str(status_code), response_body)
            except ConnectionError as exc:
                print(exc, file=sys.stderr)
                if log_handle is not None:
                    write_log(log_handle, args.environment, uid, "error", str(exc))
                return 1
            if index + 1 < len(ordered_uids):
                time.sleep(3)
    finally:
        if log_handle is not None:
            log_handle.close()
            if log_path is not None:
                print(f"Log written to {log_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
