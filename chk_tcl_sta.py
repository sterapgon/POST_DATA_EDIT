"""Fetches tax form information for VAT POS UIDs and logs the responses."""

import argparse
import csv
import json
import ssl
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import List, Optional, Tuple
from urllib import error, request

ENV_URLS = {
    "prod": "https://vsintra.rd.go.th/rd-common-tcl-service/tcl/getTaxFormInformation2/vatpos?uid=",
    "uat": "https://vsintra-uat.rd.go.th/rd-common-tcl-service/tcl/getTaxFormInformation2/vatpos?uid=",
}
DEFAULT_ENVIRONMENT = "prod"
DEFAULT_UID_FILE = Path("uids_chk_tcl.txt")
DEFAULT_LOG_DIR = Path("log")
LOG_BASENAME = "get_data_tcl"
LOG_EXTENSION_TEXT = ".txt"
LOG_EXTENSION_CSV = ".csv"
DEFAULT_TIMEOUT = 30
DEFAULT_DELAY_SECONDS = 3.0
DEFAULT_LOG_FORMAT = "csv"
CSV_HEADER = [
    "timestamp",
    "environment",
    "uid",
    "status",
    "error",
    "formStatusCode",
    "DLN",
    "taxType",
    "formCode",
    "TIN",
    "NID",
    "branch",
    "ltoStatus",
    "homeOfficeCode",
    "periodForm",
    "periodTo",
    "taxAmount",
    "penaltyAmount",
    "surchargeAmount",
    "localTaxAmount",
    "totalPayAmount",
    "refundStatus",
    "effectiveDate",
    "raw_response",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch VAT POS form information for a list of UIDs and write the responses to log files.",
    )
    parser.add_argument(
        "--environment",
        choices=sorted(ENV_URLS.keys()),
        default=DEFAULT_ENVIRONMENT,
        help="Target environment base URL (default: prod).",
    )
    parser.add_argument(
        "--uids-file",
        type=Path,
        default=DEFAULT_UID_FILE,
        help="Path to the UID list file (default: uids_chk_tcl.txt).",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory where log files are written (default: log).",
    )
    parser.add_argument(
        "--log-format",
        choices=("text", "csv"),
        default=DEFAULT_LOG_FORMAT,
        help="Log output format (default: csv).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Request timeout in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help="Delay between requests in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Verify TLS certificates using the system trust store.",
    )
    return parser.parse_args()


def load_uids(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"UID file not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    uids: List[str] = []
    for raw in lines:
        uid = raw.strip()
        if not uid or uid.startswith("#"):
            continue
        uids.append(uid)
    return uids


def build_log_path(log_dir: Path, extension: str) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H.%M.%S.%f")
    filename = f"{LOG_BASENAME}_{timestamp}{extension}"
    return log_dir / filename


def build_ssl_context(verify_ssl: bool) -> ssl.SSLContext:
    if verify_ssl:
        return ssl.create_default_context()
    return ssl._create_unverified_context()


def fetch_url(url: str, timeout: float, ssl_context: ssl.SSLContext) -> Tuple[Optional[int], str, str]:
    req = request.Request(url, headers={"Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
            body_bytes = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            body_text = body_bytes.decode(charset, errors="replace")
            return resp.status, body_text, ""
    except error.HTTPError as exc:
        body_bytes = exc.read()
        charset = exc.headers.get_content_charset() or "utf-8"
        body_text = body_bytes.decode(charset, errors="replace")
        return exc.code, body_text, f"HTTPError: {exc}"
    except error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return None, "", f"URLError: {reason}"
    except Exception as exc:  # pragma: no cover - unexpected failure path
        return None, "", f"UnexpectedError: {exc}"


def pretty_body(body: str) -> str:
    if not body:
        return "<no-content>"
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body
    return json.dumps(parsed, ensure_ascii=False, indent=4)


def format_entry(uid: str, url: str, status: Optional[int], error_message: str, body: str) -> str:
    timestamp = datetime.now().isoformat(timespec="seconds")
    lines = [
        f"[{timestamp}] UID: {uid}",
        f"URL: {url}",
        f"Status: {status if status is not None else 'N/A'}",
    ]
    if error_message:
        lines.append(f"Error: {error_message}")
    lines.append("Response:")
    lines.append(pretty_body(body))
    lines.append("-" * 80)
    return "\n".join(lines) + "\n"


def extract_form_details(body_text: str) -> List[dict]:
    try:
        parsed = json.loads(body_text)
    except json.JSONDecodeError:
        return []

    response_data = parsed.get("responseData") or {}
    form_details = response_data.get("formDetails")

    if form_details is None:
        return []
    if isinstance(form_details, dict):
        form_details = [form_details]
    if not isinstance(form_details, list):
        return []

    normalized: List[dict] = []
    for detail in form_details:
        if not isinstance(detail, dict):
            continue
        normalized.append(
            {
                "formStatusCode": str(detail.get("formStatusCode", "")),
                "DLN": str(detail.get("DLN", "")),
                "taxType": str(detail.get("taxType", "")),
                "formCode": str(detail.get("formCode", "")),
                "TIN": str(detail.get("TIN", "")),
                "NID": str(detail.get("NID", "")),
                "branch": str(detail.get("branch", "")),
                "ltoStatus": str(detail.get("ltoStatus", "")),
                "homeOfficeCode": str(detail.get("homeOfficeCode", "")),
                "periodForm": str(detail.get("periodForm", "")),
                "periodTo": str(detail.get("periodTo", "")),
                "taxAmount": str(detail.get("taxAmount", "")),
                "penaltyAmount": str(detail.get("penaltyAmount", "")),
                "surchargeAmount": str(detail.get("surchargeAmount", "")),
                "localTaxAmount": str(detail.get("localTaxAmount", "")),
                "totalPayAmount": str(detail.get("totalPayAmount", "")),
                "refundStatus": str(detail.get("refundStatus", "")),
                "effectiveDate": str(detail.get("effectiveDate", "")),
            }
        )
    return normalized


def main() -> None:
    args = parse_args()

    uids = load_uids(args.uids_file)
    if not uids:
        print("No UIDs to process.")
        return

    base_url = ENV_URLS[args.environment]
    ssl_context = build_ssl_context(args.verify_ssl)
    log_dir = args.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    if args.log_format == "csv":
        log_path = build_log_path(log_dir, LOG_EXTENSION_CSV)
        with log_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(CSV_HEADER)
            for index, uid in enumerate(uids):
                url = f"{base_url}{uid}"
                status, body_text, error_message = fetch_url(url, args.timeout, ssl_context)
                timestamp = datetime.now().isoformat(timespec="seconds")
                details = extract_form_details(body_text)

                if details:
                    for detail in details:
                        writer.writerow(
                            [
                                timestamp,
                                args.environment,
                                uid,
                                status if status is not None else "",
                                error_message,
                                detail.get("formStatusCode", ""),
                                detail.get("DLN", ""),
                                detail.get("taxType", ""),
                                detail.get("formCode", ""),
                                detail.get("TIN", ""),
                                detail.get("NID", ""),
                                detail.get("branch", ""),
                                detail.get("ltoStatus", ""),
                                detail.get("homeOfficeCode", ""),
                                detail.get("periodForm", ""),
                                detail.get("periodTo", ""),
                                detail.get("taxAmount", ""),
                                detail.get("penaltyAmount", ""),
                                detail.get("surchargeAmount", ""),
                                detail.get("localTaxAmount", ""),
                                detail.get("totalPayAmount", ""),
                                detail.get("refundStatus", ""),
                                detail.get("effectiveDate", ""),
                                body_text,
                            ]
                        )
                else:
                    writer.writerow(
                        [
                            timestamp,
                            args.environment,
                            uid,
                            status if status is not None else "",
                            error_message,
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            body_text,
                        ]
                    )
                csv_file.flush()

                if error_message:
                    print(f"{uid}: {error_message}")
                elif status is not None:
                    print(f"{uid}: status {status}")
                else:
                    print(f"{uid}: request completed")

                if index < len(uids) - 1 and args.delay > 0:
                    sleep(args.delay)
        print(f"Log written to {log_path}")
        return

    log_path = build_log_path(log_dir, LOG_EXTENSION_TEXT)
    with log_path.open("w", encoding="utf-8") as log_handle:
        for index, uid in enumerate(uids):
            url = f"{base_url}{uid}"
            status, body_text, error_message = fetch_url(url, args.timeout, ssl_context)
            log_handle.write(format_entry(uid, url, status, error_message, body_text))
            log_handle.flush()

            if error_message:
                print(f"{uid}: {error_message}")
            elif status is not None:
                print(f"{uid}: status {status}")
            else:
                print(f"{uid}: request completed")

            if index < len(uids) - 1 and args.delay > 0:
                sleep(args.delay)

    print(f"Log written to {log_path}")


if __name__ == "__main__":
    main()
