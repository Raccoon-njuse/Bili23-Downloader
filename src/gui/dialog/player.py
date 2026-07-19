"""缓存媒体的内置播放器窗口。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QDialog, QHBoxLayout, QSizePolicy, QSlider, QVBoxLayout

from qfluentwidgets import BodyLabel, CaptionLabel, FluentIcon, ToolButton

from util.format.units import Units


class PlayerDialog(QDialog):
    """播放一份临时还原媒体，并在关闭时通知缓存层释放文件。"""

    closed = Signal(str)

    def __init__(self, title: str, media_path: str, duration: int = 0, parent = None):
        super().__init__(parent)

        self._media_path = str(Path(media_path))
        self._fallback_duration_ms = max(int(duration), 0) * 1000
        self._released = False
        self._dragging_timeline = False

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(title)
        self.setMinimumSize(820, 520)
        self.resize(1040, 660)

        self._init_player()
        self._init_ui(title)
        self._connect_signals()

        self.player.setSource(QUrl.fromLocalFile(self._media_path))
        self.player.play()

    def _init_player(self) -> None:
        """初始化 Qt 多媒体对象；媒体始终是缓存层给出的临时文件。"""
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.8)

        self.player = QMediaPlayer(self)
        self.video_widget = QVideoWidget(self)
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)

        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

    def _init_ui(self, title: str) -> None:
        self.title_label = BodyLabel(title, self)
        self.title_label.setWordWrap(False)
        self.title_label.setMinimumWidth(0)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        self.play_pause_button = ToolButton(FluentIcon.PAUSE, self)
        self.play_pause_button.setToolTip(self.tr("Pause"))
        self.play_pause_button.setFixedSize(36, 36)

        self.timeline = QSlider(Qt.Orientation.Horizontal, self)
        self.timeline.setRange(0, self._fallback_duration_ms)
        self.timeline.setSingleStep(1000)
        self.timeline.setPageStep(10_000)

        self.position_label = CaptionLabel(self._format_time(0), self)
        self.duration_label = CaptionLabel(self._format_time(self._fallback_duration_ms), self)

        self.volume_button = ToolButton(FluentIcon.VOLUME, self)
        self.volume_button.setToolTip(self.tr("Mute"))
        self.volume_button.setFixedSize(36, 36)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(100)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(self.title_label)
        top_layout.addStretch()

        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(8)
        control_layout.addWidget(self.play_pause_button)
        control_layout.addWidget(self.position_label)
        control_layout.addWidget(self.timeline, 1)
        control_layout.addWidget(self.duration_label)
        control_layout.addSpacing(8)
        control_layout.addWidget(self.volume_button)
        control_layout.addWidget(self.volume_slider)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(10)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.video_widget, 1)
        main_layout.addLayout(control_layout)

        self.video_widget.setStyleSheet("background: black;")

    def _connect_signals(self) -> None:
        self.play_pause_button.clicked.connect(self._toggle_playback)
        self.timeline.sliderPressed.connect(self._on_timeline_pressed)
        self.timeline.sliderReleased.connect(self._on_timeline_released)
        self.timeline.sliderMoved.connect(self._on_timeline_moved)
        self.volume_button.clicked.connect(self._toggle_mute)
        self.volume_slider.valueChanged.connect(self._set_volume)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.errorOccurred.connect(self._on_error)

    def _toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_timeline_pressed(self) -> None:
        self._dragging_timeline = True

    def _on_timeline_released(self) -> None:
        self.player.setPosition(self.timeline.value())
        self._dragging_timeline = False

    def _on_timeline_moved(self, position: int) -> None:
        self.position_label.setText(self._format_time(position))

    def _on_position_changed(self, position: int) -> None:
        if self._dragging_timeline:
            return

        signals_were_blocked = self.timeline.blockSignals(True)
        try:
            self.timeline.setValue(position)
        finally:
            self.timeline.blockSignals(signals_were_blocked)
        self.position_label.setText(self._format_time(position))

    def _on_duration_changed(self, duration: int) -> None:
        if duration <= 0:
            return

        self.timeline.setRange(0, duration)
        self.duration_label.setText(self._format_time(duration))

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_pause_button.setIcon(FluentIcon.PAUSE if playing else FluentIcon.PLAY)
        self.play_pause_button.setToolTip(self.tr("Pause") if playing else self.tr("Play"))

    def _toggle_mute(self) -> None:
        self.audio_output.setMuted(not self.audio_output.isMuted())
        self._sync_volume_icon()

    def _set_volume(self, value: int) -> None:
        self.audio_output.setMuted(value == 0)
        self.audio_output.setVolume(value / 100)
        self._sync_volume_icon()

    def _sync_volume_icon(self) -> None:
        muted = self.audio_output.isMuted() or self.audio_output.volume() <= 0
        self.volume_button.setIcon(FluentIcon.MUTE if muted else FluentIcon.VOLUME)
        self.volume_button.setToolTip(self.tr("Unmute") if muted else self.tr("Mute"))

    def _on_error(self, _error: QMediaPlayer.Error, error_text: str) -> None:
        # Qt 会在窗口中保留黑色视频区域；标题栏不会泄露临时媒体文件位置。
        self.title_label.setText(self.tr("Unable to play: {message}").format(message = error_text))

    @staticmethod
    def _format_time(milliseconds: int) -> str:
        return Units.format_duration(max(milliseconds, 0) // 1000)

    def closeEvent(self, event) -> None:
        """断开播放器对文件的占用，并把临时明文交回缓存层清理。"""
        if not self._released:
            self._released = True
            self.player.stop()
            self.player.setSource(QUrl())
            self.closed.emit(self._media_path)

        super().closeEvent(event)
