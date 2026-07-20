"""CLI 下载调度器：复用桌面端 Downloader 与 Merger，不创建任何 UI 控件。"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import os
import shutil
import subprocess
import sys

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Slot

from util.common.config import config
from util.common.enum import DownloadStatus, DuplicateDownloadResolution, FFmpegSource, VideoContainer
from util.common.signal_bus import signal_bus

from .service import CLIServiceError, task_to_public


@dataclass
class DownloadOptions:
    """一次 CLI 下载要覆盖的桌面端下载设置。"""

    output_path: Path | None = None
    video_quality_id: int = 200
    audio_quality_id: int = 30300
    video_codec_id: int = 20
    video_only: bool = False
    audio_only: bool = False
    merge: bool = True
    keep_original_files: bool = False
    container: str = "mp4"
    download_danmaku: bool = False
    download_subtitle: bool = False
    download_cover: bool = False
    download_metadata: bool = False
    duplicate: str = "skip"


class TemporaryDownloadSettings(AbstractContextManager):
    """在下载期间覆盖运行时配置，结束后恢复用户原有 UI 设置。"""

    def __init__(self, options: DownloadOptions):
        self.options = options
        self._config_item_values: list[tuple[object, object]] = []
        self._dynamic_values: dict[str, object] = {}

    def __enter__(self):
        # 使用 save=False，确保一次 Agent 调用不会永久修改用户在 GUI 里保存的偏好。
        self._set_config_item(config.download_path, str(self.options.output_path) if self.options.output_path else config.get(config.download_path))
        self._set_config_item(config.video_container, VideoContainer(self.options.container))
        self._set_config_item(config.download_danmaku, self.options.download_danmaku)
        self._set_config_item(config.download_subtitle, self.options.download_subtitle)
        self._set_config_item(config.download_cover, self.options.download_cover)
        self._set_config_item(config.download_metadata, self.options.download_metadata)
        self._set_config_item(
            config.duplicate_download_resolution,
            DuplicateDownloadResolution.CONTINUE if self.options.duplicate == "continue" else DuplicateDownloadResolution.SKIP,
        )

        for name, value in {
            "video_quality_id": self.options.video_quality_id,
            "audio_quality_id": self.options.audio_quality_id,
            "video_codec_id": self.options.video_codec_id,
            "download_video_stream": not self.options.audio_only,
            "download_audio_stream": not self.options.video_only,
            "merge_video_audio": self.options.merge and not self.options.video_only and not self.options.audio_only,
            "keep_original_files": self.options.keep_original_files,
        }.items():
            self._dynamic_values[name] = getattr(config, name)
            setattr(config, name, value)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        for item, value in reversed(self._config_item_values):
            config.set(item, value, save = False)

        for name, value in self._dynamic_values.items():
            setattr(config, name, value)

        return False

    def _set_config_item(self, item, value):
        self._config_item_values.append((item, config.get(item)))
        config.set(item, value, save = False)


class CLIDownloadCoordinator(QObject):
    """用桌面端相同的并发/合并规则驱动任务，但将状态汇总为 CLI 结果。"""

    def __init__(self, app: QCoreApplication, progress_callback: Callable[[str], None] | None = None):
        super().__init__()
        self.app = app
        self.progress_callback = progress_callback
        self.tasks = []
        self.errors: list[str] = []
        self._schedule_pending = False
        self._finished = False

        # 定时器仅用于人类可读进度；结构化结果只在命令结束时输出到 stdout。
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(1000)
        self.progress_timer.timeout.connect(self._report_progress)

        self._connections = [
            (signal_bus.download.add_to_downloading_list, self._on_add_tasks),
            (signal_bus.download.auto_manage_concurrent_downloads, self._schedule),
            (signal_bus.download.add_to_completed_list, self._on_completed),
            (signal_bus.download.remove_from_downloading_list, self._on_removed),
            (signal_bus.toast.show_long_message, self._on_error_message),
        ]

        for signal, slot in self._connections:
            signal.connect(slot)

    def run(self, created_tasks: list) -> dict:
        """进入 QCoreApplication 事件循环，直到本次创建的任务全部终结。"""
        self._register_tasks(created_tasks)
        self._schedule()
        self.progress_timer.start()
        self.app.exec()
        self.progress_timer.stop()

        return {
            "tasks": [task_to_public(task) for task in self.tasks],
            "errors": self.errors,
            "success": all(task.Download.status == DownloadStatus.COMPLETED for task in self.tasks),
        }

    def close(self):
        """清理全局 signal bus 连接，便于单元测试与同进程多次调用。"""
        self.progress_timer.stop()

        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    @Slot(list)
    def _on_add_tasks(self, tasks: list):
        self._register_tasks(tasks)
        self._schedule()

    @Slot()
    def _schedule(self):
        if self._finished or self._schedule_pending:
            return

        self._schedule_pending = True
        QTimer.singleShot(0, self._run_schedule)

    def _run_schedule(self):
        self._schedule_pending = False
        if self._finished:
            return

        from util.download.downloader.manager import downloader_manager

        # 与 DownloadListModel.manageConcurrentDownloads 保持相同的下载并发规则。
        active_downloads = [
            task for task in self.tasks
            if task.Download.status in (DownloadStatus.PARSING, DownloadStatus.DOWNLOADING)
        ]
        queued = [task for task in self.tasks if task.Download.status == DownloadStatus.QUEUED]

        while queued and len(active_downloads) < config.get(config.download_parallel):
            task = queued.pop(0)
            downloader_manager.get(task).start()
            active_downloads.append(task)

        # 合并阶段限制为一个任务，和桌面端行为一致，避免 FFmpeg 争抢 CPU/IO。
        merging = [
            task for task in self.tasks
            if task.Download.status in (DownloadStatus.MERGING, DownloadStatus.CONVERTING)
        ]
        merge_queued = [task for task in self.tasks if task.Download.status == DownloadStatus.FFMPEG_QUEUED]

        if not merging and merge_queued:
            downloader_manager.get(merge_queued[0]).start_merge()

        self._finish_if_terminal()

    @Slot(list)
    def _on_completed(self, tasks: list):
        self._register_tasks(tasks)
        self._schedule()

    @Slot(object)
    def _on_removed(self, task):
        self._finish_if_terminal()

    @Slot(object, str, str)
    def _on_error_message(self, _category, _title: str, message: str):
        # Toast 内容仅在失败时用于诊断，不包含请求 Cookie。
        if message and message not in self.errors:
            self.errors.append(message)

    def _register_tasks(self, tasks: list):
        known = {task.Basic.task_id for task in self.tasks}
        self.tasks.extend(task for task in tasks if task.Basic.task_id not in known)

    def _finish_if_terminal(self):
        if not self.tasks:
            return

        terminal = (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.FFMPEG_FAILED)
        if all(task.Download.status in terminal for task in self.tasks):
            self._finished = True
            QTimer.singleShot(0, self.app.quit)

    def _report_progress(self):
        if self.progress_callback is None:
            return

        states = [
            f"{task.Basic.show_title}: {task.Download.progress}% ({DownloadStatus(task.Download.status).name.lower()})"
            for task in self.tasks
        ]
        self.progress_callback(" | ".join(states))


def run_download(episodes: list[dict], options: DownloadOptions, progress_callback: Callable[[str], None] | None = None) -> dict:
    """创建下载任务，并同步等待既有 Downloader/Merger 完成全部工作。"""
    if not episodes:
        raise CLIServiceError("没有可下载的剧集。")
    if options.video_only and options.audio_only:
        raise CLIServiceError("--video-only 与 --audio-only 不能同时使用。")

    if options.output_path is not None and options.output_path.exists() and not options.output_path.is_dir():
        raise CLIServiceError(f"下载目录不是目录：{options.output_path}")

    # 仅在真实下载时初始化共享任务数据库和桌面端 Downloader。
    from util.download.downloader.manager import downloader_manager
    from util.download.task.manager import task_manager

    app = QCoreApplication.instance() or QCoreApplication(["media-agent"])
    coordinator = CLIDownloadCoordinator(app, progress_callback)

    try:
        with TemporaryDownloadSettings(options):
            ensure_ffmpeg_available()
            created_tasks = task_manager.create(episodes, show_toast = False)

            if not created_tasks:
                return {
                    "tasks": [],
                    "errors": ["没有创建下载任务；该内容可能已存在于任务列表中。可使用 --duplicate continue 强制创建。"],
                    "success": False,
                }

            return coordinator.run(created_tasks)
    finally:
        for task in coordinator.tasks:
            if task.Download.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.FFMPEG_FAILED):
                downloader_manager.remove(task.Basic.task_id)
        coordinator.close()


def ensure_ffmpeg_available() -> str:
    """选择并实测 FFmpeg，且不修改用户保存的 GUI 设置。"""
    executable_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    # 源码 CLI 允许从任意工作目录调用；打包版仍由 PYSTAND_HOME 指向资源根目录。
    base_dir = Path(os.environ.get("PYSTAND_HOME") or Path(__file__).resolve().parents[2])
    bundled = base_dir / "bundle" / executable_name
    custom = Path(config.get(config.custom_ffmpeg_path)).expanduser()
    system = shutil.which(executable_name)

    # 打包版优先 bundle，源码开发则回退系统 PATH；每个候选都必须实际可执行。
    source = config.get(config.ffmpeg_source)
    if source == FFmpegSource.CUSTOM:
        candidates = [custom, bundled, system]
    elif source == FFmpegSource.SYSTEM:
        candidates = [system, bundled]
    else:
        candidates = [bundled, system]

    errors = []
    for candidate in candidates:
        if not candidate:
            continue

        path = Path(candidate)
        if not path.is_file():
            continue

        result = subprocess.run(
            [str(path), "-hide_banner", "-version"],
            stdout = subprocess.DEVNULL,
            stderr = subprocess.PIPE,
            text = True,
            check = False,
        )
        if result.returncode == 0:
            # FFmpegCommand 固定调用 `ffmpeg`，所以只在本进程首位注入最终可用二进制的目录。
            os.environ["PATH"] = f"{path.parent}{os.pathsep}{os.environ.get('PATH', '')}"
            return str(path)

        errors.append(result.stderr.strip() or f"{path}: 退出码 {result.returncode}")

    detail = "; ".join(errors) if errors else "未找到候选二进制"
    raise CLIServiceError(f"未找到可执行的 FFmpeg：{detail}")


def ffmpeg_diagnostic() -> dict:
    """为 doctor 命令提供是否可合并媒体的明确诊断。"""
    try:
        return {"available": True, "path": ensure_ffmpeg_available()}
    except CLIServiceError as error:
        return {"available": False, "error": str(error)}
