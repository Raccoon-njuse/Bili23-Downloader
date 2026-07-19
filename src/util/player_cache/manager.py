"""把现有下载器作为缓存后端，并在媒体封装后请求内置播放器。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from util.common.config import config
from util.common.enum import DownloadStatus, VideoContainer
from util.common.signal_bus import signal_bus
from util.download.downloader.manager import downloader_manager
from util.download.task.manager import task_manager
from util.thread.pool import GlobalThreadPoolTask

from .paths import cache_paths
from .store import CacheEntry, CacheStore, cache_key_from_episode

import logging
import shutil


logger = logging.getLogger(__name__)


# 仅桌面运行时创建默认缓存库；单元测试可传入临时 CachePaths 隔离文件系统。
cache_store = CacheStore()


class CacheDownloadRuntime(QObject):
    """隐藏下载队列的最小调度器，沿用原应用的下载并发和单路合并规则。"""

    def __init__(self, parent = None):
        super().__init__(parent)
        self.tasks: dict[str, object] = {}
        self._schedule_pending = False

        signal_bus.download.add_to_downloading_list.connect(self._on_add_tasks)
        signal_bus.download.auto_manage_concurrent_downloads.connect(self.schedule)
        signal_bus.download.remove_from_downloading_list.connect(self._on_remove_task)

    def _on_add_tasks(self, tasks: list) -> None:
        for task in tasks:
            if self._is_cache_task(task):
                self.tasks[task.Basic.task_id] = task
        self.schedule()

    def _on_remove_task(self, task) -> None:
        if not self._is_cache_task(task):
            return

        self.tasks.pop(task.Basic.task_id, None)
        downloader_manager.remove(task.Basic.task_id)
        self.schedule()

    def schedule(self) -> None:
        """合并同一事件循环周期内的多次调度请求。"""
        if self._schedule_pending:
            return

        self._schedule_pending = True
        QTimer.singleShot(0, self._manage)

    def _manage(self) -> None:
        self._schedule_pending = False
        task_list = list(self.tasks.values())
        active_downloads = [
            task for task in task_list
            if task.Download.status in (DownloadStatus.PARSING, DownloadStatus.DOWNLOADING)
        ]
        queued = [task for task in task_list if task.Download.status == DownloadStatus.QUEUED]

        while queued and len(active_downloads) < config.get(config.download_parallel):
            task = queued.pop(0)
            downloader_manager.get(task).start()
            active_downloads.append(task)

        merging = [
            task for task in task_list
            if task.Download.status in (DownloadStatus.MERGING, DownloadStatus.CONVERTING)
        ]
        waiting_merge = [task for task in task_list if task.Download.status == DownloadStatus.FFMPEG_QUEUED]
        if not merging and waiting_merge:
            downloader_manager.get(waiting_merge[0]).start_merge()

    @staticmethod
    def _is_cache_task(task) -> bool:
        return cache_paths.is_under_work_root(Path(task.File.download_path))


class CachePlaybackManager(QObject):
    """处理缓存命中、后台封装/还原、缓存历史变更和自动播放请求。"""

    cache_changed = Signal()
    cache_state_changed = Signal(str, int, str)
    playback_ready = Signal(object, str)
    playback_failed = Signal(str)
    playback_stop_requested = Signal()

    _entry_sealed = Signal(object, str)
    _entry_failed = Signal(str, str, str)
    _playback_decrypted = Signal(object, str, int)
    _playback_decrypt_failed = Signal(str)

    def __init__(self, parent = None):
        super().__init__(parent)
        self._pending_play_keys: set[str] = set()
        self._task_context: dict[str, tuple[str, str]] = {}
        self._sealing_task_ids: set[str] = set()
        self._active_entry: CacheEntry | None = None
        self._active_playback_path = ""
        self._playback_generation = 0

        self._configure_download_defaults()
        self._cleanup_private_runtime_state()

        signal_bus.download.add_to_completed_list.connect(self._on_tasks_completed)
        signal_bus.download.update_downloading_item.connect(self._on_download_updated)
        signal_bus.login.update_avatar.connect(lambda _: self.cache_changed.emit())

        self._entry_sealed.connect(self._on_entry_sealed)
        self._entry_failed.connect(self._on_entry_failed)
        self._playback_decrypted.connect(self._on_playback_decrypted)
        self._playback_decrypt_failed.connect(self.playback_failed)

    def request_play(self, episode_info: dict) -> None:
        """命中缓存即播放；未命中则下载、合并、封装完成后再打开播放器。"""
        owner_uid = self.current_owner_uid()
        if not owner_uid:
            self._show_login_required()
            return

        cache_key = cache_key_from_episode(episode_info, owner_uid)
        entry = cache_store.get_entry(cache_key, owner_uid)
        if entry is not None:
            self._prepare_playback(entry)
            return

        if cache_key in self._pending_play_keys:
            signal_bus.toast.show.emit(
                self._info_category(),
                "",
                "该视频正在缓存中。",
            )
            return

        self._pending_play_keys.add(cache_key)
        self._configure_download_defaults()
        task_list = task_manager.create([episode_info], show_toast = False) or []
        if not task_list:
            self._pending_play_keys.discard(cache_key)
            signal_bus.toast.show_long_message.emit(
                self._error_category(),
                "无法开始缓存",
                "未能创建媒体缓存任务。",
            )
            return

        task = task_list[0]
        self._task_context[task.Basic.task_id] = (cache_key, owner_uid)
        self.cache_state_changed.emit(task.Basic.show_title, 0, "缓存中")

    def list_entries(self) -> list[CacheEntry]:
        """仅返回当前登录账号的缓存历史。"""
        return cache_store.list_entries(self.current_owner_uid())

    def play_entry(self, entry: CacheEntry) -> None:
        """从缓存历史直接播放，避免再次构造下载任务或重新解析链接。"""
        owner_uid = self.current_owner_uid()
        if not owner_uid:
            self._show_login_required()
            return

        cached_entry = cache_store.get_entry(entry.cache_key, owner_uid)
        if cached_entry is None:
            signal_bus.toast.show.emit(self._error_category(), "缓存不可用", "该缓存文件已被删除或损坏。")
            self.cache_changed.emit()
            return

        self._prepare_playback(cached_entry)

    def delete_entry(self, entry: CacheEntry) -> None:
        """删除一条密文缓存和它的历史记录。"""
        self._cancel_pending_playback()
        if self._active_entry == entry:
            self.playback_stop_requested.emit()
        cache_store.delete_entry(entry)
        self.cache_changed.emit()

    def clear_cache(self) -> int:
        """清空当前账号的全部缓存。"""
        owner_uid = self.current_owner_uid()
        self._cancel_pending_playback()
        if self._active_entry is not None and self._active_entry.owner_uid == owner_uid:
            self.playback_stop_requested.emit()

        count = cache_store.clear_entries(owner_uid)
        self.cache_changed.emit()
        return count

    def release_playback(self, path: str) -> None:
        """由播放器窗口关闭事件调用，移除短暂还原出的媒体。"""
        cache_store.release_playback(path)
        if path == self._active_playback_path:
            self._active_entry = None
            self._active_playback_path = ""

    def current_owner_uid(self) -> str:
        """读取运行时登录账号 ID；未登录或用户资料未初始化时返回空字符串。"""
        if not config.get(config.is_login) or config.is_expired:
            return ""

        # 用户资料接口异步返回；扫码登录后先用已授权 Cookie 中的账号标识兜底，
        # 让用户无需等待头像和昵称加载完成才能开始缓存。
        return str(getattr(config, "user_uid", "") or config.get(config.DedeUserID)).strip()

    def _on_tasks_completed(self, tasks: list) -> None:
        for task in tasks:
            context = self._task_context.get(task.Basic.task_id)
            if context is None:
                # 任何绕过播放器入口的完成任务都不得留下普通媒体文件。
                if cache_paths.is_under_work_root(Path(task.File.download_path)):
                    try:
                        cache_store.discard_task_work(task)
                        task_manager.delete(task, completed = True)
                    except Exception:
                        logger.exception("清理无播放上下文的缓存任务失败：%s", task.Basic.task_id)
                continue

            if task.Basic.task_id in self._sealing_task_ids:
                continue

            self._sealing_task_ids.add(task.Basic.task_id)
            cache_key, owner_uid = context
            self.cache_state_changed.emit(task.Basic.show_title, 100, "整理缓存")
            GlobalThreadPoolTask.run_func(self._seal_completed_task, task, cache_key, owner_uid)

    def _on_download_updated(self, task) -> None:
        context = self._task_context.get(task.Basic.task_id)
        if context is None:
            return

        status = DownloadStatus(task.Download.status)
        self.cache_state_changed.emit(task.Basic.show_title, task.Download.progress, status.name.lower())
        if status in (DownloadStatus.FAILED, DownloadStatus.FFMPEG_FAILED):
            cache_key, _ = context
            self._pending_play_keys.discard(cache_key)
            self._task_context.pop(task.Basic.task_id, None)

    def _seal_completed_task(self, task, cache_key: str, owner_uid: str) -> None:
        """在线程池中封装大型媒体，避免阻塞 Qt 主线程。"""
        try:
            entry = cache_store.seal_task(task, owner_uid)
            task_manager.delete(task, completed = True)
            try:
                self._entry_sealed.emit(entry, cache_key)
            except RuntimeError:
                # 程序退出期间 QObject 已销毁时，媒体已安全封存，无需再回调 UI。
                logger.debug("播放器已关闭，跳过缓存封存回调：%s", task.Basic.task_id)
        except Exception as error:
            try:
                cache_store.discard_task_work(task)
                task_manager.delete(task, completed = True)
            except Exception:
                logger.exception("清理失败缓存工作区时出错：%s", task.Basic.task_id)
            try:
                self._entry_failed.emit(task.Basic.task_id, task.Basic.show_title, str(error))
            except RuntimeError:
                logger.debug("播放器已关闭，跳过缓存失败回调：%s", task.Basic.task_id)

    def _on_entry_sealed(self, entry: CacheEntry, cache_key: str) -> None:
        task_id = next(
            (task_id for task_id, context in self._task_context.items() if context[0] == cache_key),
            None,
        )
        if task_id is not None:
            self._task_context.pop(task_id, None)
            self._sealing_task_ids.discard(task_id)

        should_play = cache_key in self._pending_play_keys
        self._pending_play_keys.discard(cache_key)
        self.cache_changed.emit()
        if should_play:
            self._prepare_playback(entry)

    def _on_entry_failed(self, task_id: str, title: str, error: str) -> None:
        cache_key, _ = self._task_context.pop(task_id, ("", ""))
        if cache_key:
            self._pending_play_keys.discard(cache_key)
        self._sealing_task_ids.discard(task_id)
        signal_bus.toast.show_long_message.emit(self._error_category(), "缓存媒体失败", f"{title}\n\n{error}")

    def _prepare_playback(self, entry: CacheEntry) -> None:
        """在后台短暂还原，准备好后再由主窗口创建播放器。"""
        self._playback_generation += 1
        generation = self._playback_generation
        self.cache_state_changed.emit(entry.title, 100, "准备播放")
        GlobalThreadPoolTask.run_func(self._decrypt_entry, entry, generation)

    def _cancel_pending_playback(self) -> None:
        """使正在还原的旧请求失效，避免删除后仍弹出播放器。"""
        self._playback_generation += 1

    def _decrypt_entry(self, entry: CacheEntry, generation: int) -> None:
        try:
            path = cache_store.decrypt_for_playback(entry)
            try:
                self._playback_decrypted.emit(entry, str(path), generation)
            except RuntimeError:
                # 关闭应用时仍在运行的还原任务必须自行删除临时明文。
                cache_store.release_playback(path)
                logger.debug("播放器已关闭，已释放未交付的临时媒体。")
        except Exception as error:
            try:
                self._playback_decrypt_failed.emit(str(error))
            except RuntimeError:
                logger.debug("播放器已关闭，跳过播放失败回调。")

    def _on_playback_decrypted(self, entry: CacheEntry, path: str, generation: int) -> None:
        if generation != self._playback_generation:
            cache_store.release_playback(path)
            return

        self._active_entry = entry
        self._active_playback_path = path
        self.cache_changed.emit()
        self.playback_ready.emit(entry, path)

    def _cleanup_private_runtime_state(self) -> None:
        """删除异常退出残留的临时明文和未完成工作区，不触碰普通下载文件。"""
        cache_store.cleanup_stale_playback()
        if cache_paths.work_root.exists():
            for path in cache_paths.work_root.iterdir():
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors = True)

        for task in task_manager.query(completed = False):
            if cache_paths.is_under_work_root(Path(task.File.download_path)):
                task_manager.delete(task)
        for task in task_manager.query(completed = True):
            if cache_paths.is_under_work_root(Path(task.File.download_path)):
                task_manager.delete(task, completed = True)

    @staticmethod
    def _configure_download_defaults() -> None:
        """固定为适合本地缓存播放的媒体配置，且不写入用户原下载偏好。"""
        config.video_quality_id = 200
        config.audio_quality_id = 30300
        config.video_codec_id = 20
        config.download_video_stream = True
        config.download_audio_stream = True
        config.merge_video_audio = True
        config.keep_original_files = False
        config.target_naming_rule_id = None
        config.current_starting_number = 1

        # 720p 在播放延迟、磁盘占用和大多数内网/家庭网络下更平衡。
        config.set(config.video_quality_priority, [64, 32, 16], save = False)
        config.set(config.video_codec_priority, [7, 12, 13], save = False)
        config.set(config.video_container, VideoContainer.MP4, save = False)
        config.set(config.download_danmaku, False, save = False)
        config.set(config.download_subtitle, False, save = False)
        config.set(config.download_cover, False, save = False)
        config.set(config.download_metadata, False, save = False)
        config.set(config.attach_cover, False, save = False)
        config.set(config.m4a_to_mp3, False, save = False)

    @staticmethod
    def _show_login_required() -> None:
        signal_bus.toast.show.emit(
            CachePlaybackManager._error_category(),
            "需要登录",
            "请先完成扫码登录后再缓存和播放。",
        )

    @staticmethod
    def _info_category():
        from util.common.enum import ToastNotificationCategory
        return ToastNotificationCategory.INFO

    @staticmethod
    def _error_category():
        from util.common.enum import ToastNotificationCategory
        return ToastNotificationCategory.ERROR


cache_download_runtime = CacheDownloadRuntime()
cache_playback_manager = CachePlaybackManager()
