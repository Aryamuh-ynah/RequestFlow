from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.network.models import (
    NetworkStage,
    NetworkTimings,
)


@dataclass(slots=True)
class StageVisual:
    stage: NetworkStage
    rect: QRectF


STAGE_NAMES = {
    "dns": "DNS Lookup",
    "tcp": "TCP Connect",
    "tls": "TLS Handshake",
    "pre_transfer": "Request Setup",
    "first_byte": "First Byte",
    "download": "Download",
}


STAGE_EXPLANATIONS = {
    "dns": (
        "DNS translates the hostname in the URL into an IP address "
        "that the computer can connect to."
    ),
    "tcp": (
        "TCP establishes the network connection between your computer "
        "and the remote server."
    ),
    "tls": (
        "TLS creates the encrypted connection used by HTTPS before "
        "HTTP data is exchanged."
    ),
    "pre_transfer": (
        "This represents protocol setup completed after the connection "
        "is ready and immediately before the transfer begins."
    ),
    "first_byte": (
        "This is the time spent waiting between the request being ready "
        "for transfer and receiving the first response byte. For uploads, "
        "this interval can also include request-body transmission."
    ),
    "download": (
        "This is the time spent receiving the response after the first "
        "response byte arrived."
    ),
}


class FlowCanvas(QWidget):
    """
    Custom-painted network flow and waterfall timeline.

    This widget contains no networking logic. It only renders
    NetworkStage objects produced by Phase 2.
    """

    stage_selected = Signal(object)

    CARD_WIDTH = 150
    CARD_HEIGHT = 92

    CARD_GAP = 38

    LEFT_MARGIN = 28
    RIGHT_MARGIN = 28

    FLOW_TOP = 28
    WATERFALL_TOP = 165

    WATERFALL_ROW_HEIGHT = 27

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._timings: NetworkTimings | None = None
        self._stage_visuals: list[StageVisual] = []

        self._selected_key: str | None = None
        self._hovered_key: str | None = None

        self.setMouseTracking(True)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.setMinimumHeight(365)

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def set_timings(
        self,
        timings: NetworkTimings,
    ) -> None:
        self._timings = timings

        self._selected_key = None
        self._hovered_key = None

        stage_count = len(timings.stages)

        width = (
            self.LEFT_MARGIN
            + self.RIGHT_MARGIN
            + stage_count * self.CARD_WIDTH
            + max(0, stage_count - 1) * self.CARD_GAP
        )

        self.setMinimumWidth(
            max(900, width)
        )

        self.update()

    def clear(self) -> None:
        self._timings = None
        self._stage_visuals.clear()

        self._selected_key = None
        self._hovered_key = None

        self.setMinimumWidth(900)

        self.update()

    # ---------------------------------------------------------
    # Painting
    # ---------------------------------------------------------

    def paintEvent(
        self,
        event: QPaintEvent,
    ) -> None:
        del event

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        painter.fillRect(
            self.rect(),
            QColor("#15181d"),
        )

        if self._timings is None:
            self._paint_empty(painter)
            return

        self._paint_flow(painter)
        self._paint_waterfall(painter)

    def _paint_empty(
        self,
        painter: QPainter,
    ) -> None:
        painter.setPen(
            QColor("#7f8894")
        )

        font = painter.font()
        font.setPointSize(11)

        painter.setFont(font)

        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "Send a request to visualize its network flow.",
        )

    # ---------------------------------------------------------
    # Flow cards
    # ---------------------------------------------------------

    def _paint_flow(
        self,
        painter: QPainter,
    ) -> None:
        assert self._timings is not None

        stages = self._timings.stages

        self._stage_visuals.clear()

        x = float(self.LEFT_MARGIN)

        slowest_key = self._slowest_stage_key()

        for index, stage in enumerate(stages):
            rect = QRectF(
                x,
                self.FLOW_TOP,
                self.CARD_WIDTH,
                self.CARD_HEIGHT,
            )

            self._stage_visuals.append(
                StageVisual(
                    stage=stage,
                    rect=rect,
                )
            )

            self._paint_stage_card(
                painter,
                stage,
                rect,
                stage.key == slowest_key,
            )

            if index < len(stages) - 1:
                self._paint_arrow(
                    painter,
                    rect,
                )

            x += (
                self.CARD_WIDTH
                + self.CARD_GAP
            )

    def _paint_stage_card(
        self,
        painter: QPainter,
        stage: NetworkStage,
        rect: QRectF,
        is_slowest: bool,
    ) -> None:

        selected = (
            stage.key
            == self._selected_key
        )

        hovered = (
            stage.key
            == self._hovered_key
        )

        if stage.skipped:
            background = QColor("#1b1e23")
            border = QColor("#343942")

        elif selected:
            background = QColor("#29315b")
            border = QColor("#7180ff")

        elif hovered:
            background = QColor("#242936")
            border = QColor("#596573")

        else:
            background = QColor("#1d2128")
            border = QColor("#353b45")

        painter.setBrush(background)

        painter.setPen(
            QPen(
                border,
                1.5,
            )
        )

        painter.drawRoundedRect(
            rect,
            10,
            10,
        )

        # Stage title
        painter.setPen(
            QColor(
                "#aeb6c2"
                if not stage.skipped
                else "#666d77"
            )
        )

        title_font = QFont(
            painter.font()
        )

        title_font.setPointSize(9)
        title_font.setBold(True)

        painter.setFont(title_font)

        title = STAGE_NAMES.get(
            stage.key,
            stage.label,
        )

        painter.drawText(
            QRectF(
                rect.left() + 12,
                rect.top() + 12,
                rect.width() - 24,
                22,
            ),
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter,
            title,
        )

        # Duration
        duration_font = QFont(
            painter.font()
        )

        duration_font.setPointSize(14)
        duration_font.setBold(True)

        painter.setFont(duration_font)

        if stage.skipped:
            painter.setPen(
                QColor("#777f89")
            )

            duration_text = "Not used"

        else:
            painter.setPen(
                QColor("#f0f2f5")
            )

            duration_text = (
                f"{stage.duration_ms:.2f} ms"
            )

        painter.drawText(
            QRectF(
                rect.left() + 12,
                rect.top() + 36,
                rect.width() - 24,
                30,
            ),
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter,
            duration_text,
        )

        if (
            is_slowest
            and not stage.skipped
            and stage.duration_ms > 0
        ):
            badge_font = QFont(
                painter.font()
            )

            badge_font.setPointSize(7)
            badge_font.setBold(False)

            painter.setFont(badge_font)

            painter.setPen(
                QColor("#f4c56b")
            )

            painter.drawText(
                QRectF(
                    rect.left() + 12,
                    rect.bottom() - 24,
                    rect.width() - 24,
                    18,
                ),
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter,
                "Longest stage",
            )

    def _paint_arrow(
        self,
        painter: QPainter,
        rect: QRectF,
    ) -> None:
        start_x = rect.right() + 7
        end_x = (
            rect.right()
            + self.CARD_GAP
            - 7
        )

        y = rect.center().y()

        pen = QPen(
            QColor("#59616c"),
            2,
        )

        painter.setPen(pen)

        painter.drawLine(
            QPointF(
                start_x,
                y,
            ),
            QPointF(
                end_x,
                y,
            ),
        )

        painter.drawLine(
            QPointF(
                end_x - 7,
                y - 5,
            ),
            QPointF(
                end_x,
                y,
            ),
        )

        painter.drawLine(
            QPointF(
                end_x - 7,
                y + 5,
            ),
            QPointF(
                end_x,
                y,
            ),
        )

    # ---------------------------------------------------------
    # Waterfall
    # ---------------------------------------------------------

    def _paint_waterfall(
        self,
        painter: QPainter,
    ) -> None:
        assert self._timings is not None

        total_ms = max(
            self._timings.total_ms,
            0.001,
        )

        left_label_width = 135

        graph_left = (
            self.LEFT_MARGIN
            + left_label_width
        )

        graph_right = (
            self.width()
            - self.RIGHT_MARGIN
        )

        graph_width = max(
            100.0,
            graph_right - graph_left,
        )

        # Header
        header_font = QFont(
            painter.font()
        )

        header_font.setPointSize(10)
        header_font.setBold(True)

        painter.setFont(header_font)

        painter.setPen(
            QColor("#aeb6c2")
        )

        painter.drawText(
            self.LEFT_MARGIN,
            self.WATERFALL_TOP - 16,
            "Timing waterfall",
        )

        painter.setPen(
            QColor("#626a75")
        )

        painter.drawLine(
            QPointF(
                graph_left,
                self.WATERFALL_TOP,
            ),
            QPointF(
                graph_right,
                self.WATERFALL_TOP,
            ),
        )

        small_font = QFont(
            painter.font()
        )

        small_font.setPointSize(8)
        small_font.setBold(False)

        painter.setFont(small_font)

        painter.drawText(
            QRectF(
                graph_left,
                self.WATERFALL_TOP - 20,
                60,
                18,
            ),
            Qt.AlignmentFlag.AlignLeft,
            "0 ms",
        )

        painter.drawText(
            QRectF(
                graph_right - 100,
                self.WATERFALL_TOP - 20,
                100,
                18,
            ),
            Qt.AlignmentFlag.AlignRight,
            f"{total_ms:.1f} ms",
        )

        for row, stage in enumerate(
            self._timings.stages
        ):
            y = (
                self.WATERFALL_TOP
                + 15
                + row * self.WATERFALL_ROW_HEIGHT
            )

            painter.setPen(
                QColor("#98a1ad")
            )

            painter.drawText(
                QRectF(
                    self.LEFT_MARGIN,
                    y,
                    left_label_width - 12,
                    20,
                ),
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter,
                STAGE_NAMES.get(
                    stage.key,
                    stage.label,
                ),
            )

            # Row background
            track_rect = QRectF(
                graph_left,
                y + 5,
                graph_width,
                10,
            )

            painter.setBrush(
                QColor("#20242b")
            )

            painter.setPen(
                Qt.PenStyle.NoPen
            )

            painter.drawRoundedRect(
                track_rect,
                4,
                4,
            )

            if stage.skipped:
                continue

            start_ratio = min(
                max(
                    stage.start_ms / total_ms,
                    0.0,
                ),
                1.0,
            )

            end_ratio = min(
                max(
                    stage.end_ms / total_ms,
                    start_ratio,
                ),
                1.0,
            )

            start_x = (
                graph_left
                + graph_width * start_ratio
            )

            end_x = (
                graph_left
                + graph_width * end_ratio
            )

            bar_width = max(
                3.0,
                end_x - start_x,
            )

            if (
                stage.key
                == self._selected_key
            ):
                bar_color = QColor(
                    "#7180ff"
                )

            else:
                bar_color = QColor(
                    "#5865f2"
                )

            painter.setBrush(
                bar_color
            )

            painter.drawRoundedRect(
                QRectF(
                    start_x,
                    y + 5,
                    bar_width,
                    10,
                ),
                4,
                4,
            )

    # ---------------------------------------------------------
    # Mouse
    # ---------------------------------------------------------

    def mouseMoveEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        key = self._stage_at(
            event.position()
        )

        if key != self._hovered_key:
            self._hovered_key = key

            if key:
                self.setCursor(
                    Qt.CursorShape.PointingHandCursor
                )
            else:
                self.unsetCursor()

            self.update()

        super().mouseMoveEvent(event)

    def leaveEvent(
        self,
        event,
    ) -> None:
        self._hovered_key = None
        self.unsetCursor()

        self.update()

        super().leaveEvent(event)

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if (
            event.button()
            != Qt.MouseButton.LeftButton
        ):
            return

        position = event.position()

        for visual in self._stage_visuals:
            if visual.rect.contains(position):
                self._selected_key = (
                    visual.stage.key
                )

                self.stage_selected.emit(
                    visual.stage
                )

                self.update()
                return

    def _stage_at(
        self,
        position: QPointF,
    ) -> str | None:
        for visual in self._stage_visuals:
            if visual.rect.contains(
                position
            ):
                return visual.stage.key

        return None

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def _slowest_stage_key(
        self,
    ) -> str | None:
        if self._timings is None:
            return None

        candidates = [
            stage
            for stage in self._timings.stages
            if (
                not stage.skipped
                and stage.duration_ms > 0
            )
        ]

        if not candidates:
            return None

        slowest = max(
            candidates,
            key=lambda item: item.duration_ms,
        )

        return slowest.key


class FlowPanel(QWidget):
    """
    Complete Flow tab.

    Contains:
        - request summary
        - scrollable visual flow
        - timing waterfall
        - stage explanation panel
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._timings: NetworkTimings | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )

        layout.setSpacing(10)

        # -----------------------------------------------------
        # Summary
        # -----------------------------------------------------

        summary_layout = QHBoxLayout()

        self.total_label = QLabel(
            "No timing data"
        )

        self.total_label.setStyleSheet(
            """
            QLabel {
                color: #e8eaed;
                font-size: 14px;
                font-weight: 700;
            }
            """
        )

        self.endpoint_label = QLabel(
            ""
        )

        self.endpoint_label.setStyleSheet(
            """
            QLabel {
                color: #8e97a3;
            }
            """
        )

        summary_layout.addWidget(
            self.total_label
        )

        summary_layout.addStretch(1)

        summary_layout.addWidget(
            self.endpoint_label
        )

        layout.addLayout(
            summary_layout
        )

        # -----------------------------------------------------
        # Canvas
        # -----------------------------------------------------

        self.canvas = FlowCanvas()

        self.canvas.stage_selected.connect(
            self._stage_selected
        )

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        scroll.setWidget(
            self.canvas
        )

        layout.addWidget(
            scroll,
            1,
        )

        # -----------------------------------------------------
        # Details
        # -----------------------------------------------------

        detail_frame = QFrame()

        detail_frame.setStyleSheet(
            """
            QFrame {
                background: #191d23;
                border: 1px solid #2d333d;
                border-radius: 10px;
            }

            QLabel {
                border: none;
                background: transparent;
            }
            """
        )

        detail_layout = QVBoxLayout(
            detail_frame
        )

        detail_layout.setContentsMargins(
            14,
            12,
            14,
            12,
        )

        self.detail_title = QLabel(
            "Select a stage"
        )

        self.detail_title.setStyleSheet(
            """
            QLabel {
                color: #f0f2f5;
                font-size: 14px;
                font-weight: 700;
            }
            """
        )

        self.detail_text = QLabel(
            "Click a network stage above to learn what happened."
        )

        self.detail_text.setWordWrap(
            True
        )

        self.detail_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.detail_text.setStyleSheet(
            """
            QLabel {
                color: #9ba4af;
                line-height: 1.4;
            }
            """
        )

        detail_layout.addWidget(
            self.detail_title
        )

        detail_layout.addWidget(
            self.detail_text
        )

        layout.addWidget(
            detail_frame
        )

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def set_timings(
        self,
        timings: NetworkTimings,
    ) -> None:
        self._timings = timings

        self.canvas.set_timings(
            timings
        )

        self.total_label.setText(
            f"Total request time: "
            f"{timings.total_ms:.2f} ms"
        )

        endpoint = ""

        if timings.primary_ip:
            endpoint = timings.primary_ip

            if timings.primary_port:
                endpoint += (
                    f":{timings.primary_port}"
                )

        if endpoint:
            self.endpoint_label.setText(
                f"Remote: {endpoint}"
            )
        else:
            self.endpoint_label.clear()

        self.detail_title.setText(
            "Select a stage"
        )

        self.detail_text.setText(
            "Click any stage to inspect its timing "
            "and understand what happened."
        )

    def clear(self) -> None:
        self._timings = None

        self.canvas.clear()

        self.total_label.setText(
            "No timing data"
        )

        self.endpoint_label.clear()

        self.detail_title.setText(
            "Select a stage"
        )

        self.detail_text.setText(
            "Send a request to visualize its "
            "network lifecycle."
        )

    # ---------------------------------------------------------
    # Stage details
    # ---------------------------------------------------------

    def _stage_selected(
        self,
        stage: NetworkStage,
    ) -> None:

        title = STAGE_NAMES.get(
            stage.key,
            stage.label,
        )

        self.detail_title.setText(
            title
        )

        explanation = STAGE_EXPLANATIONS.get(
            stage.key,
            "No explanation is available for this stage.",
        )

        if stage.skipped:
            timing_text = (
                "This stage was not used for the request."
            )

        else:
            timing_text = (
                f"Duration: {stage.duration_ms:.2f} ms\n"
                f"Started: {stage.start_ms:.2f} ms\n"
                f"Finished: {stage.end_ms:.2f} ms"
            )

        self.detail_text.setText(
            f"{timing_text}\n\n"
            f"{explanation}"
        )