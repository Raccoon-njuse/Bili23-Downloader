"""播放器私有缓存：保存私有媒体容器、缓存索引与临时播放文件。"""

from .paths import CachePaths, cache_paths
from .store import CacheEntry, CacheStore

__all__ = ["CacheEntry", "CachePaths", "CacheStore", "cache_paths"]
