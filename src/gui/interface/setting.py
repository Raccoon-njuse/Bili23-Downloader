"""播放器分支的最小设置页。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QVBoxLayout, QWidget

from qfluentwidgets import (
    ComboBoxSettingCard,
    FluentIcon,
    MSFluentWindow,
    MessageBox,
    SettingCardGroup,
    setTheme,
    setThemeColor,
)

from gui.component.setting import CheckUpdateSettingCard, FFmpegSettingCard, PersonalizationCard, ProxySettingCard
from gui.component.widget.scroll import ScrollArea

from util.common.config import config
from util.common.enum import ToastNotificationCategory
from util.common.signal_bus import signal_bus
from util.common.style_sheet import StyleSheet


class SettingInterface(ScrollArea):
    """只保留影响播放运行环境的设置，不显示下载和个人内容选项。"""

    def __init__(self, parent = None):
        super().__init__(parent = parent)

        self.main_window: MSFluentWindow = parent
        self.setObjectName("SettingInterface")
        self._init_ui()

    def _init_ui(self) -> None:
        self.scroll_widget = QWidget()
        self.scroll_widget.setObjectName("scrollWidget")
        self.expand_layout = QVBoxLayout(self.scroll_widget)

        self.interface_group = SettingCardGroup(self.tr("Interface"), self)
        self.personalization_card = PersonalizationCard(self.main_window, self)
        self.scaling_card = ComboBoxSettingCard(
            config.display_scaling,
            FluentIcon.ZOOM,
            self.tr("Display Scaling"),
            self.tr("Adjust the scaling of the application interface"),
            ["100%", "125%", "150%", "175%", "200%", self.tr("System default")],
            self,
        )
        self.language_card = ComboBoxSettingCard(
            config.language,
            FluentIcon.LANGUAGE,
            self.tr("Language"),
            self.tr("Choose the display language of the application"),
            ["简体中文", "繁體中文", "English", self.tr("System default")],
            self,
        )

        self.runtime_group = SettingCardGroup(self.tr("Playback Runtime"), self)
        self.ffmpeg_card = FFmpegSettingCard(self.main_window, self)
        self.proxy_card = ProxySettingCard(self)

        self.update_group = SettingCardGroup(self.tr("Updates"), self)
        self.check_update_card = CheckUpdateSettingCard(self)

        self.interface_group.addSettingCard(self.personalization_card)
        self.interface_group.addSettingCard(self.scaling_card)
        self.interface_group.addSettingCard(self.language_card)
        self.runtime_group.addSettingCard(self.ffmpeg_card)
        self.runtime_group.addSettingCard(self.proxy_card)
        self.update_group.addSettingCard(self.check_update_card)

        self.expand_layout.setSpacing(28)
        self.expand_layout.setContentsMargins(30, 10, 30, 0)
        self.expand_layout.addWidget(self.interface_group)
        self.expand_layout.addWidget(self.runtime_group)
        self.expand_layout.addWidget(self.update_group)
        self.expand_layout.addStretch(1)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scroll_widget)
        self.setWidgetResizable(True)
        StyleSheet.SETTING_INTERFACE.apply(self)

        self._connect_signals()

    def _connect_signals(self) -> None:
        config.themeChanged.connect(setTheme)
        config.appRestartSig.connect(self._show_restart_message)
        self.personalization_card.accentColorChanged.connect(setThemeColor)
        self.personalization_card.mica_effect_switch.checkedChanged.connect(signal_bus.interface.mica_effect_changed)

        self.ffmpeg_card.source_choice.currentIndexChanged.connect(self._on_change_ffmpeg_source)
        self.ffmpeg_card.custom_btn.clicked.connect(self._on_change_ffmpeg_path)
        self.proxy_card.custom_btn.clicked.connect(self._on_custom_proxy)
        self.check_update_card.check_now_btn.clicked.connect(self._on_check_update)

    def _on_change_ffmpeg_source(self, index: int) -> None:
        if index == 0 and not config.bundle_ffmpeg_exist:
            dialog = MessageBox(
                self.tr("Bundled FFmpeg not found"),
                self.tr("The bundled FFmpeg executable is missing. Please switch to 'System PATH' or specify a custom path."),
                self.main_window,
            )
            dialog.hideCancelButton()
            if dialog.exec():
                self.ffmpeg_card.source_choice.setCurrentIndex(1)

        self.ffmpeg_card.custom_group.setEnabled(index == 2)

    def _on_change_ffmpeg_path(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select FFmpeg executable"),
            config.get(config.custom_ffmpeg_path),
            self.tr("FFmpeg executable ({executable})").format(executable = config.ffmpeg_executable),
        )
        if not file_path:
            return

        config.set(config.custom_ffmpeg_path, file_path)
        self.ffmpeg_card.custom_group.setContent(file_path)

    def _on_custom_proxy(self) -> None:
        from ..dialog.setting.proxy import ProxyDialog

        ProxyDialog(self.main_window).exec()

    @staticmethod
    def _on_check_update() -> None:
        signal_bus.update.check.emit(True)

    def _show_restart_message(self) -> None:
        signal_bus.toast.show.emit(
            ToastNotificationCategory.SUCCESS,
            "",
            self.tr("Configuration takes effect after restart"),
        )
