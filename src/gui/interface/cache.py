"""播放器私有缓存的历史列表。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QHeaderView, QTreeWidgetItem, QVBoxLayout, QWidget

from qfluentwidgets import BodyLabel, FluentIcon, MessageBox, PushButton, SubtitleLabel, ToolButton, TreeWidget

from util.format.time import Time
from util.format.units import Units
from util.player_cache.manager import cache_playback_manager
from util.player_cache.store import CacheEntry


class CacheInterface(QFrame):
    """展示当前账号的可播放缓存，且不暴露媒体文件或普通下载任务。"""

    def __init__(self, parent = None):
        super().__init__(parent = parent)

        self.main_window = parent
        self._entries: dict[str, CacheEntry] = {}
        self.setObjectName("CacheInterface")

        self._init_ui()
        self._connect_signals()
        self.reload_entries()

    def _init_ui(self) -> None:
        self.title_label = SubtitleLabel(self.tr("Cache"), self)
        self.status_label = BodyLabel("", self)
        self.status_label.setMinimumWidth(0)

        self.clear_button = PushButton(FluentIcon.DELETE, self.tr("Clear All"), self)

        self.cache_list = TreeWidget(self)
        self.cache_list.setSelectionMode(TreeWidget.SelectionMode.SingleSelection)
        self.cache_list.setIndentation(0)
        self.cache_list.setHeaderLabels(
            [
                self.tr("Title"),
                self.tr("Duration"),
                self.tr("Cached"),
                self.tr("Size"),
                self.tr("Actions"),
            ]
        )
        self.cache_list.setColumnWidth(0, 360)
        self.cache_list.setColumnWidth(1, 90)
        self.cache_list.setColumnWidth(2, 160)
        self.cache_list.setColumnWidth(3, 105)
        self.cache_list.setColumnWidth(4, 95)
        self.cache_list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cache_list.header().setStretchLastSection(False)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(self.title_label)
        top_layout.addSpacing(12)
        top_layout.addWidget(self.status_label, 1)
        top_layout.addWidget(self.clear_button)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 15, 25, 15)
        main_layout.setSpacing(12)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.cache_list, 1)

    def _connect_signals(self) -> None:
        self.clear_button.clicked.connect(self._clear_all)
        self.cache_list.itemDoubleClicked.connect(lambda item, _column: self._play_item(item))

        cache_playback_manager.cache_changed.connect(self.reload_entries)
        cache_playback_manager.cache_state_changed.connect(self._on_cache_state_changed)

    def reload_entries(self) -> None:
        """刷新当前账号的缓存索引，不读取或展示磁盘上的媒体路径。"""
        self.cache_list.clear()
        self._entries.clear()

        entries = cache_playback_manager.list_entries()
        for entry in entries:
            self._entries[entry.cache_key] = entry
            item = QTreeWidgetItem(
                [
                    entry.title,
                    Units.format_episode_duration(entry.duration),
                    Time.format_timestamp(entry.created_at),
                    Units.format_file_size(entry.file_size),
                    "",
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, entry.cache_key)
            item.setSizeHint(0, QSize(0, 40))
            self.cache_list.addTopLevelItem(item)
            self.cache_list.setItemWidget(item, 4, self._create_action_widget(entry))

        self.clear_button.setEnabled(bool(entries))
        if not entries:
            self.status_label.setText(self.tr("No cached videos"))
        elif not self.status_label.text():
            self.status_label.setText(self.tr("{count} cached").format(count = len(entries)))

    def _create_action_widget(self, entry: CacheEntry) -> QWidget:
        action_widget = QWidget(self.cache_list)
        play_button = ToolButton(FluentIcon.PLAY, action_widget)
        play_button.setToolTip(self.tr("Play"))
        delete_button = ToolButton(FluentIcon.DELETE, action_widget)
        delete_button.setToolTip(self.tr("Delete"))

        layout = QHBoxLayout(action_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(play_button)
        layout.addWidget(delete_button)

        play_button.clicked.connect(lambda: cache_playback_manager.play_entry(entry))
        delete_button.clicked.connect(lambda: self._delete_entry(entry))
        return action_widget

    def _play_item(self, item: QTreeWidgetItem) -> None:
        entry = self._entries.get(item.data(0, Qt.ItemDataRole.UserRole))
        if entry is not None:
            cache_playback_manager.play_entry(entry)

    def _delete_entry(self, entry: CacheEntry) -> None:
        cache_playback_manager.delete_entry(entry)

    def _clear_all(self) -> None:
        if not self._entries:
            return

        dialog = MessageBox(
            self.tr("Clear cache"),
            self.tr("Remove all cached videos for the current account?"),
            self.main_window,
        )
        dialog.yesButton.setText(self.tr("Clear"))
        dialog.cancelButton.setText(self.tr("Cancel"))
        if dialog.exec():
            cache_playback_manager.clear_cache()

    def _on_cache_state_changed(self, title: str, progress: int, state: str) -> None:
        """显示下载到播放的状态，不记录链接或在线播放历史。"""
        if state == "缓存中":
            self.status_label.setText(self.tr("Caching {progress}%").format(progress = progress))
        elif state == "整理缓存":
            self.status_label.setText(self.tr("Finalizing cache"))
        elif state == "准备播放":
            self.status_label.setText(self.tr("Preparing playback"))
        elif state in {"failed", "ffmpeg_failed"}:
            self.status_label.setText(self.tr("Caching failed"))
        else:
            self.status_label.setText(state.replace("_", " ").title())
