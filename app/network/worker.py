from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from app.network.client import (
    HttpClient,
    RequestCancelled,
)
from app.network.models import (
    RequestConfig,
    RequestResult,
)


class RequestWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    progress = Signal(
        int,
        int,
        int,
        int,
    )

    done = Signal()

    def __init__(
        self,
        config: RequestConfig,
    ) -> None:
        super().__init__()

        self._config = config
        self._cancel_event = Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    @Slot()
    def run(self) -> None:

        try:
            client = HttpClient()

            result: RequestResult = (
                client.execute(
                    self._config,
                    self._cancel_event,
                    self._emit_progress,
                )
            )

            self.completed.emit(
                result
            )

        except RequestCancelled:
            self.cancelled.emit()

        except Exception as exc:
            self.failed.emit(
                str(exc)
            )

        finally:
            self.done.emit()

    def _emit_progress(
        self,
        download_total: int,
        download_now: int,
        upload_total: int,
        upload_now: int,
    ) -> None:

        self.progress.emit(
            download_total,
            download_now,
            upload_total,
            upload_now,
        )