"""将既有登录、解析和媒体信息能力转换为可供 CLI 调用的同步服务。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode
import sqlite3

from PySide6.QtCore import QObject, Slot

from util.common.config import appdata_path, config
from util.common.data import (
    reversed_audio_quality_map,
    reversed_video_codec_map,
    reversed_video_quality_map,
)
from util.common.enum import DownloadStatus, MediaType
from util.common.signal_bus import signal_bus
from util.network.request import SyncNetWorkRequest
from util.parse.episode.tree import Attribute, EpisodeData, TreeItem
from util.parse.parser.base import ParserBase
from util.parse.worker import WorkerBase


class CLIServiceError(RuntimeError):
    """表示可以直接返回给 CLI 调用方的业务错误。"""


VIDEO_QUALITY_ALIASES = {
    "AUTO": 200,
    "8K": 127,
    "4320": 127,
    "DOLBYVISION": 126,
    "HDR": 125,
    "4K": 120,
    "2160": 120,
    "1080P60": 116,
    "1080P+": 112,
    "1080PPLUS": 112,
    "1080": 80,
    "1080P": 80,
    "AI": 100,
    "720": 64,
    "720P": 64,
    "480": 32,
    "480P": 32,
    "360": 16,
    "360P": 16,
}

AUDIO_QUALITY_ALIASES = {
    "AUTO": 30300,
    "HIRES": 30251,
    "DOLBY": 30250,
    "DOLBYATMOS": 30250,
    "192K": 30280,
    "192": 30280,
    "132K": 30232,
    "132": 30232,
    "64K": 30216,
    "64": 30216,
}

VIDEO_CODEC_ALIASES = {
    "AUTO": 20,
    "H264": 7,
    "AVC": 7,
    "AVC/H264": 7,
    "H265": 12,
    "HEVC": 12,
    "AV1": 13,
}


@dataclass
class ParsedContent:
    """一次 URL 解析的树、分页信息和默认选中项。"""

    original_url: str
    resolved_url: str
    category: str
    title: str
    root: TreeItem
    current_episode_data: tuple[str, Any] | None
    extra_data: dict[str, Any]

    def leaves(self) -> list[dict[str, Any]]:
        """返回可下载的叶子节点，保持下载管理器需要的原始字段。"""
        return self.root.get_all_children(to_dict = True)

    def to_public_dict(self) -> dict[str, Any]:
        """转换成不包含内部对象和登录凭据的 JSON 结构。"""
        return {
            "original_url": self.original_url,
            "resolved_url": self.resolved_url,
            "category": self.category,
            "title": self.title,
            "episodes": [episode_to_public(item, index + 1) for index, item in enumerate(self.leaves())],
            "extra": self.extra_data,
        }


class _ParseCollector(QObject):
    """捕获原 GUI 解析器通过 signal bus 发送的同步解析结果。"""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.category = ""
        self.root: TreeItem | None = None
        self.current_episode_data: tuple[str, Any] | None = None
        self.redirect_url = ""

        signal_bus.parse.update_parse_list.connect(self._on_update_parse_list)
        signal_bus.parse.parse_url.connect(self._on_redirect)

    @Slot(str, str, object, object)
    def _on_update_parse_list(self, title: str, category: str, root: TreeItem, current_episode_data: object):
        self.title = title
        self.category = category
        self.root = root

        if isinstance(current_episode_data, tuple) and len(current_episode_data) == 2:
            self.current_episode_data = current_episode_data

    @Slot(str)
    def _on_redirect(self, url: str):
        self.redirect_url = url

    def close(self):
        """避免一次 CLI 调用内的临时 collector 残留信号连接。"""
        for signal, slot in (
            (signal_bus.parse.update_parse_list, self._on_update_parse_list),
            (signal_bus.parse.parse_url, self._on_redirect),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass


class Bili23CLIService:
    """复用 Bili23 Downloader 现有 API/解析逻辑的无界面服务。"""

    def auth_status(self, require_login: bool = False) -> dict[str, Any]:
        """刷新运行时用户资料，并只返回可公开给本地 Agent 的账户摘要。"""
        response = self._request_json("https://api.bilibili.com/x/web-interface/nav")
        data = response.get("data") or {}
        is_logged_in = bool(data.get("isLogin"))

        # WBI 签名密钥和用户 ID 只保存在当前进程内存，避免 CLI 重新写入配置文件。
        wbi_img = data.get("wbi_img") or {}
        img_url = wbi_img.get("img_url", "")
        sub_url = wbi_img.get("sub_url", "")

        if img_url:
            config.set(config.img_key, Path(img_url).stem, save = False)
        if sub_url:
            config.set(config.sub_key, Path(sub_url).stem, save = False)

        if is_logged_in:
            config.user_uid = data.get("mid", "")
            config.user_uname = data.get("uname", "")

        result = {
            "is_logged_in": is_logged_in,
            "user": {
                "uid": data.get("mid") if is_logged_in else None,
                "name": data.get("uname") if is_logged_in else None,
                "level": (data.get("level_info") or {}).get("current_level") if is_logged_in else None,
            },
        }

        if require_login and not is_logged_in:
            raise CLIServiceError("当前登录态无效，请先在 Bili23 Downloader 图形界面扫码登录。")

        return result

    def list_favorites(self, include_collected: bool = False) -> dict[str, Any]:
        """获取当前账户创建的收藏夹，可选合并已收藏的他人收藏夹。"""
        status = self.auth_status(require_login = True)
        uid = status["user"]["uid"]

        created_response = self._request_json(
            f"https://api.bilibili.com/x/v3/fav/folder/created/list-all?up_mid={uid}"
        )
        created = [self._favorite_to_public(item, "created") for item in (created_response.get("data") or {}).get("list", [])]

        result: dict[str, Any] = {"created": created}

        if include_collected:
            params = {
                "pn": 1,
                "ps": 50,
                "up_mid": uid,
                "platform": "web",
                "web_location": "333.1387",
            }
            collected_response = self._request_json(
                f"https://api.bilibili.com/x/v3/fav/folder/collected/list?{urlencode(params)}"
            )
            result["collected"] = [
                self._favorite_to_public(item, "collected")
                for item in (collected_response.get("data") or {}).get("list", [])
            ]

        return result

    def parse_url(self, url: str, page: int = 1) -> ParsedContent:
        """用原项目的解析器同步解析链接，并捕获它生成的剧集树。"""
        self.auth_status(require_login = False)
        EpisodeData.clear_cache()

        original_url = url.strip()
        if not original_url:
            raise CLIServiceError("链接不能为空。")

        current_url = original_url
        worker = WorkerBase()

        # 投稿重定向最多跟随三次，避免异常链接造成 CLI 无限循环。
        for _ in range(3):
            parser_type = worker.get_parser_type(current_url)
            current_url = self._resolve_special_url(parser_type, current_url)
            parser_type = worker.get_parser_type(current_url)

            collector = _ParseCollector()
            try:
                parser = worker.get_parser(parser_type)
                parser.parse(current_url, page)

                if collector.redirect_url:
                    current_url = collector.redirect_url
                    continue

                if collector.root is None:
                    raise CLIServiceError("该链接没有生成可下载的剧集列表，可能是互动视频或不受支持的内容类型。")

                return ParsedContent(
                    original_url = original_url,
                    resolved_url = current_url,
                    category = collector.category,
                    title = collector.title,
                    root = collector.root,
                    current_episode_data = collector.current_episode_data,
                    extra_data = parser.get_extra_data(),
                )
            finally:
                collector.close()

        raise CLIServiceError("链接重定向次数过多，无法确定最终内容。")

    def select_episodes(
        self,
        parsed: ParsedContent,
        *,
        episode: int | None = None,
        part: int | None = None,
        ep_id: int | None = None,
        cid: int | None = None,
        title_contains: str | None = None,
        select_all: bool = False,
    ) -> list[dict[str, Any]]:
        """按 UI 可见的剧集、分 P、ID 或标题筛选可下载叶子节点。"""
        items = parsed.leaves()

        if not items:
            raise CLIServiceError("没有可下载的剧集。")

        if title_contains is not None:
            title_contains = title_contains.strip()
            if not title_contains:
                raise CLIServiceError("--match 不能为空；请传入要匹配的标题文本。")

        has_specific_selector = any(value is not None for value in (episode, part, ep_id, cid, title_contains))
        if select_all:
            if has_specific_selector:
                raise CLIServiceError("--all 不能与 --episode、--part、--ep-id、--cid 或 --match 同时使用。")
            return items

        if not has_specific_selector:
            current = self._select_current_episode(parsed, items)
            if current is not None:
                return [current]

            if len(items) == 1:
                return items

            raise CLIServiceError(
                f"解析到 {len(items)} 个可下载项。请通过 --episode、--part、--ep-id、--cid 或 --match 指定目标。"
            )

        selected = list(items)

        if episode is not None:
            selected = [
                item for item in selected
                if item.get("episode_number") == episode or str(item.get("number", "")) == str(episode)
            ]

        if part is not None:
            selected = [item for item in selected if item.get("part_number") == part]

        if ep_id is not None:
            selected = [item for item in selected if item.get("ep_id") == ep_id]

        if cid is not None:
            selected = [item for item in selected if item.get("cid") == cid]

        if title_contains:
            keyword = title_contains.casefold()
            selected = [item for item in selected if keyword in item.get("title", "").casefold()]

        if not selected:
            raise CLIServiceError("没有找到匹配的剧集，请先使用 inspect 查看可用 selector。")

        return selected

    def media_options(self, episode: dict[str, Any]) -> dict[str, Any]:
        """读取一集视频允许的清晰度、视频编码和音频质量。"""
        info_data, media_type = self._get_media_info(episode, quality_id = 80)

        video_streams = info_data.get("dash", {}).get("video", [])
        quality_ids = info_data.get("accept_quality") or [entry.get("id") for entry in video_streams]
        quality_ids = [quality_id for quality_id in quality_ids if isinstance(quality_id, int)]
        codecs_by_quality: dict[int, list[int]] = {}

        for stream in video_streams:
            quality_id = stream.get("id")
            codec_id = stream.get("codecid")
            if isinstance(quality_id, int):
                codecs_by_quality.setdefault(quality_id, [])
                if isinstance(codec_id, int) and codec_id not in codecs_by_quality[quality_id]:
                    codecs_by_quality[quality_id].append(codec_id)

        video_qualities = [
            {
                "id": quality_id,
                "label": quality_label(quality_id),
                "codecs": [
                    {"id": codec_id, "label": codec_label(codec_id)}
                    for codec_id in codecs_by_quality.get(quality_id, [])
                ],
            }
            for quality_id in quality_ids
        ]

        audio_qualities = []
        dash = info_data.get("dash") or {}
        for stream in dash.get("audio", []):
            quality_id = stream.get("id")
            if isinstance(quality_id, int) and not any(entry["id"] == quality_id for entry in audio_qualities):
                audio_qualities.append({"id": quality_id, "label": audio_quality_label(quality_id)})

        if dash.get("flac", {}).get("audio"):
            audio_qualities.append({"id": 30251, "label": audio_quality_label(30251)})
        if dash.get("dolby", {}).get("audio"):
            audio_qualities.append({"id": 30250, "label": audio_quality_label(30250)})

        # 旧 MP4/FLV 流已含音轨，不会返回独立 DASH audio 节点。
        return {
            "media_type": media_type.name.lower(),
            "available_video_qualities": video_qualities,
            "available_audio_qualities": audio_qualities,
        }

    def validate_download_plan(
        self,
        episodes: Iterable[dict[str, Any]],
        video_quality_id: int,
        audio_quality_id: int,
    ) -> list[dict[str, Any]]:
        """在入队前校验请求质量，并返回 Agent 可审阅的下载计划。"""
        plan = []

        for index, episode in enumerate(episodes, start = 1):
            media = self.media_options(episode)
            available_video_ids = {entry["id"] for entry in media["available_video_qualities"]}
            available_audio_ids = {entry["id"] for entry in media["available_audio_qualities"]}

            if video_quality_id != 200 and available_video_ids and video_quality_id not in available_video_ids:
                raise CLIServiceError(
                    f"{episode.get('title', '')} 不支持 {quality_label(video_quality_id)}，"
                    f"可用清晰度为：{', '.join(quality_label(item) for item in sorted(available_video_ids, reverse = True))}。"
                )

            if audio_quality_id != 30300 and available_audio_ids and audio_quality_id not in available_audio_ids:
                raise CLIServiceError(
                    f"{episode.get('title', '')} 不支持 {audio_quality_label(audio_quality_id)} 音频。"
                )

            plan.append({
                "index": index,
                "episode": episode_to_public(episode, index),
                "requested_video_quality": {"id": video_quality_id, "label": quality_label(video_quality_id)},
                "requested_audio_quality": {"id": audio_quality_id, "label": audio_quality_label(audio_quality_id)},
                "media": media,
            })

        return plan

    def list_tasks(self, completed: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
        """读取下载列表或已完成列表，复用桌面端相同的任务数据库。"""
        from util.common._json import json_loads
        from util.download.task.info import TaskInfo

        # 只读 URI 避免 TaskDatabase 构造器执行建表/WAL 初始化，从而保证查询没有写入副作用。
        database_path = Path(appdata_path) / "Bili23 Downloader" / "task.db"
        if not database_path.exists():
            return []

        table_name = "completed_task" if completed else "download_task"
        tasks = []
        try:
            with sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri = True) as connection:
                for entry in connection.execute(f"SELECT data FROM {table_name}"):
                    task = TaskInfo()
                    task.from_dict(json_loads(entry[0]))
                    tasks.append(task)
        except sqlite3.Error as error:
            raise CLIServiceError(f"无法读取任务数据库：{error}") from error

        tasks.sort(key = lambda item: item.Basic.completed_time if completed else item.Basic.created_time, reverse = True)

        if limit is not None:
            tasks = tasks[:limit]

        return [task_to_public(task) for task in tasks]

    def _request_json(self, url: str) -> dict[str, Any]:
        response = SyncNetWorkRequest(url).run()

        if response.get("code", 0) != 0:
            message = response.get("message", "Bilibili 接口返回异常")
            raise CLIServiceError(message)

        return response

    def _resolve_special_url(self, parser_type: str, url: str) -> str:
        """复用 GUI ParseWorker 对短链和节日页的预处理规则。"""
        if parser_type == "b23":
            from util.parse.parser.b23 import B23Parser
            return B23Parser().parse(url)

        if parser_type == "festival":
            from util.parse.parser.festival import FestivalParser
            return FestivalParser().parse(url)

        return url

    def _select_current_episode(self, parsed: ParsedContent, items: list[dict[str, Any]]) -> dict[str, Any] | None:
        if parsed.current_episode_data is None:
            return None

        key, value = parsed.current_episode_data
        return next((item for item in items if item.get(key) == value), None)

    def _get_media_info(self, episode: dict[str, Any], quality_id: int) -> tuple[dict[str, Any], MediaType]:
        """同步执行下载器使用的 playurl 请求，且不生成下载任务。"""
        attribute = Attribute(episode.get("attribute", 0))
        parser = ParserBase()

        if attribute & Attribute.VIDEO_BIT:
            params = {
                "bvid": episode["bvid"],
                "cid": episode["cid"],
                "qn": quality_id,
                "fnver": 0,
                "fnval": 4048,
                "fourk": 1,
            }
            response = self._request_json(
                f"https://api.bilibili.com/x/player/wbi/playurl?{parser.enc_wbi(params)}"
            )
            info_data = response.get("data") or {}
        elif attribute & Attribute.BANGUMI_BIT:
            params = {
                "bvid": episode["bvid"],
                "cid": episode["cid"],
                "qn": quality_id,
                "fnver": 0,
                "fnval": 12240,
                "fourk": 1,
            }
            response = self._request_json(
                f"https://api.bilibili.com/pgc/player/web/playurl?{urlencode(params)}"
            )
            info_data = response.get("result") or {}
        elif attribute & Attribute.CHEESE_BIT:
            params = {
                "avid": episode["aid"],
                "cid": episode["cid"],
                "qn": quality_id,
                "fnver": 0,
                "fnval": 16,
                "fourk": 1,
                "ep_id": episode["ep_id"],
            }
            response = self._request_json(
                f"https://api.bilibili.com/pugv/player/web/playurl?{urlencode(params)}"
            )
            info_data = response.get("data") or {}
        elif attribute & Attribute.AUDIO_BIT:
            params = {"sid": episode["sid"], "privilege": 2, "quality": 2}
            response = self._request_json(
                f"https://www.bilibili.com/audio/music-service-c/web/url?{urlencode(params)}"
            )
            info_data = response.get("data") or {}
            info_data["format"] = "m4a"
        else:
            raise CLIServiceError("该项目仍需要二次解析，请先使用它自身的视频或剧集链接再次执行 inspect。")

        if info_data.get("is_drm"):
            raise CLIServiceError("该媒体受 DRM 保护，项目原有下载器也不支持下载。")

        if "dash" in info_data:
            media_type = MediaType.DASH
        elif str(info_data.get("format", "")).startswith("mp4"):
            media_type = MediaType.MP4
        elif str(info_data.get("format", "")).startswith("flv"):
            media_type = MediaType.FLV
        elif str(info_data.get("format", "")).startswith("m4a"):
            media_type = MediaType.M4A
        else:
            media_type = MediaType.UNKNOWN

        return info_data, media_type

    def _favorite_to_public(self, item: dict[str, Any], source: str) -> dict[str, Any]:
        media_id = item.get("id", "")
        mid = item.get("mid", "")
        return {
            "id": media_id,
            "title": item.get("title", ""),
            "count": item.get("media_count", 0),
            "source": source,
            "url": f"https://space.bilibili.com/{mid}/favlist?fid={media_id}",
        }


def parse_video_quality(value: str | int) -> int:
    """把 Agent 友好的清晰度别名规范化为 Bilibili quality ID。"""
    raw = str(value).strip()
    normalized = raw.upper().replace(" ", "").replace("_", "").replace(".", "")

    if normalized in VIDEO_QUALITY_ALIASES:
        return VIDEO_QUALITY_ALIASES[normalized]
    if raw.isdigit() and int(raw) in reversed_video_quality_map:
        return int(raw)

    raise CLIServiceError(f"未知视频清晰度：{value}。可用示例：720p、1080p、4k、auto。")


def parse_audio_quality(value: str | int) -> int:
    """把音频质量别名规范化为下载器使用的 quality ID。"""
    raw = str(value).strip()
    normalized = raw.upper().replace(" ", "").replace("_", "")

    if normalized in AUDIO_QUALITY_ALIASES:
        return AUDIO_QUALITY_ALIASES[normalized]
    if raw.isdigit() and int(raw) in reversed_audio_quality_map:
        return int(raw)

    raise CLIServiceError(f"未知音频质量：{value}。可用示例：192k、132k、64k、auto。")


def parse_video_codec(value: str | int) -> int:
    """把常见视频编码别名规范化为项目既有 codec ID。"""
    raw = str(value).strip()
    normalized = raw.upper().replace(" ", "").replace("_", "").replace(".", "")

    if normalized in VIDEO_CODEC_ALIASES:
        return VIDEO_CODEC_ALIASES[normalized]
    if raw.isdigit() and int(raw) in reversed_video_codec_map:
        return int(raw)

    raise CLIServiceError(f"未知视频编码：{value}。可用示例：h264、h265、av1、auto。")


def quality_label(quality_id: int) -> str:
    """返回稳定、可读的质量标签，不依赖 GUI 翻译对象。"""
    return reversed_video_quality_map.get(quality_id, str(quality_id))


def audio_quality_label(quality_id: int) -> str:
    """返回稳定、可读的音频质量标签。"""
    return reversed_audio_quality_map.get(quality_id, str(quality_id))


def codec_label(codec_id: int) -> str:
    """返回稳定、可读的视频编码标签。"""
    return reversed_video_codec_map.get(codec_id, str(codec_id))


def episode_to_public(item: dict[str, Any], index: int) -> dict[str, Any]:
    """从下载器叶节点提取 Agent 选择剧集所需的字段。"""
    attribute = Attribute(item.get("attribute", 0))
    kind = "video"
    if attribute & Attribute.BANGUMI_BIT:
        kind = "bangumi"
    elif attribute & Attribute.CHEESE_BIT:
        kind = "cheese"
    elif attribute & Attribute.AUDIO_BIT:
        kind = "audio"

    selectors = {
        "episode": item.get("episode_number") or None,
        "part": item.get("part_number") or None,
        "ep_id": item.get("ep_id") or None,
        "cid": item.get("cid") or None,
    }

    return {
        "index": index,
        "kind": kind,
        "title": item.get("title", ""),
        "number": item.get("number", ""),
        "badge": item.get("badge", ""),
        "duration_seconds": item.get("duration", 0),
        "url": item.get("url", ""),
        "selectors": selectors,
    }


def task_to_public(task) -> dict[str, Any]:
    """把任务数据库记录转换为不会暴露 Cookie 的状态摘要。"""
    try:
        status_name = DownloadStatus(task.Download.status).name.lower()
    except ValueError:
        status_name = str(task.Download.status)

    output_dir = Path(task.File.download_path, task.File.folder)
    return {
        "id": task.Basic.task_id,
        "title": task.Basic.show_title,
        "status": status_name,
        "progress": task.Download.progress,
        "video_quality": quality_label(task.Download.video_quality_id),
        "audio_quality": audio_quality_label(task.Download.audio_quality_id),
        "output_dir": str(output_dir),
        "files": list(task.File.relative_files),
        "created_time": task.Basic.created_time,
        "completed_time": task.Basic.completed_time,
    }


def cli_runtime_paths() -> dict[str, str]:
    """返回诊断所需的非敏感本地路径。"""
    return {
        "appdata": str(Path(appdata_path) / "Bili23 Downloader"),
        "download_path": str(config.get(config.download_path)),
    }
