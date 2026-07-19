"""CLI 纯业务逻辑测试，不访问网络、不读取真实登录态。"""

from __future__ import annotations

import unittest

from cli.service import (
    Bili23CLIService,
    CLIServiceError,
    ParsedContent,
    parse_audio_quality,
    parse_video_codec,
    parse_video_quality,
)
from util.parse.episode.tree import Attribute, TreeItem


def make_episode(**overrides):
    """构造最小下载器叶子节点，覆盖剧集选择路径。"""
    data = {
        "attribute": int(Attribute.BANGUMI_BIT),
        "title": "第 1 集",
        "number": "1",
        "episode_number": 1,
        "ep_id": 1001,
        "cid": 2001,
        "bvid": "BV1test",
        "duration": 600,
        "url": "https://www.bilibili.com/bangumi/play/ep1001",
    }
    data.update(overrides)
    return TreeItem(data)


class CLIServiceTest(unittest.TestCase):
    """验证 selector 与质量别名，防止 Agent 误选整季内容。"""

    def setUp(self):
        root = TreeItem({})
        root.add_child(make_episode())
        root.add_child(make_episode(title = "第 27 集", number = "27", episode_number = 27, ep_id = 1027, cid = 2027))
        self.parsed = ParsedContent(
            original_url = "https://example.invalid/ss1",
            resolved_url = "https://example.invalid/ss1",
            category = "ANIME",
            title = "测试番剧",
            root = root,
            current_episode_data = None,
            extra_data = {},
        )
        self.service = Bili23CLIService()

    def test_selects_requested_episode_number(self):
        selected = self.service.select_episodes(self.parsed, episode = 27)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["ep_id"], 1027)

    def test_requires_selector_for_multi_episode_content(self):
        with self.assertRaises(CLIServiceError):
            self.service.select_episodes(self.parsed)

    def test_current_episode_is_used_when_present(self):
        self.parsed.current_episode_data = ("ep_id", 1027)
        selected = self.service.select_episodes(self.parsed)
        self.assertEqual(selected[0]["cid"], 2027)

    def test_all_cannot_override_a_specific_selector(self):
        with self.assertRaises(CLIServiceError):
            self.service.select_episodes(self.parsed, episode = 27, select_all = True)

    def test_blank_match_is_rejected_instead_of_selecting_everything(self):
        with self.assertRaises(CLIServiceError):
            self.service.select_episodes(self.parsed, title_contains = "   ")

    def test_quality_aliases_are_stable(self):
        self.assertEqual(parse_video_quality("720p"), 64)
        self.assertEqual(parse_video_quality("4k"), 120)
        self.assertEqual(parse_audio_quality("192k"), 30280)
        self.assertEqual(parse_video_codec("h264"), 7)
        self.assertEqual(parse_video_codec("H.265"), 12)

    def test_unknown_quality_is_rejected(self):
        with self.assertRaises(CLIServiceError):
            parse_video_quality("1440p")


if __name__ == "__main__":
    unittest.main()
