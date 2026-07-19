"""播放器私有缓存的纯文件系统测试，不访问网络或真实登录态。"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from util.player_cache.crypto import CacheIntegrityError, load_or_create_key, restore_file, seal_file
from util.player_cache.paths import CachePaths
from util.player_cache.store import CacheStore
from util.download.task import db as task_db
from util.parse.worker import ParseWorker


def make_task(paths: CachePaths, content: bytes):
    """构造下载器完成后的最小任务对象，覆盖缓存入库路径。"""
    task_id = "task-001"
    work_dir = paths.work_root / task_id
    work_dir.mkdir(parents = True, exist_ok = True)
    (work_dir / "payload.mp4").write_bytes(content)

    return SimpleNamespace(
        Basic = SimpleNamespace(task_id = task_id, show_title = "Cache fixture"),
        File = SimpleNamespace(
            download_path = str(paths.work_root),
            folder = task_id,
            relative_files = ["payload.mp4"],
        ),
        Episode = SimpleNamespace(
            attribute = 1,
            bvid = "BV1fixture",
            aid = 1,
            cid = 2,
            ep_id = 0,
            sid = 0,
            duration = 42,
        ),
    )


class PlayerCacheTest(unittest.TestCase):
    """验证私有缓存容器、临时明文和缓存历史的基本约束。"""

    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.paths = CachePaths(Path(self.temporary_directory.name) / "cache")
        self.store = CacheStore(self.paths)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_private_container_is_not_plain_mp4_and_round_trips(self):
        source = self.paths.root / "source.mp4"
        encrypted = self.paths.media_root / "entry.b23c"
        restored = self.paths.root / "restored.mp4"
        content = b"\x00\x00\x00\x18ftypmp42" + b"media-data" * 4096
        source.write_bytes(content)
        key = load_or_create_key(self.paths.key_path)

        seal_file(source, encrypted, key)

        self.assertNotEqual(encrypted.read_bytes()[:12], content[:12])
        self.assertEqual(encrypted.suffix, ".b23c")

        restore_file(encrypted, restored, key)
        self.assertEqual(restored.read_bytes(), content)

    def test_tampered_container_is_rejected(self):
        source = self.paths.root / "source.mp4"
        encrypted = self.paths.media_root / "entry.b23c"
        restored = self.paths.root / "restored.mp4"
        source.write_bytes(b"video" * 4096)
        key = load_or_create_key(self.paths.key_path)
        seal_file(source, encrypted, key)

        payload = bytearray(encrypted.read_bytes())
        # 篡改容器主体而非尾部校验值，确认完整性校验覆盖了全部媒体数据。
        payload[len(b"B23CACH2") + 16 + 128] ^= 0xFF
        encrypted.write_bytes(payload)

        with self.assertRaises(CacheIntegrityError):
            restore_file(encrypted, restored, key)
        self.assertFalse(restored.exists())

    def test_large_container_round_trips_across_copy_chunks(self):
        """媒体主体跨多个分块时仍可快速顺序封装和还原。"""
        source = self.paths.root / "large-source.mp4"
        encrypted = self.paths.media_root / "large-entry.b23c"
        restored = self.paths.root / "large-restored.mp4"
        content = b"\x00\x00\x00\x18ftypmp42" + b"large-media-block" * (400 * 1024)
        source.write_bytes(content)
        key = load_or_create_key(self.paths.key_path)

        seal_file(source, encrypted, key)
        restore_file(encrypted, restored, key)

        self.assertEqual(restored.read_bytes(), content)

    def test_sealed_cache_keeps_history_and_removes_plain_work_file(self):
        content = b"\x00\x00\x00\x18ftypmp42" + b"cached-media" * 1024
        task = make_task(self.paths, content)

        entry = self.store.seal_task(task, owner_uid = "10001")

        self.assertFalse((self.paths.work_root / task.Basic.task_id).exists())
        self.assertTrue(self.store.media_path(entry).is_file())
        self.assertEqual(self.store.list_entries("10001"), [entry])
        self.assertEqual(self.store.list_entries("20002"), [])

        playback_path = self.store.decrypt_for_playback(entry)
        self.assertTrue(playback_path.name.startswith("."))
        self.assertEqual(playback_path.read_bytes(), content)
        self.store.release_playback(playback_path)
        self.assertFalse(playback_path.exists())

        self.assertEqual(self.store.clear_entries("10001"), 1)
        self.assertEqual(self.store.list_entries("10001"), [])
        self.assertFalse(self.store.media_path(entry).exists())

    def test_runtime_cleanup_removes_plaintext_and_incomplete_container(self):
        """异常退出后，下次启动不得遗留可直接打开的临时媒体。"""
        playback_file = self.paths.playback_root / ".interrupted.mp4"
        incomplete_container = self.paths.media_root / ".entry.b23c.fixture.part"
        playback_file.write_bytes(b"temporary plaintext")
        incomplete_container.write_bytes(b"incomplete encrypted cache")

        self.store.cleanup_stale_playback()

        self.assertFalse(playback_file.exists())
        self.assertFalse(incomplete_container.exists())

    def test_discard_task_work_refuses_to_remove_cache_root(self):
        """失败清理只能删除任务子目录，不能误删整个缓存工作区。"""
        task = make_task(self.paths, b"temporary media")

        self.store.discard_task_work(task)

        self.assertFalse((self.paths.work_root / task.Basic.task_id).exists())
        self.assertTrue(self.paths.work_root.is_dir())

        root_task = SimpleNamespace(
            File = SimpleNamespace(download_path = str(self.paths.work_root), folder = ""),
        )
        with self.assertRaises(RuntimeError):
            self.store.discard_task_work(root_task)

    def test_task_database_isolated_from_downloader_history(self):
        """播放器任务数据库必须与原下载器的历史数据库隔离。"""
        original_appdata_path = task_db.appdata_path
        task_db.appdata_path = self.paths.root

        try:
            database = task_db.TaskDatabase()
            self.assertEqual(database.path, self.paths.root / "Bili23 Player" / "task.db")
            self.assertTrue(database.path.is_file())
        finally:
            task_db.appdata_path = original_appdata_path


class PlayerParsingGuardTest(unittest.TestCase):
    """验证短链重定向后仍不会进入账号个性化页面。"""

    def test_redirected_personal_page_is_rejected(self):
        worker = ParseWorker("https://example.invalid", allowed_parser_types = {"video", "bangumi"})
        worker.parser_type = "favlist"

        with self.assertRaises(ValueError):
            worker.validate_parser_type()


if __name__ == "__main__":
    unittest.main()
