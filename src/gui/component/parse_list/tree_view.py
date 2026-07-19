"""播放器解析结果树，只提供剧集选择能力。"""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import QModelIndex, QTimer, Qt

from qfluentwidgets import TreeView, isDarkTheme, setCustomStyleSheet

from .model import ParseModel

from util.common.config import config
from util.common.signal_bus import signal_bus
from util.parse.episode.tree import TreeItem


class ParseTreeView(TreeView):
    """展示当前链接的剧集并允许勾选，不提供下载或外部跳转菜单。"""

    def __init__(self, main_window, parent = None):
        super().__init__(parent)

        self.main_window = main_window
        self._model = ParseModel(parent = self)
        self._expand_timer = QTimer(self)
        self._expand_timer.setSingleShot(True)
        self._expand_timer.timeout.connect(self._expand_next_batch)
        self._expand_queue = deque()
        self._expand_callback = None
        self._expand_batch_size = 100

        self.setModel(self._model)
        self.setUniformRowHeights(True)
        self.setSortingEnabled(True)
        self.setSelectionMode(TreeView.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        signal_bus.parse.update_column_settings.connect(self._set_header_width)
        self._set_header_width()
        self._update_alternate_row_color()

    def _set_header_width(self) -> None:
        for index, entry in enumerate(config.get(config.parse_list_column)):
            self.setColumnWidth(index, entry["width"])

        self._schedule_expand_all()
        self.header().setStretchLastSection(False)

    def update_tree(self, root_node: TreeItem, current_episode_data: tuple = None) -> None:
        self._model.beginResetModel()
        self._model.root_node = root_node
        self._model.endResetModel()
        self._schedule_expand_all(lambda: self.locate_to_item_by_episode_data(current_episode_data))

    def clear_tree(self) -> None:
        self.update_tree(TreeItem({"number": "", "title": ""}))

    def get_all_items(self):
        return self._model.root_node.get_all_children()

    def get_checked_items(self, to_dict = False, mark_as_downloaded = False):
        return self._model.root_node.get_all_checked_children(
            to_dict = to_dict,
            mark_as_downloaded = mark_as_downloaded,
        )

    def get_checked_items_count(self) -> int:
        return len(self.get_checked_items())

    def get_total_items_count(self) -> int:
        return len(self.get_all_items())

    def check_all_items(self, uncheck = False) -> None:
        """保留键盘全选/全不选，便于从剧集树中选择目标项。"""
        state = Qt.CheckState.Unchecked if uncheck else Qt.CheckState.Checked
        self._model.root_node.set_checked_state(state)
        self.update_check_state()

    def locate_to_item_by_episode_data(self, current_episode_data: tuple = None) -> None:
        if not current_episode_data:
            return

        key, value = current_episode_data
        for item in self.get_all_items():
            if getattr(item, key) == value:
                self.scroll_to_item(item)
                item.set_checked_state(Qt.CheckState.Checked)
                self.update_check_state()
                break

    def scroll_to_item(self, item: TreeItem) -> None:
        index = self._model.get_index_for_item(item)
        if index.isValid():
            self.scrollTo(index)
            self.setCurrentIndex(index)

    def update_check_state(self) -> None:
        self._model.check_state_changed.emit(QModelIndex())

    def _schedule_expand_all(self, callback = None) -> None:
        self._expand_queue.clear()
        self._expand_queue.append(QModelIndex())
        self._expand_callback = callback
        if not self._expand_timer.isActive():
            self._expand_timer.start(0)

    def _expand_next_batch(self) -> None:
        processed = 0
        while self._expand_queue and processed < self._expand_batch_size:
            parent = self._expand_queue.popleft()
            for row in range(self._model.rowCount(parent)):
                index = self._model.index(row, 0, parent)
                if not index.isValid():
                    continue

                self.expand(index)
                self._expand_queue.append(index)
                processed += 1
                if processed >= self._expand_batch_size:
                    break

        if self._expand_queue:
            self._expand_timer.start(0)
            return

        callback = self._expand_callback
        self._expand_callback = None
        if callback:
            callback()

    def _update_alternate_row_color(self) -> None:
        if not config.get(config.parse_list_alternate_row_color):
            return

        light_style = """
            QTreeView {
                background-color: transparent;
                alternate-background-color: rgba(0, 0, 0, 0.05);
            }
        """
        dark_style = """
            QTreeView {
                background-color: transparent;
                alternate-background-color: rgba(255, 255, 255, 0.08);
            }
        """
        setCustomStyleSheet(self, light_style, dark_style)
