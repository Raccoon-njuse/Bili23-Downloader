"""播放器私有媒体容器和历史索引。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .crypto import load_or_create_key, restore_file, seal_file
from .paths import CachePaths, cache_paths

from hashlib import sha256
from uuid import uuid4
import os
import shutil
import sqlite3
import threading
import time


@dataclass(frozen = True)
class CacheEntry:
    """可播放缓存的公开元数据；不保存 Cookie、下载 URL 或原始文件路径。"""

    cache_key: str
    owner_uid: str
    title: str
    duration: int
    file_name: str
    media_extension: str
    file_size: int
    created_at: int
    last_played_at: int


class CacheStore:
    """持久化缓存索引，并负责在原始媒体和私有容器之间转换。"""

    def __init__(self, paths: CachePaths = cache_paths):
        self.paths = paths
        self._seal_lock = threading.Lock()
        self.paths.ensure_layout()
        self._create_schema()

    def get_entry(self, cache_key: str, owner_uid: str) -> CacheEntry | None:
        """读取当前账号的有效缓存；丢失文件会同步剔除索引。"""
        if not owner_uid:
            return None

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM cache_entries WHERE cache_key = ? AND owner_uid = ?",
                (cache_key, owner_uid),
            ).fetchone()

        if row is None:
            return None

        entry = self._entry_from_row(row)
        if not self.media_path(entry).is_file():
            self.delete_entry(entry)
            return None

        return entry

    def list_entries(self, owner_uid: str) -> list[CacheEntry]:
        """按最近播放/缓存时间返回当前授权账号的缓存历史。"""
        if not owner_uid:
            return []

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM cache_entries
                WHERE owner_uid = ?
                ORDER BY last_played_at DESC, created_at DESC
                """,
                (owner_uid,),
            ).fetchall()

        entries = []
        for row in rows:
            entry = self._entry_from_row(row)
            if self.media_path(entry).is_file():
                entries.append(entry)
            else:
                self.delete_entry(entry)

        return entries

    def seal_task(self, task_info: Any, owner_uid: str) -> CacheEntry:
        """把下载器的最终媒体封装为私有缓存，并删除隐藏工作目录。"""
        if not owner_uid:
            raise RuntimeError("登录账号信息不可用，无法建立私有缓存。")

        raw_path = self._find_primary_media(task_info)
        cache_key = cache_key_from_task(task_info, owner_uid)

        with self._seal_lock:
            existing = self.get_entry(cache_key, owner_uid)
            if existing is not None:
                self._cleanup_work_file(raw_path)
                return existing

            extension = raw_path.suffix.lstrip(".").lower() or "mp4"
            file_name = f"{cache_key}.b23c"
            destination = self.media_path_from_name(file_name)
            container_size = seal_file(raw_path, destination, self._key())
            now = int(time.time())
            entry = CacheEntry(
                cache_key = cache_key,
                owner_uid = owner_uid,
                title = task_info.Basic.show_title,
                duration = int(task_info.Episode.duration or 0),
                file_name = file_name,
                media_extension = extension,
                file_size = container_size,
                created_at = now,
                last_played_at = now,
            )

            try:
                self._upsert_entry(entry)
            except Exception:
                destination.unlink(missing_ok = True)
                raise

            self._cleanup_work_file(raw_path)
            return entry

    def decrypt_for_playback(self, entry: CacheEntry) -> Path:
        """还原当前缓存到隐藏临时目录，播放器关闭时由 release_playback 清理。"""
        source = self.media_path(entry)
        if not source.is_file():
            self.delete_entry(entry)
            raise FileNotFoundError("缓存媒体文件不存在。")

        extension = _safe_extension(entry.media_extension)
        destination = self.paths.playback_root / f".{uuid4().hex}.{extension}"
        restore_file(source, destination, self._key())
        self.touch(entry)
        return destination

    def release_playback(self, path: Path | str | None) -> None:
        """删除短暂还原的媒体，仅接受本播放器的隐藏播放目录。"""
        if path is None:
            return

        candidate = Path(path)
        try:
            candidate.resolve().relative_to(self.paths.playback_root.resolve())
        except ValueError:
            return

        candidate.unlink(missing_ok = True)

    def cleanup_stale_playback(self) -> None:
        """应用启动时清理由异常退出遗留的临时明文和私有容器半成品。"""
        self.paths.ensure_layout()
        for path in self.paths.playback_root.iterdir():
            # 播放目录完全由本模块管理，其中的任何文件都不应跨进程保留。
            if path.is_file():
                path.unlink(missing_ok = True)

        for path in self.paths.media_root.iterdir():
            if path.is_file() and path.name.endswith(".part"):
                path.unlink(missing_ok = True)

    def discard_task_work(self, task_info: Any) -> None:
        """删除失败或已封存任务的私有工作目录，不接受缓存根目录本身。"""
        self._discard_work_directory(Path(task_info.File.download_path, task_info.File.folder))

    def _discard_work_directory(self, work_directory: Path) -> None:
        """校验工作目录归属后递归清理，作为所有明文清理路径的唯一入口。"""
        work_directory = work_directory.resolve()
        work_root = self.paths.work_root.resolve()

        try:
            relative_path = work_directory.relative_to(work_root)
        except ValueError as error:
            raise RuntimeError("拒绝清理缓存工作目录之外的文件。") from error

        if not relative_path.parts:
            raise RuntimeError("拒绝清理播放器缓存根目录。")

        shutil.rmtree(work_directory, ignore_errors = True)

    def delete_entry(self, entry: CacheEntry) -> None:
        """删除一个缓存索引及对应密文，不影响其他账号的缓存。"""
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM cache_entries WHERE cache_key = ? AND owner_uid = ?",
                (entry.cache_key, entry.owner_uid),
            )

        self.media_path(entry).unlink(missing_ok = True)

    def clear_entries(self, owner_uid: str) -> int:
        """一键清空当前账号全部缓存，返回已移除条数。"""
        entries = self.list_entries(owner_uid)
        for entry in entries:
            self.delete_entry(entry)
        return len(entries)

    def touch(self, entry: CacheEntry) -> None:
        """更新最近播放时间，使缓存列表把最近使用内容排在前面。"""
        now = int(time.time())
        with self._connect() as connection:
            connection.execute(
                "UPDATE cache_entries SET last_played_at = ? WHERE cache_key = ? AND owner_uid = ?",
                (now, entry.cache_key, entry.owner_uid),
            )

    def media_path(self, entry: CacheEntry) -> Path:
        """返回一条缓存的密文路径，并拒绝数据库外的路径穿越。"""
        return self.media_path_from_name(entry.file_name)

    def media_path_from_name(self, file_name: str) -> Path:
        """将数据库中的不透明文件名限制在媒体目录内。"""
        candidate = (self.paths.media_root / file_name).resolve()
        try:
            candidate.relative_to(self.paths.media_root.resolve())
        except ValueError as error:
            raise RuntimeError("缓存文件名无效。") from error
        return candidate

    def _find_primary_media(self, task_info: Any) -> Path:
        base = Path(task_info.File.download_path, task_info.File.folder)
        candidates = [
            base / file_name
            for file_name in task_info.File.relative_files
            if (base / file_name).is_file()
        ]
        if not candidates:
            raise FileNotFoundError("下载完成后未找到可缓存的媒体文件。")

        # 合并后的媒体一般最大；选最大文件可排除残余封面/字幕等附属文件。
        return max(candidates, key = lambda path: path.stat().st_size)

    def _cleanup_work_file(self, raw_path: Path) -> None:
        self._discard_work_directory(raw_path.parent)

    def _key(self) -> bytes:
        return load_or_create_key(self.paths.key_path)

    def _connect(self) -> sqlite3.Connection:
        self.paths.ensure_layout()
        connection = sqlite3.connect(self.paths.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_schema(self) -> None:
        # SQLite 不支持列级 COMMENT；字段含义如下：账号、标题、时长、密文文件名、媒体扩展名、大小和时间。
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT NOT NULL,
                    owner_uid TEXT NOT NULL,
                    title TEXT NOT NULL,
                    duration INTEGER NOT NULL,
                    file_name TEXT NOT NULL,
                    media_extension TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    last_played_at INTEGER NOT NULL,
                    PRIMARY KEY (cache_key, owner_uid)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_entries_recent ON cache_entries(owner_uid, last_played_at DESC)"
            )

    def _upsert_entry(self, entry: CacheEntry) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cache_entries (
                    cache_key, owner_uid, title, duration, file_name,
                    media_extension, file_size, created_at, last_played_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key, owner_uid) DO UPDATE SET
                    title = excluded.title,
                    duration = excluded.duration,
                    file_name = excluded.file_name,
                    media_extension = excluded.media_extension,
                    file_size = excluded.file_size,
                    created_at = excluded.created_at,
                    last_played_at = excluded.last_played_at
                """,
                (
                    entry.cache_key,
                    entry.owner_uid,
                    entry.title,
                    entry.duration,
                    entry.file_name,
                    entry.media_extension,
                    entry.file_size,
                    entry.created_at,
                    entry.last_played_at,
                ),
            )

    @staticmethod
    def _entry_from_row(row: sqlite3.Row) -> CacheEntry:
        return CacheEntry(
            cache_key = row["cache_key"],
            owner_uid = row["owner_uid"],
            title = row["title"],
            duration = row["duration"],
            file_name = row["file_name"],
            media_extension = row["media_extension"],
            file_size = row["file_size"],
            created_at = row["created_at"],
            last_played_at = row["last_played_at"],
        )


def cache_key_from_task(task_info: Any, owner_uid: str) -> str:
    """按账号和媒体标识生成缓存键，避免不同登录账号共用受限媒体。"""
    episode = task_info.Episode
    identity = "|".join(
        str(value)
        for value in (
            owner_uid,
            episode.attribute,
            episode.bvid,
            episode.aid,
            episode.cid,
            episode.ep_id,
            episode.sid,
        )
    )
    return sha256(identity.encode("utf-8")).hexdigest()


def cache_key_from_episode(episode: dict[str, Any], owner_uid: str) -> str:
    """在创建下载任务前用解析树数据计算同一套缓存键。"""
    identity = "|".join(
        str(value)
        for value in (
            owner_uid,
            episode.get("attribute", 0),
            episode.get("bvid", ""),
            episode.get("aid", 0),
            episode.get("cid", 0),
            episode.get("ep_id", 0),
            episode.get("sid", 0),
        )
    )
    return sha256(identity.encode("utf-8")).hexdigest()


def _safe_extension(value: str) -> str:
    normalized = "".join(char for char in value.lower() if char.isalnum())
    return normalized or "mp4"
