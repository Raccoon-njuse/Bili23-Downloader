"""只保留链接解析、剧集选择和缓存播放的入口。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QVBoxLayout

from qfluentwidgets import Action, BodyLabel, FluentIcon, LineEdit, PrimaryPushButton

from gui.component.parse_list import ParseTreeView
from gui.component.widget import SeasonComboBox, SegmentedWidget

from util.common.enum import ToastNotificationCategory
from util.common.signal_bus import signal_bus
from util.common.translator import Translator
from util.parse.worker import ParseWorker, WorkerBase
from util.player_cache.manager import cache_playback_manager
from util.thread.async_ import AsyncTask

import logging


logger = logging.getLogger(__name__)


# 个人空间、收藏夹、历史、稍后再看和榜单均不属于播放器的链接解析范围。
SUPPORTED_PARSER_TYPES = {"video", "bangumi", "cheese", "audio", "b23", "festival"}


class ParseInterface(QFrame):
    """解析一个可播放链接，让用户选择一个剧集后缓存并在应用内播放。"""

    def __init__(self, parent = None):
        super().__init__(parent = parent)

        self.main_window = parent
        self.category_name = ""
        self.setObjectName("ParseInterface")

        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        paste_action = Action(icon = FluentIcon.PASTE, text = self.tr("Paste and Parse"), parent = self)
        paste_action.triggered.connect(lambda _checked: self._paste_and_parse())

        self.url_box = LineEdit(self)
        self.url_box.setPlaceholderText(self.tr("Link / av / BV / ep / ss / md"))
        self.url_box.setClearButtonEnabled(True)
        self.url_box.addAction(paste_action, LineEdit.ActionPosition.TrailingPosition)

        self.parse_button = PrimaryPushButton(self.tr("Parse"), self)
        self.parse_button.setMinimumWidth(88)

        self.item_count_label = BodyLabel("", self)
        self.cache_state_label = BodyLabel("", self)
        self.cache_state_label.setMinimumWidth(0)
        self.parse_list = ParseTreeView(self.main_window, parent = self)

        self.segmented_widget = SegmentedWidget(self)
        self.segmented_widget.hide()
        # 分页仅浏览同一链接的结果，禁用旧自动解析菜单批量创建任务。
        self.segmented_widget.pager_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self.season_choice = SeasonComboBox(self)
        self.season_choice.setFixedWidth(150)
        self.season_choice.hide()

        self.play_button = PrimaryPushButton(FluentIcon.PLAY, self.tr("Cache and Play"), self)
        self.play_button.setMinimumWidth(140)
        self.play_button.setEnabled(False)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(self.url_box)
        top_layout.addWidget(self.parse_button)

        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.addWidget(self.item_count_label)
        info_layout.addStretch()
        info_layout.addWidget(self.cache_state_label)

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(self.segmented_widget)
        bottom_layout.addWidget(self.season_choice)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.play_button)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 15, 25, 15)
        main_layout.setSpacing(10)
        main_layout.addLayout(top_layout)
        main_layout.addLayout(info_layout)
        main_layout.addWidget(self.parse_list, 1)
        main_layout.addLayout(bottom_layout)

    def _connect_signals(self) -> None:
        self.parse_button.clicked.connect(self.on_parse)
        self.url_box.returnPressed.connect(self.on_parse)
        self.segmented_widget.pager_widget.pageChanged.connect(self.on_parse)
        self.season_choice.changeSeason.connect(self.reparse)
        self.parse_list._model.check_state_changed.connect(self._on_item_check_state_changed)
        self.play_button.clicked.connect(self._cache_and_play)

        signal_bus.parse.update_parse_list.connect(self._on_update_parse_list)
        signal_bus.parse.update_parse_list_count.connect(self._on_update_parse_list_count)
        cache_playback_manager.cache_state_changed.connect(self._on_cache_state_changed)
        cache_playback_manager.playback_failed.connect(self._on_playback_failed)

    def _paste_and_parse(self) -> None:
        url = QApplication.clipboard().text().strip()
        if not url:
            return

        self.url_box.setText(url)
        self.on_parse()

    def on_parse(self, page: int = 1) -> None:
        """只接受直接媒体链接，避免把账号个性化内容交给解析器。"""
        url = self.url_box.text().strip()
        if not url:
            signal_bus.toast.show.emit(ToastNotificationCategory.WARNING, self.tr("Invalid link"), self.tr("Paste a supported video link."))
            return

        try:
            parser_type = WorkerBase().get_parser_type(url)
        except ValueError as error:
            signal_bus.toast.show.emit(ToastNotificationCategory.ERROR, self.tr("Parse Failed"), str(error))
            return

        if parser_type not in SUPPORTED_PARSER_TYPES:
            signal_bus.toast.show.emit(
                ToastNotificationCategory.WARNING,
                self.tr("Unsupported link"),
                self.tr("Only direct video, episode, course, audio, and short links are supported."),
            )
            return

        self._set_parsing_state(True)
        # 除初始 URL 外，也会校验 b23/festival 等重定向后的真实页面类型。
        worker = ParseWorker(url, page, allowed_parser_types = SUPPORTED_PARSER_TYPES)
        worker.success.connect(self._on_parse_success)
        worker.error.connect(self._on_parse_error)

        logger.info("开始解析播放器链接，类型: %s, 页码: %d", parser_type, page)
        AsyncTask.run(worker)

    def _on_parse_success(self, category_name: str, extra_data: dict) -> None:
        self.parse_list._model._set_category_name(category_name)
        self.category_name = Translator.EPISODE_TYPE(category_name)
        self._update_extra_data(extra_data)
        self._on_item_check_state_changed(None)
        self._set_parsing_state(False)

    def _on_parse_error(self, error_message: str) -> None:
        self._set_parsing_state(False)
        self.parse_list.clear_tree()
        self.segmented_widget.hide_pager()
        self.season_choice.hide()
        self.item_count_label.setText("")
        self.play_button.setEnabled(False)
        signal_bus.toast.show.emit(ToastNotificationCategory.ERROR, self.tr("Parse Failed"), error_message)

    def _on_update_parse_list(self, _title: str, _category_name: str, root_node, current_episode_data: dict) -> None:
        """仅更新当前解析结果；不将链接写入任何解析历史。"""
        self.parse_list.update_tree(root_node, current_episode_data)

    def _on_update_parse_list_count(self, category_name: str, count: int) -> None:
        self.category_name = Translator.EPISODE_TYPE(category_name)
        self.item_count_label.setText(
            self.tr("{category_name} ({total_count} total)").format(
                category_name = self.category_name,
                total_count = count,
            )
        )

    def _update_extra_data(self, extra_data: dict) -> None:
        if extra_data.get("pagination"):
            self.segmented_widget.show_pager(extra_data["pagination_data"])
        else:
            self.segmented_widget.hide_pager()

        if extra_data.get("seasons"):
            self.season_choice.update_data(extra_data["season_data"])
        else:
            self.season_choice.hide()

    def _on_item_check_state_changed(self, _index) -> None:
        checked_count = self.parse_list.get_checked_items_count()
        total_count = self.parse_list.get_total_items_count()
        self.play_button.setEnabled(checked_count > 0)

        if total_count:
            self.item_count_label.setText(
                self.tr("{category_name} ({selected_count} selected, {total_count} total)").format(
                    category_name = self.category_name,
                    selected_count = checked_count,
                    total_count = total_count,
                )
            )

    def _cache_and_play(self) -> None:
        episodes = self.parse_list.get_checked_items(to_dict = True, mark_as_downloaded = False)
        if len(episodes) != 1:
            signal_bus.toast.show.emit(
                ToastNotificationCategory.WARNING,
                self.tr("Select one episode"),
                self.tr("Choose exactly one episode to cache and play."),
            )
            return

        cache_playback_manager.request_play(episodes[0])

    def _on_cache_state_changed(self, _title: str, progress: int, state: str) -> None:
        """在解析页显示当前缓存进度，不把任务写入旧下载列表。"""
        if state == "缓存中":
            self.cache_state_label.setText(self.tr("Caching {progress}%").format(progress = progress))
        elif state == "整理缓存":
            self.cache_state_label.setText(self.tr("Finalizing cache"))
        elif state == "准备播放":
            self.cache_state_label.setText(self.tr("Preparing playback"))
        elif state in {"failed", "ffmpeg_failed"}:
            self.cache_state_label.setText(self.tr("Caching failed"))
        else:
            self.cache_state_label.setText(state.replace("_", " ").title())

    def _on_playback_failed(self, error: str) -> None:
        self.cache_state_label.setText(self.tr("Playback failed"))
        signal_bus.toast.show_long_message.emit(
            ToastNotificationCategory.ERROR,
            self.tr("Playback failed"),
            error,
        )

    def _set_parsing_state(self, parsing: bool) -> None:
        self.parse_button.setEnabled(not parsing)
        self.parse_button.setText(self.tr("Parsing...") if parsing else self.tr("Parse"))

    def adjust_column_width(self) -> None:
        self.parse_list.header().setSectionResizeMode(1, self.parse_list.header().ResizeMode.Stretch)

    def reparse(self, url: str) -> None:
        self.url_box.setText(url)
        self.on_parse()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_A:
            self.parse_list.check_all_items()
            event.accept()
            return

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_D:
            self.parse_list.check_all_items(uncheck = True)
            event.accept()
            return

        super().keyPressEvent(event)
