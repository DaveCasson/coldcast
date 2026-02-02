from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


logger = logging.getLogger("coldcast.download")


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    filename: str
    headers: Optional[dict] = None
    auth: Optional[Tuple[str, str]] = None


def _download_one(request: DownloadRequest, output_dir: Path, timeout: int = 60) -> bool:
    output_path = output_dir / request.filename
    if output_path.exists():
        logger.info("File %s already exists. Skipping.", output_path)
        return False

    try:
        with requests.get(
            request.url,
            headers=request.headers,
            auth=request.auth,
            stream=True,
            timeout=timeout,
        ) as response:
            if response.status_code < 200 or response.status_code >= 300:
                logger.warning("Failed to download %s (status %s)", request.url, response.status_code)
                return False
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 512):
                    if chunk:
                        handle.write(chunk)
        logger.info("Downloaded %s", request.url)
        return True
    except requests.RequestException as exc:
        logger.warning("Download failed for %s: %s", request.url, exc)
        return False


def download_requests(
    requests_list: Iterable[DownloadRequest],
    output_dir: str,
    max_num_threads: int,
) -> int:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    request_list = list(requests_list)
    if not request_list:
        logger.info("No download requests to process.")
        return 0

    successes = 0
    semaphore = threading.BoundedSemaphore(max_num_threads)

    def wrapped_download(req: DownloadRequest) -> bool:
        with semaphore:
            return _download_one(req, output_path)

    with ThreadPoolExecutor(max_workers=max_num_threads) as executor:
        future_map = {executor.submit(wrapped_download, req): req for req in request_list}
        for future in as_completed(future_map):
            if future.result():
                successes += 1

    return successes
