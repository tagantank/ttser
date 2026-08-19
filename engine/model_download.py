from __future__ import annotations

import re
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from engine.errors import DownloadCancelled

ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]

USER_AGENT = "ttser/0.1"
_CONTENT_RANGE_TOTAL = re.compile(r"/(\d+)\s*$")


def format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KiB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MiB"
    return f"{num_bytes / (1024 * 1024 * 1024):.2f} GiB"


def _parse_content_range_total(value: str) -> int:
    match = _CONTENT_RANGE_TOTAL.search(value.strip())
    if not match:
        return 0
    return int(match.group(1))


def _request_content_length(url: str, method: str, extra_headers: dict[str, str] | None = None) -> int:
    headers = {"User-Agent": USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    req = Request(url, method=method, headers=headers)
    with urlopen(req, timeout=60) as response:
        content_range = response.headers.get("Content-Range", "")
        total = _parse_content_range_total(content_range)
        if total > 0:
            return total
        return int(response.headers.get("Content-Length") or 0)


def resolve_content_length(url: str, expected_size: int = 0) -> int:
    for method, extra_headers in (
        ("GET", {"Range": "bytes=0-0"}),
        ("HEAD", None),
    ):
        try:
            total = _request_content_length(
                url,
                method,
                extra_headers=extra_headers,
            )
        except (HTTPError, URLError):
            continue
        if total > 0:
            return total
    return expected_size


def probe_content_length(url: str) -> int:
    return resolve_content_length(url)


def download_file(
    url: str,
    destination: Path,
    progress: ProgressCallback | None = None,
    expected_size: int = 0,
    chunk_size: int = 1024 * 1024,
    should_cancel: CancelCallback | None = None,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".part")
    total = resolve_content_length(url, expected_size=expected_size)
    if should_cancel and should_cancel():
        raise DownloadCancelled()
    req = Request(url, headers={"User-Agent": USER_AGENT})
    received = 0
    try:
        with urlopen(req, timeout=60) as response:
            response_total = int(response.headers.get("Content-Length") or 0)
            if response_total > 0:
                total = response_total
            with temp_path.open("wb") as handle:
                while True:
                    if should_cancel and should_cancel():
                        raise DownloadCancelled()
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    handle.write(chunk)
                    received += len(chunk)
                    if total > 0 and received > total:
                        total = received
                    if progress:
                        progress(received, total)
    except DownloadCancelled:
        temp_path.unlink(missing_ok=True)
        raise
    except HTTPError as exc:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"HTTP {exc.code} while downloading {url}") from exc
    except URLError as exc:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Network error while downloading {url}: {exc.reason}") from exc

    if progress:
        progress(received, max(received, total))
    temp_path.replace(destination)
    return destination
