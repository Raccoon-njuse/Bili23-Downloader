"""定义播放器缓存的私有目录布局。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths

import os
import sys


class CachePaths:
    """管理媒体密文、临时工作区和缓存索引所在目录。"""

    def __init__(self, root: Path | None = None):
        # macOS 优先落在 ~/Library/Caches，避免出现在用户的 Downloads 文件夹中。
        self.root = Path(root) if root is not None else self._default_root()

    @staticmethod
    def _default_root() -> Path:
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Caches" / "Bili23 Player"

        cache_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericCacheLocation)
        if cache_root:
            return Path(cache_root) / "Bili23 Player"

        app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(app_data) / "cache"

    @property
    def media_root(self) -> Path:
        """持久化的私有媒体容器目录。"""
        return self.root / "media"

    @property
    def work_root(self) -> Path:
        """下载/合并期间使用的隐藏临时目录。"""
        return self.root / ".work"

    @property
    def playback_root(self) -> Path:
        """仅在播放器打开时保留短暂明文的隐藏临时目录。"""
        return self.root / ".playback"

    @property
    def database_path(self) -> Path:
        """缓存历史的 SQLite 索引文件。"""
        return self.root / "cache.sqlite3"

    @property
    def key_path(self) -> Path:
        """本机私钥文件；不随缓存列表或日志暴露。"""
        return self.root / ".cache-key"

    def ensure_layout(self) -> None:
        """创建私有目录并收紧其 POSIX 权限。"""
        for path in (self.root, self.media_root, self.work_root, self.playback_root):
            path.mkdir(parents = True, exist_ok = True)
            self._restrict_permissions(path)

    def is_under_work_root(self, path: Path) -> bool:
        """确认路径属于本播放器创建的临时目录，避免误删其他下载文件。"""
        try:
            path.resolve().relative_to(self.work_root.resolve())
            return True
        except ValueError:
            return False

    @staticmethod
    def _restrict_permissions(path: Path) -> None:
        # Windows 不支持 POSIX chmod 语义，忽略即可。
        if os.name != "nt":
            path.chmod(0o700)


cache_paths = CachePaths()
