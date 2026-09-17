from __future__ import annotations

import json
from typing import Any
from unittest import result

from PySide6.QtCore import (
    QThread,
    QTimer,
    Qt,
)
from PySide6.QtGui import (
    QCloseEvent,
    QFont,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.network.models import (
    RequestConfig,
    RequestResult,
)
from app.network.worker import RequestWorker
from app.ui.flow_view import FlowPanel



DARK_STYLE = """
QWidget {
    background: #111317;
    color: #e8eaed;
    font-size: 14px;
}

QFrame#panel {
    background: #191c22;
    border: 1px solid #2a2f38;
    border-radius: 12px;
}

QLineEdit,
QComboBox,
QPlainTextEdit {
    background: #181b20;
    color: #eef1f5;
    border: 1px solid #303641;
    border-radius: 8px;
    padding: 8px;
    selection-background-color: #5865f2;
}

QLineEdit:focus,
QComboBox:focus,
QPlainTextEdit:focus {
    border: 1px solid #6574ff;
}

QPushButton {
    background: #262b33;
    border: 1px solid #343a45;
    border-radius: 8px;
    padding: 8px 14px;
}

QPushButton:hover {
    background: #303640;
}

QPushButton#sendButton {
    background: #5865f2;
    border: none;
    color: white;
    font-weight: 700;
}

QPushButton#sendButton:hover {
    background: #6875ff;
}

QPushButton#cancelButton {
    background: #3a2328;
    border: 1px solid #6d333d;
    color: #ffb4bd;
}

QTabWidget::pane {
    border: 1px solid #2a2f38;
    background: #15181d;
}

QTabBar::tab {
    background: #191c22;
    padding: 9px 16px;
    border: 1px solid #2a2f38;
}

QTabBar::tab:selected {
    background: #252a32;
    color: white;
}

QLabel#muted {
    color: #929aa5;
}

QLabel#statusGood {
    color: #63d392;
    font-weight: 700;
}

QLabel#statusBad {
    color: #ff7a89;
    font-weight: 700;
}
"""


class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(
            "RequestFlow — Phase 1"
        )

        self.resize(
            1180,
            760,
        )

        self.setMinimumSize(
            850,
            600,
        )

        self.setStyleSheet(
            DARK_STYLE
        )

        self._thread: QThread | None = None
        self._worker: RequestWorker | None = None

        self._close_after_request = False

        self._build_ui()

    def _build_ui(self) -> None:

        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)

        layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        layout.setSpacing(12)

        title = QLabel(
            "RequestFlow"
        )

        title.setFont(
            QFont(
                "Sans Serif",
                22,
                QFont.Weight.Bold,
            )
        )

        subtitle = QLabel(
            "Phase 1 • non-blocking libcurl request engine"
        )

        subtitle.setObjectName(
            "muted"
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # --------------------------------------------------
        # Request bar
        # --------------------------------------------------

        request_bar = QHBoxLayout()

        self.method_combo = QComboBox()

        self.method_combo.addItems(
            [
                "GET",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
                "HEAD",
            ]
        )

        self.method_combo.setFixedWidth(
            105
        )

        self.url_edit = QLineEdit(
            "https://httpbin.org/get"
        )

        self.url_edit.setPlaceholderText(
            "https://api.example.com/users"
        )

        self.url_edit.returnPressed.connect(
            self.send_request
        )

        self.send_button = QPushButton(
            "Send"
        )

        self.send_button.setObjectName(
            "sendButton"
        )

        self.send_button.clicked.connect(
            self.send_request
        )

        self.cancel_button = QPushButton(
            "Cancel"
        )

        self.cancel_button.setObjectName(
            "cancelButton"
        )

        self.cancel_button.setEnabled(
            False
        )

        self.cancel_button.clicked.connect(
            self.cancel_request
        )

        request_bar.addWidget(
            self.method_combo
        )

        request_bar.addWidget(
            self.url_edit,
            1,
        )

        request_bar.addWidget(
            self.send_button
        )

        request_bar.addWidget(
            self.cancel_button
        )

        layout.addLayout(
            request_bar
        )

        # --------------------------------------------------
        # Main area
        # --------------------------------------------------

        splitter = QSplitter(
            Qt.Orientation.Vertical
        )

        splitter.setChildrenCollapsible(
            False
        )

        layout.addWidget(
            splitter,
            1,
        )

        # --------------------------------------------------
        # Request tabs
        # --------------------------------------------------

        request_panel = QTabWidget()

        self.headers_edit = QPlainTextEdit()

        self.headers_edit.setPlainText(
            '{\n'
            '  "Accept": "application/json"\n'
            '}'
        )

        self.body_edit = QPlainTextEdit()

        self.body_edit.setPlaceholderText(
            '{\n'
            '  "name": "Alice"\n'
            '}'
        )

        request_panel.addTab(
            self.headers_edit,
            "Request Headers (JSON)",
        )

        request_panel.addTab(
            self.body_edit,
            "Request Body",
        )

        splitter.addWidget(
            request_panel
        )

        # --------------------------------------------------
        # Response
        # --------------------------------------------------

        response_frame = QFrame()
        response_frame.setObjectName(
            "panel"
        )

        response_layout = QVBoxLayout(
            response_frame
        )

        summary = QHBoxLayout()

        self.status_label = QLabel(
            "Ready"
        )

        self.status_label.setObjectName(
            "muted"
        )

        self.time_label = QLabel(
            "— ms"
        )

        self.size_label = QLabel(
            "— B"
        )

        self.version_label = QLabel(
            "—"
        )

        self.type_label = QLabel(
            "—"
        )

        for widget in (
            self.time_label,
            self.size_label,
            self.version_label,
            self.type_label,
        ):
            widget.setObjectName(
                "muted"
            )

        summary.addWidget(
            self.status_label
        )

        summary.addSpacing(12)

        summary.addWidget(
            self.time_label
        )

        summary.addSpacing(12)

        summary.addWidget(
            self.size_label
        )

        summary.addSpacing(12)

        summary.addWidget(
            self.version_label
        )

        summary.addSpacing(12)

        summary.addWidget(
            self.type_label
        )

        summary.addStretch(1)

        response_layout.addLayout(
            summary
        )

        self.response_tabs = QTabWidget()

        self.response_body = (
            QPlainTextEdit()
        )

        self.response_body.setReadOnly(
            True
        )

        self.response_headers = (
            QPlainTextEdit()
        )

        self.response_headers.setReadOnly(
            True
        )
        self.timing_view = QPlainTextEdit()

        self.timing_view.setReadOnly(
            True
        )

        self.timing_view.setPlaceholderText(
            "Network timing information "
            "will appear after a request."
        )

        self.flow_view = FlowPanel()

        self.response_tabs.addTab(
            self.response_body,
            "Response Body",
        )

        self.response_tabs.addTab(
            self.response_headers,
            "Response Headers",
        )

        self.response_tabs.addTab(
            self.timing_view,
            "Timing",
        )

        response_layout.addWidget(
            self.response_tabs,
            1,
        )

        splitter.addWidget(
            response_frame
        )

        splitter.setSizes(
            [
                270,
                430,
            ]
        )

        self.statusBar().showMessage(
            "Ready"
        )

    # ------------------------------------------------------
    # Request
    # ------------------------------------------------------

    def send_request(self) -> None:

        if (
            self._thread is not None
            and self._thread.isRunning()
        ):
            return

        try:
            config = (
                self._build_request_config()
            )

        except ValueError as exc:
            QMessageBox.warning(
                self,
                "Invalid request",
                str(exc),
            )
            return

        self.response_body.clear()
        self.response_headers.clear()
        self.timing_view.clear()
        self.flow_view.clear()





        self._set_running(
            True
        )

        self.statusBar().showMessage(
            "Sending request…"
        )

        thread = QThread(
            self
        )

        worker = RequestWorker(
            config
        )

        worker.moveToThread(
            thread
        )

        thread.started.connect(
            worker.run
        )

        worker.completed.connect(
            self._request_completed
        )

        worker.failed.connect(
            self._request_failed
        )

        worker.cancelled.connect(
            self._request_cancelled
        )

        worker.progress.connect(
            self._request_progress
        )

        worker.done.connect(
            thread.quit
        )

        worker.done.connect(
            worker.deleteLater
        )

        thread.finished.connect(
            thread.deleteLater
        )

        thread.finished.connect(
            self._thread_finished
        )

        self._thread = thread
        self._worker = worker

        thread.start()

    def cancel_request(self) -> None:

        if self._worker is None:
            return

        self._worker.cancel()

        self.cancel_button.setEnabled(
            False
        )

        self.statusBar().showMessage(
            "Cancelling request…"
        )

    # ------------------------------------------------------
    # Build request
    # ------------------------------------------------------

    def _build_request_config(
        self,
    ) -> RequestConfig:

        url = (
            self.url_edit
            .text()
            .strip()
        )

        if not url:
            raise ValueError(
                "Enter a URL first."
            )

        if not url.startswith(
            (
                "http://",
                "https://",
            )
        ):
            raise ValueError(
                "Phase 1 supports "
                "http:// and https:// URLs."
            )

        headers_text = (
            self.headers_edit
            .toPlainText()
            .strip()
        )

        headers: dict[str, str] = {}

        if headers_text:
            try:
                parsed: Any = json.loads(
                    headers_text
                )

            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Headers must be valid JSON: "
                    f"{exc.msg} "
                    f"(line {exc.lineno}, "
                    f"column {exc.colno})."
                ) from exc

            if not isinstance(
                parsed,
                dict,
            ):
                raise ValueError(
                    "Headers JSON must "
                    "be an object."
                )

            headers = {
                str(key): str(value)
                for key, value
                in parsed.items()
            }

        return RequestConfig(
            method=(
                self.method_combo
                .currentText()
            ),
            url=url,
            headers=headers,
            body=(
                self.body_edit
                .toPlainText()
            ),
            timeout_seconds=30,
        )

    # ------------------------------------------------------
    # Result
    # ------------------------------------------------------

    def _request_completed(
        self,
        result: RequestResult,
    ) -> None:

        self.status_label.setText(
            f"{result.status_code} "
            f"{result.status_text}"
        )

        if (
            200
            <= result.status_code
            < 400
        ):
            name = "statusGood"
        else:
            name = "statusBad"

        self.status_label.setObjectName(
            name
        )

        self.status_label.style().unpolish(
            self.status_label
        )

        self.status_label.style().polish(
            self.status_label
        )

        self.time_label.setText(
            f"{result.total_time_ms:.1f} ms"
        )

        self.size_label.setText(
            self._human_bytes(
                result.response_size
            )
        )

        self.version_label.setText(
            result.http_version
        )

        self.type_label.setText(
            result.content_type
            or "Unknown content type"
        )

        self.response_headers.setPlainText(
            result.response_headers
        )

        self.response_body.setPlainText(
            self._display_body(
                result
            )
        )

        self.timing_view.setPlainText(
            self._format_timings(
                result
            )
        )

        self.flow_view.set_timings(
            result.timings
        )


        self.statusBar().showMessage(
            "Finished: "
            f"{result.effective_url}"
        )

    def _request_failed(
        self,
        message: str,
    ) -> None:

        self.flow_view.clear()
        self.status_label.setText(
            "Request failed"
        )

        self.status_label.setObjectName(
            "statusBad"
        )

        self.status_label.style().unpolish(
            self.status_label
        )

        self.status_label.style().polish(
            self.status_label
        )

        self.response_body.setPlainText(
            message
        )

        self.statusBar().showMessage(
            "Request failed"
        )

    def _request_cancelled(
        self,
    ) -> None:
        self.flow_view.clear()
        self.status_label.setText(
            "Cancelled"
        )

        self.status_label.setObjectName(
            "muted"
        )

        self.status_label.style().unpolish(
            self.status_label
        )

        self.status_label.style().polish(
            self.status_label
        )

        self.statusBar().showMessage(
            "Request cancelled"
        )

    # ------------------------------------------------------
    # Progress
    # ------------------------------------------------------

    def _request_progress(
        self,
        download_total: int,
        download_now: int,
        upload_total: int,
        upload_now: int,
    ) -> None:

        if download_total > 0:

            self.statusBar().showMessage(
                "Downloading "
                f"{self._human_bytes(download_now)}"
                " / "
                f"{self._human_bytes(download_total)}"
            )

        elif upload_total > 0:

            self.statusBar().showMessage(
                "Uploading "
                f"{self._human_bytes(upload_now)}"
                " / "
                f"{self._human_bytes(upload_total)}"
            )

        else:
            self.statusBar().showMessage(
                "Waiting for response…"
            )

    # ------------------------------------------------------
    # Thread cleanup
    # ------------------------------------------------------

    def _thread_finished(
        self,
    ) -> None:

        self._thread = None
        self._worker = None

        self._set_running(
            False
        )

        if self._close_after_request:
            self._close_after_request = False

            QTimer.singleShot(
                0,
                self.close,
            )

    def _set_running(
        self,
        running: bool,
    ) -> None:

        self.send_button.setEnabled(
            not running
        )

        self.cancel_button.setEnabled(
            running
        )

        self.method_combo.setEnabled(
            not running
        )

        self.url_edit.setEnabled(
            not running
        )

    # ------------------------------------------------------
    # Helpers
    # ------------------------------------------------------

    @staticmethod
    def _format_timings(
        result: RequestResult,
    ) -> str:
        timings = result.timings

        lines = [
            "NETWORK TIMING",
            "",
        ]

        for stage in timings.stages:
            if stage.skipped:
                value = "Not used"
            else:
                value = (
                    f"{stage.duration_ms:.2f} ms"
                )

            lines.append(
                f"{stage.label:<26} {value}"
            )

        lines.extend(
            [
                "",
                "----------------------------------------",
                f"{'Total':<26} "
                f"{timings.total_ms:.2f} ms",
            ]
        )

        if timings.primary_ip:
            endpoint = timings.primary_ip

            if timings.primary_port:
                endpoint += (
                    f":{timings.primary_port}"
                )

            lines.extend(
                [
                    "",
                    f"Remote endpoint: {endpoint}",
                ]
            )

        lines.extend(
            [
                "",
                "CUMULATIVE LIBCURL TIMESTAMPS",
                "",
                (
                    f"{'DNS complete':<26} "
                    f"{timings.name_lookup_at_ms:.2f} ms"
                ),
                (
                    f"{'TCP connected':<26} "
                    f"{timings.connect_at_ms:.2f} ms"
                ),
            ]
        )

        if timings.app_connect_at_ms > 0:
            lines.append(
                f"{'TLS complete':<26} "
                f"{timings.app_connect_at_ms:.2f} ms"
            )

        lines.extend(
            [
                (
                    f"{'Pre-transfer':<26} "
                    f"{timings.pre_transfer_at_ms:.2f} ms"
                ),
                (
                    f"{'First byte':<26} "
                    f"{timings.start_transfer_at_ms:.2f} ms"
                ),
                (
                    f"{'Transfer complete':<26} "
                    f"{timings.total_ms:.2f} ms"
                ),
            ]
        )

        return "\n".join(
            lines
        )





    @staticmethod
    def _display_body(
        result: RequestResult,
    ) -> str:

        text = result.body.decode(
            "utf-8",
            errors="replace",
        )

        if (
            "json"
            in result.content_type.lower()
        ):
            try:
                return json.dumps(
                    json.loads(text),
                    indent=2,
                    ensure_ascii=False,
                )

            except json.JSONDecodeError:
                pass

        return text

    @staticmethod
    def _human_bytes(
        value: int,
    ) -> str:

        size = float(value)

        for unit in (
            "B",
            "KB",
            "MB",
            "GB",
        ):
            if (
                size < 1024
                or unit == "GB"
            ):
                if unit == "B":
                    return (
                        f"{int(size)} {unit}"
                    )

                return (
                    f"{size:.1f} {unit}"
                )

            size /= 1024

        return f"{value} B"

    # ------------------------------------------------------
    # Application closing
    # ------------------------------------------------------

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:

        if (
            self._thread is not None
            and self._thread.isRunning()
        ):
            self._close_after_request = True

            self.cancel_request()

            event.ignore()
            return

        event.accept()