"""Fetches taxpayer information for NIDs and logs the responses."""

import argparse
import csv
import json
import ssl
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Dict, List, Optional, Tuple
from urllib import error, request

ENV_URLS: Dict[str, str] = {
    "prod": "https://vsintra.rd.go.th/rd-common-nid-service/nid/getTaxpayerInfoList",
    "uat": "https://vsintra-uat.rd.go.th/rd-common-nid-service/nid/getTaxpayerInfoList",
}
DEFAULT_ENVIRONMENT = "prod"
DEFAULT_NID_FILE = Path("nid.txt")
DEFAULT_LOG_DIR = Path("log")
LOG_BASENAME = "get_nid_data"
LOG_EXTENSION_TEXT = ".txt"
LOG_EXTENSION_CSV = ".csv"
DEFAULT_TIMEOUT = 30
DEFAULT_DELAY_SECONDS = 0.1
DEFAULT_LOG_FORMAT = "csv"
CSV_HEADER = [
    "timestamp",
    "environment",
    "nid",
    "status",
    "error",
    "entryIdentifier",
    "entryStatusCode",
    "taxpayerIdentifier",
    "personIdentifier",
    "taxpayerStatusCode",
    "vatStatus",
    "sbtStatus",
    "titleCode",
    "titleName",
    "firstName",
    "middleName",
    "lastName",
    "buildingName",
    "roomIdentifier",
    "floorIdentifier",
    "villageName",
    "entranceIdentifier",
    "mooIdentifier",
    "soiName",
    "yaek",
    "streetName",
    "subdistrictCode",
    "districtCode",
    "provinceCode",
    "postalCode",
    "telephoneIdentifier",
    "unitIdentifier",
    "issueCountryCode",
    "issueDate",
    "issueOrganizationName",
    "nationalityCode",
    "typeCode",
    "identifier",
    "raw_response",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch taxpayer info for each NID and write the responses to log files.",
    )
    parser.add_argument(
        "--environment",
        choices=sorted(ENV_URLS.keys()),
        default=DEFAULT_ENVIRONMENT,
        help="Target environment base URL (default: prod).",
    )
    parser.add_argument(
        "--nids-file",
        type=Path,
        default=DEFAULT_NID_FILE,
        help="Path to the NID list file (default: nid.txt).",
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


def load_nids(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"NID file not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    nids: List[str] = []
    for raw in lines:
        nid = raw.strip()
        if not nid or nid.startswith("#"):
            continue
        nids.append(nid)
    return nids


def build_payload(nid: str) -> Dict[str, object]:
    return {
        "taxpayerList": [
            {
                "refId": "",
                "tin": nid,
                "vatsbtId": "",
                "branchId": "",
            }
        ]
    }


def build_ssl_context(verify_ssl: bool) -> ssl.SSLContext:
    if verify_ssl:
        return ssl.create_default_context()
    return ssl._create_unverified_context()


def fetch_url(
    url: str,
    payload: Dict[str, object],
    timeout: float,
    ssl_context: ssl.SSLContext,
) -> Tuple[Optional[int], str, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
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


def format_entry(nid: str, url: str, status: Optional[int], error_message: str, response_body: str) -> str:
    timestamp = datetime.now().isoformat(timespec="seconds")
    lines = [
        f"[{timestamp}] NID: {nid}",
        f"URL: {url}",
        f"Status: {status if status is not None else 'N/A'}",
    ]
    if error_message:
        lines.append(f"Error: {error_message}")
    lines.append("Response:")
    lines.append(pretty_body(response_body))
    lines.append("-" * 80)
    return "\n".join(lines) + "\n"


def build_log_path(log_dir: Path, extension: str) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H.%M.%S.%f")
    filename = f"{LOG_BASENAME}_{timestamp}{extension}"
    return log_dir / filename


def extract_entries(body_text: str) -> List[Dict[str, str]]:
    try:
        parsed = json.loads(body_text)
    except json.JSONDecodeError:
        return []

    response_data = parsed.get("responseData") or {}
    taxpayer_list = response_data.get("TaxpayerList") or {}
    entries = taxpayer_list.get("Entry")

    if entries is None:
        return []
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        return []

    flattened: List[Dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name_info = entry.get("taxpayerNameInformation") or {}
        address_info = entry.get("currentAddressInformation") or {}
        doc_info = entry.get("importantDocumentInformation") or {}
        flattened.append(
            {
                "entryIdentifier": str(entry.get("entryIdentifier", "")),
                "entryStatusCode": str(entry.get("entryStatusCode", "")),
                "taxpayerIdentifier": str(entry.get("taxpayerIdentifier", "")),
                "personIdentifier": str(entry.get("personIdentifier", "")),
                "taxpayerStatusCode": str(entry.get("taxpayerStatusCode", "")),
                "vatStatus": str(entry.get("vatStatus", "")),
                "sbtStatus": str(entry.get("sbtStatus", "")),
                "titleCode": str(name_info.get("titleCode", "")),
                "titleName": str(name_info.get("titleName", "")),
                "firstName": str(name_info.get("firstName", "")),
                "middleName": str(name_info.get("middleName", "")),
                "lastName": str(name_info.get("lastName", "")),
                "buildingName": str(address_info.get("buildingName", "")),
                "roomIdentifier": str(address_info.get("roomIdentifier", "")),
                "floorIdentifier": str(address_info.get("floorIdentifier", "")),
                "villageName": str(address_info.get("villageName", "")),
                "entranceIdentifier": str(address_info.get("entranceIdentifier", "")),
                "mooIdentifier": str(address_info.get("mooIdentifier", "")),
                "soiName": str(address_info.get("soiName", "")),
                "yaek": str(address_info.get("yaek", "")),
                "streetName": str(address_info.get("streetName", "")),
                "subdistrictCode": str(address_info.get("subdistrictCode", "")),
                "districtCode": str(address_info.get("districtCode", "")),
                "provinceCode": str(address_info.get("provinceCode", "")),
                "postalCode": str(address_info.get("postalCode", "")),
                "telephoneIdentifier": str(address_info.get("telephoneIdentifier", "")),
                "unitIdentifier": str(address_info.get("unitIdentifier", "")),
                "issueCountryCode": str(doc_info.get("issueCountryCode", "")),
                "issueDate": str(doc_info.get("issueDate", "")),
                "issueOrganizationName": str(doc_info.get("issueOrganizationName", "")),
                "nationalityCode": str(doc_info.get("nationalityCode", "")),
                "typeCode": str(doc_info.get("typeCode", "")),
                "identifier": str(doc_info.get("identifier", "")),
            }
        )
    return flattened


def main() -> None:
    args = parse_args()

    nids = load_nids(args.nids_file)
    if not nids:
        print("No NIDs to process.")
        return

    url = ENV_URLS[args.environment]
    ssl_context = build_ssl_context(args.verify_ssl)

    log_dir = args.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    if args.log_format == "csv":
        log_path = build_log_path(log_dir, LOG_EXTENSION_CSV)
        with log_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(CSV_HEADER)
            for index, nid in enumerate(nids):
                payload = build_payload(nid)
                status, body_text, error_message = fetch_url(url, payload, args.timeout, ssl_context)
                timestamp = datetime.now().isoformat(timespec="seconds")
                entries = extract_entries(body_text)

                if entries:
                    for entry in entries:
                        writer.writerow(
                            [
                                timestamp,
                                args.environment,
                                nid,
                                status if status is not None else "",
                                error_message,
                                entry.get("entryIdentifier", ""),
                                entry.get("entryStatusCode", ""),
                                entry.get("taxpayerIdentifier", ""),
                                entry.get("personIdentifier", ""),
                                entry.get("taxpayerStatusCode", ""),
                                entry.get("vatStatus", ""),
                                entry.get("sbtStatus", ""),
                                entry.get("titleCode", ""),
                                entry.get("titleName", ""),
                                entry.get("firstName", ""),
                                entry.get("middleName", ""),
                                entry.get("lastName", ""),
                                entry.get("buildingName", ""),
                                entry.get("roomIdentifier", ""),
                                entry.get("floorIdentifier", ""),
                                entry.get("villageName", ""),
                                entry.get("entranceIdentifier", ""),
                                entry.get("mooIdentifier", ""),
                                entry.get("soiName", ""),
                                entry.get("yaek", ""),
                                entry.get("streetName", ""),
                                entry.get("subdistrictCode", ""),
                                entry.get("districtCode", ""),
                                entry.get("provinceCode", ""),
                                entry.get("postalCode", ""),
                                entry.get("telephoneIdentifier", ""),
                                entry.get("unitIdentifier", ""),
                                entry.get("issueCountryCode", ""),
                                entry.get("issueDate", ""),
                                entry.get("issueOrganizationName", ""),
                                entry.get("nationalityCode", ""),
                                entry.get("typeCode", ""),
                                entry.get("identifier", ""),
                                body_text,
                            ]
                        )
                else:
                    writer.writerow(
                        [
                            timestamp,
                            args.environment,
                            nid,
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
                    print(f"{nid}: {error_message}")
                elif status is not None:
                    print(f"{nid}: status {status}")
                else:
                    print(f"{nid}: request completed")

                if index < len(nids) - 1 and args.delay > 0:
                    sleep(args.delay)
        print(f"Log written to {log_path}")
        return

    log_path = build_log_path(log_dir, LOG_EXTENSION_TEXT)
    with log_path.open("w", encoding="utf-8") as log_handle:
        for index, nid in enumerate(nids):
            payload = build_payload(nid)
            status, body_text, error_message = fetch_url(url, payload, args.timeout, ssl_context)
            log_handle.write(format_entry(nid, url, status, error_message, body_text))
            log_handle.flush()

            if error_message:
                print(f"{nid}: {error_message}")
            elif status is not None:
                print(f"{nid}: status {status}")
            else:
                print(f"{nid}: request completed")

            if index < len(nids) - 1 and args.delay > 0:
                sleep(args.delay)

    print(f"Log written to {log_path}")


if __name__ == "__main__":
    main()
