"""Media Agent CLI 的 Agent 友好命令行入口。"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys

# qfluentwidgets 在导入时会输出推广提示。CLI 保持 stdout 只包含 JSON，方便 Agent 解析。
with contextlib.redirect_stdout(io.StringIO()):
    from cli.service import (
        Bili23CLIService,
        CLIServiceError,
        cli_runtime_paths,
        parse_audio_quality,
        parse_video_codec,
        parse_video_quality,
    )


class CLIArgumentParser(argparse.ArgumentParser):
    """将无效参数转换成 CLIServiceError，保持 Agent 可解析的 JSON 错误契约。"""

    def error(self, message: str):
        raise CLIServiceError(f"参数错误：{message}")


def build_parser() -> argparse.ArgumentParser:
    """声明稳定的命令契约；所有成功结果均输出一行 JSON。"""
    parser = CLIArgumentParser(
        prog = "media-agent",
        description = "基于本机 Media Agent CLI 登录态的无界面命令行",
    )
    subparsers = parser.add_subparsers(dest = "command", required = True)

    auth = subparsers.add_parser("auth", help = "查看当前登录态")
    auth_sub = auth.add_subparsers(dest = "auth_command", required = True)
    auth_sub.add_parser("status", help = "刷新并输出登录账户摘要")

    favorites = subparsers.add_parser("favorites", help = "读取当前账户收藏夹")
    favorites_sub = favorites.add_subparsers(dest = "favorites_command", required = True)
    favorites_list = favorites_sub.add_parser("list", help = "列出收藏夹")
    favorites_list.add_argument("--include-collected", action = "store_true", help = "同时列出收藏的他人收藏夹")
    favorites_items = favorites_sub.add_parser("items", help = "列出一个收藏夹中的视频")
    favorites_items.add_argument("favorite", help = "收藏夹 ID 或收藏夹链接")
    favorites_items.add_argument("--page", type = positive_int, default = 1, help = "页码，默认 1")

    inspect = subparsers.add_parser("inspect", help = "解析链接并列出可选剧集")
    inspect.add_argument("url", help = "Bilibili 链接、BV/AV、ep/ss/md 等")
    inspect.add_argument("--page", type = positive_int, default = 1, help = "列表/收藏夹页码")
    add_selection_arguments(inspect)
    inspect.add_argument("--with-media", action = "store_true", help = "额外请求选中剧集的清晰度和编码信息")

    download = subparsers.add_parser("download", help = "下载指定链接中的剧集")
    download.add_argument("url", help = "Bilibili 链接、BV/AV、ep/ss/md 等")
    download.add_argument("--page", type = positive_int, default = 1, help = "列表/收藏夹页码")
    add_selection_arguments(download)
    download.add_argument("--quality", default = "auto", help = "auto、720p、1080p、4k 或 quality ID")
    download.add_argument("--audio-quality", default = "auto", help = "auto、192k、132k、64k 或 quality ID")
    download.add_argument("--codec", default = "auto", help = "auto、h264、h265、av1 或 codec ID")
    download.add_argument("--output", type = Path, help = "下载根目录；未传入时沿用 GUI 设置")
    media_group = download.add_mutually_exclusive_group()
    media_group.add_argument("--video-only", action = "store_true", help = "只下载独立视频流")
    media_group.add_argument("--audio-only", action = "store_true", help = "只下载独立音频流")
    download.add_argument("--no-merge", action = "store_true", help = "保留独立音视频文件，不调用合并")
    download.add_argument("--keep-original-files", action = "store_true", help = "合并后保留原始音视频流")
    download.add_argument("--container", choices = ("mp4", "mkv"), default = "mp4", help = "合并产物容器")
    download.add_argument("--danmaku", action = "store_true", help = "同时下载弹幕")
    download.add_argument("--subtitle", action = "store_true", help = "同时下载字幕")
    download.add_argument("--cover", action = "store_true", help = "同时下载封面")
    download.add_argument("--metadata", action = "store_true", help = "同时下载元数据")
    download.add_argument("--duplicate", choices = ("skip", "continue"), default = "skip", help = "遇到重复任务时跳过或继续")
    download.add_argument("--dry-run", action = "store_true", help = "只解析与校验，不创建文件或下载任务")

    tasks = subparsers.add_parser("tasks", help = "查看桌面端共享的下载任务列表")
    tasks_sub = tasks.add_subparsers(dest = "tasks_command", required = True)
    tasks_list = tasks_sub.add_parser("list", help = "列出进行中任务")
    tasks_list.add_argument("--completed", action = "store_true", help = "改为列出已完成任务")
    tasks_list.add_argument("--limit", type = positive_int, help = "最多返回多少条任务")

    subparsers.add_parser("doctor", help = "检查登录态、FFmpeg 与下载目录空间")
    return parser


def add_selection_arguments(parser: argparse.ArgumentParser):
    """在 inspect/download 之间复用严格且不易误选的剧集 selector。"""
    selector_group = parser.add_argument_group("剧集选择")
    selector_group.add_argument("--episode", type = positive_int, help = "剧集序号，例如第 27 集传 27")
    selector_group.add_argument("--part", type = positive_int, help = "分 P 序号")
    selector_group.add_argument("--ep-id", type = positive_int, help = "精确的 Bilibili ep_id")
    selector_group.add_argument("--cid", type = positive_int, help = "精确的 Bilibili cid")
    selector_group.add_argument("--match", help = "标题包含的文本")
    selector_group.add_argument("--all", action = "store_true", help = "选择全部解析出的叶子项")


def positive_int(value: str) -> int:
    """拒绝 0 和负数，避免错误选择第 0 集。"""
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"应为正整数：{value}") from error

    if number <= 0:
        raise argparse.ArgumentTypeError(f"应为正整数：{value}")

    return number


def selected_episodes(service: Bili23CLIService, parsed, args) -> list[dict]:
    """统一处理所有需要指定剧集的子命令。"""
    return service.select_episodes(
        parsed,
        episode = args.episode,
        part = args.part,
        ep_id = args.ep_id,
        cid = args.cid,
        title_contains = args.match,
        select_all = args.all,
    )


def dispatch(args: argparse.Namespace) -> tuple[dict, int]:
    """执行一条命令并返回 JSON 数据和进程退出码。"""
    service = Bili23CLIService()

    if args.command == "auth":
        return service.auth_status(), 0

    if args.command == "favorites":
        if args.favorites_command == "list":
            return service.list_favorites(include_collected = args.include_collected), 0

        parsed = service.parse_url(normalize_favorite_input(args.favorite), page = args.page)
        return parsed.to_public_dict(), 0

    if args.command == "inspect":
        parsed = service.parse_url(args.url, page = args.page)
        result = parsed.to_public_dict()

        if args.with_media:
            episodes = selected_episodes(service, parsed, args)
            result["media"] = [
                {
                    "episode": episode,
                    "options": service.media_options(episode),
                }
                for episode in episodes
            ]

        return result, 0

    if args.command == "download":
        # 仅下载命令初始化任务数据库和下载器，避免 --help/inspect 产生缓存文件。
        from cli.download import DownloadOptions, run_download

        parsed = service.parse_url(args.url, page = args.page)
        episodes = selected_episodes(service, parsed, args)
        video_quality_id = parse_video_quality(args.quality)
        audio_quality_id = parse_audio_quality(args.audio_quality)
        codec_id = parse_video_codec(args.codec)
        plan = service.validate_download_plan(episodes, video_quality_id, audio_quality_id)

        if args.dry_run:
            return {"dry_run": True, "plan": plan}, 0

        output_path = args.output.expanduser().resolve() if args.output else None
        options = DownloadOptions(
            output_path = output_path,
            video_quality_id = video_quality_id,
            audio_quality_id = audio_quality_id,
            video_codec_id = codec_id,
            video_only = args.video_only,
            audio_only = args.audio_only,
            merge = not args.no_merge,
            keep_original_files = args.keep_original_files,
            container = args.container,
            download_danmaku = args.danmaku,
            download_subtitle = args.subtitle,
            download_cover = args.cover,
            download_metadata = args.metadata,
            duplicate = args.duplicate,
        )
        result = run_download(episodes, options, progress_callback = lambda text: print(text, file = sys.stderr, flush = True))
        result["plan"] = plan
        return result, 0 if result["success"] else 2

    if args.command == "tasks":
        return {"completed": args.completed, "tasks": service.list_tasks(args.completed, args.limit)}, 0

    if args.command == "doctor":
        from cli.download import ffmpeg_diagnostic

        auth = service.auth_status()
        paths = cli_runtime_paths()
        usage = shutil.disk_usage(nearest_existing_path(Path(paths["download_path"])))
        return {
            "auth": auth,
            "ffmpeg": ffmpeg_diagnostic(),
            "download_path": paths["download_path"],
            "disk": {
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
            },
        }, 0

    raise CLIServiceError("未知命令。")


def normalize_favorite_input(value: str) -> str:
    """允许 favorites items 同时接受纯 ID 和 UI 中复制出的收藏夹链接。"""
    if value.isdigit():
        return f"https://space.bilibili.com/0/favlist?fid={value}"

    return value


def nearest_existing_path(path: Path) -> Path:
    """诊断不存在的下载目录时，使用最近存在的父目录查询磁盘容量。"""
    current = path.expanduser()
    while not current.exists() and current.parent != current:
        current = current.parent

    return current


def main(argv: list[str] | None = None) -> int:
    """CLI 主函数：stdout 只输出单行 JSON，错误同样以 JSON 表示。"""
    parser = build_parser()

    try:
        args = parser.parse_args(argv)
        payload, status = dispatch(args)
    except CLIServiceError as error:
        payload, status = {"error": str(error)}, 2
    except Exception as error:
        # 不输出 traceback 到 stdout，避免 Agent 将半截堆栈当成可解析结果。
        payload, status = {"error": str(error), "type": type(error).__name__}, 1

    print(json.dumps(payload, ensure_ascii = False, separators = (",", ":")))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
