from __future__ import annotations

import time
from io import BytesIO
from threading import Event
from typing import Callable

import pycurl

from app.network.models import RequestConfig, RequestResult
from app.network.timing import collect_network_timings

class RequestCancelled(Exception):
    """Raised when the user cancels an active request."""


ProgressCallback = Callable[
    [int, int, int, int],
    None,
]


class HttpClient:
    """Low-level HTTP client powered by libcurl."""

    def execute(
        self,
        config: RequestConfig,
        cancel_event: Event,
        progress_callback: ProgressCallback | None = None,
    ) -> RequestResult:
        response_body = BytesIO()
        response_headers = BytesIO()

        curl = pycurl.Curl()

        last_progress_emit = 0.0

        def on_progress(
            download_total: int,
            download_now: int,
            upload_total: int,
            upload_now: int,
        ) -> int:
            nonlocal last_progress_emit

            if cancel_event.is_set():
                # Returning non-zero tells libcurl to abort.
                return 1

            now = time.monotonic()

            if (
                progress_callback
                and now - last_progress_emit >= 0.1
            ):
                progress_callback(
                    download_total,
                    download_now,
                    upload_total,
                    upload_now,
                )

                last_progress_emit = now

            return 0

        try:
            self._configure_common(
                curl=curl,
                config=config,
                response_body=response_body,
                response_headers=response_headers,
                progress_callback=on_progress,
            )

            self._configure_method(
                curl,
                config,
            )

            curl.perform()

            if cancel_event.is_set():
                raise RequestCancelled()
            status_code = int(
                curl.getinfo(
                    pycurl.RESPONSE_CODE
                )
            )

            timings = collect_network_timings(
                curl
            )
            
            effective_url = str(
                curl.getinfo(
                    pycurl.EFFECTIVE_URL
                )
                or config.url
            )

            content_type = str(
                curl.getinfo(
                    pycurl.CONTENT_TYPE
                )
                or ""
            )

            total_time_ms = timings.total_ms

            size_info = getattr(
                pycurl,
                "SIZE_DOWNLOAD_T",
                pycurl.SIZE_DOWNLOAD,
            )

            response_size = int(
                float(
                    curl.getinfo(
                        size_info
                    )
                )
            )

            http_version = self._http_version(
                curl
            )

            header_text = (
                response_headers
                .getvalue()
                .decode(
                    "iso-8859-1",
                    errors="replace",
                )
            )

            status_text = self._status_text(
                header_text,
                status_code,
            )

            return RequestResult(
                status_code=status_code,
                status_text=status_text,
                effective_url=effective_url,
                content_type=content_type,
                http_version=http_version,
                total_time_ms=total_time_ms,
                response_size=response_size,
                response_headers=header_text,
                body=response_body.getvalue(),
                timings=timings,
            )

        except pycurl.error as exc:
            if cancel_event.is_set():
                raise RequestCancelled() from exc

            error_code, error_message = exc.args

            raise RuntimeError(
                f"libcurl error "
                f"{error_code}: "
                f"{error_message}"
            ) from exc

        finally:
            curl.close()

    @staticmethod
    def _configure_common(
        curl: pycurl.Curl,
        config: RequestConfig,
        response_body: BytesIO,
        response_headers: BytesIO,
        progress_callback: Callable[
            [int, int, int, int],
            int,
        ],
    ) -> None:

        curl.setopt(
            pycurl.URL,
            config.url,
        )

        curl.setopt(
            pycurl.WRITEFUNCTION,
            response_body.write,
        )

        curl.setopt(
            pycurl.HEADERFUNCTION,
            response_headers.write,
        )

        curl.setopt(
            pycurl.CONNECTTIMEOUT_MS,
            10_000,
        )

        curl.setopt(
            pycurl.TIMEOUT_MS,
            config.timeout_seconds * 1000,
        )

        curl.setopt(
            pycurl.NOSIGNAL,
            1,
        )

        # Redirect visualization comes later.
        curl.setopt(
            pycurl.FOLLOWLOCATION,
            False,
        )

        # Accept gzip/br/zstd when supported.
        curl.setopt(
            pycurl.ACCEPT_ENCODING,
            "",
        )

        curl.setopt(
            pycurl.USERAGENT,
            "RequestFlow/0.1",
        )

        # Required for XFERINFOFUNCTION.
        curl.setopt(
            pycurl.NOPROGRESS,
            False,
        )

        curl.setopt(
            pycurl.XFERINFOFUNCTION,
            progress_callback,
        )

        if config.headers:
            headers = [
                f"{name}: {value}"
                for name, value
                in config.headers.items()
            ]

            curl.setopt(
                pycurl.HTTPHEADER,
                headers,
            )

    @staticmethod
    def _configure_method(
        curl: pycurl.Curl,
        config: RequestConfig,
    ) -> None:

        method = (
            config.method
            .upper()
            .strip()
        )

        body = config.body.encode(
            "utf-8"
        )

        if method == "GET":
            curl.setopt(
                pycurl.HTTPGET,
                True,
            )
            return

        if method == "HEAD":
            curl.setopt(
                pycurl.NOBODY,
                True,
            )

            curl.setopt(
                pycurl.CUSTOMREQUEST,
                "HEAD",
            )
            return

        if method == "POST":
            curl.setopt(
                pycurl.POST,
                True,
            )

            curl.setopt(
                pycurl.POSTFIELDS,
                body,
            )
            return

        # PUT / PATCH / DELETE
        curl.setopt(
            pycurl.CUSTOMREQUEST,
            method,
        )

        if body:
            curl.setopt(
                pycurl.POSTFIELDS,
                body,
            )

    @staticmethod
    def _status_text(
        raw_headers: str,
        status_code: int,
    ) -> str:

        status_line = ""

        for line in raw_headers.splitlines():
            if line.startswith("HTTP/"):
                status_line = line.strip()

        if not status_line:
            return str(status_code)

        parts = status_line.split(
            " ",
            2,
        )

        if len(parts) == 3:
            return parts[2]

        return str(status_code)

    @staticmethod
    def _http_version(
        curl: pycurl.Curl,
    ) -> str:

        info_constant = getattr(
            pycurl,
            "INFO_HTTP_VERSION",
            None,
        )

        if info_constant is None:
            return "Unknown"

        value = curl.getinfo(
            info_constant
        )

        versions = {
            getattr(
                pycurl,
                "CURL_HTTP_VERSION_1_0",
                -100,
            ): "HTTP/1.0",

            getattr(
                pycurl,
                "CURL_HTTP_VERSION_1_1",
                -101,
            ): "HTTP/1.1",

            getattr(
                pycurl,
                "CURL_HTTP_VERSION_2_0",
                -102,
            ): "HTTP/2",

            getattr(
                pycurl,
                "CURL_HTTP_VERSION_2",
                -103,
            ): "HTTP/2",

            getattr(
                pycurl,
                "CURL_HTTP_VERSION_3",
                -104,
            ): "HTTP/3",
        }

        return versions.get(
            value,
            f"HTTP version {value}",
        )