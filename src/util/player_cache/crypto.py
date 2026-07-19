"""播放器缓存容器的轻量混淆与完整性校验。"""

from __future__ import annotations

from pathlib import Path

import hashlib
import hmac
import os
import secrets
from uuid import uuid4


MAGIC = b"B23CACH2"
NONCE_SIZE = 16
MAC_SIZE = 32
CHUNK_SIZE = 4 * 1024 * 1024
# 只变换媒体开头即可阻止 Finder/常规播放器把缓存当作可打开视频；其余数据顺序复制，
# 保证大文件的缓存命中不需要进行耗时的 Python 级全文件逐字节异或。
PROTECTED_PREFIX_SIZE = 1024 * 1024


class CacheIntegrityError(RuntimeError):
    """缓存容器格式错误或完整性校验失败。"""


class _KeyStream:
    """基于 BLAKE2b 派生的前缀掩码，用于隐藏媒体容器的识别头。"""

    def __init__(self, key: bytes, nonce: bytes):
        self.key = key
        self.nonce = nonce
        self.counter = 0
        self.buffer = b""

    def xor(self, data: bytes) -> bytes:
        output = bytearray(len(data))
        offset = 0

        while offset < len(data):
            if not self.buffer:
                self.buffer = hashlib.blake2b(
                    self.nonce + self.counter.to_bytes(8, "big"),
                    key = self.key,
                    digest_size = 64,
                ).digest()
                self.counter += 1

            size = min(len(self.buffer), len(data) - offset)
            for index in range(size):
                output[offset + index] = data[offset + index] ^ self.buffer[index]

            self.buffer = self.buffer[size:]
            offset += size

        return bytes(output)


def load_or_create_key(path: Path) -> bytes:
    """读取本机私钥；首次运行时以仅用户可读的权限创建。"""
    path.parent.mkdir(parents = True, exist_ok = True)

    if path.exists():
        key = path.read_bytes()
        if len(key) != 32:
            raise CacheIntegrityError("播放器缓存密钥格式无效。")
        return key

    key = secrets.token_bytes(32)
    descriptor = None
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as file:
            descriptor = None
            file.write(key)
            file.flush()
            os.fsync(file.fileno())
    except FileExistsError:
        return load_or_create_key(path)
    finally:
        if descriptor is not None:
            os.close(descriptor)

    if os.name != "nt":
        path.chmod(0o600)

    return key


def seal_file(source: Path, destination: Path, key: bytes) -> int:
    """封装媒体为不可直接打开的私有容器，返回容器字节数。"""
    _check_key(key)
    destination.parent.mkdir(parents = True, exist_ok = True)
    nonce = secrets.token_bytes(NONCE_SIZE)
    header = MAGIC + nonce
    mac = hmac.new(key, digestmod = hashlib.sha256)
    mac.update(header)
    stream = _KeyStream(key, nonce)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.part")

    try:
        with source.open("rb") as input_file, temporary.open("wb") as output_file:
            output_file.write(header)
            prefix = input_file.read(PROTECTED_PREFIX_SIZE)
            protected_prefix = stream.xor(prefix)
            mac.update(protected_prefix)
            output_file.write(protected_prefix)

            # 主体保持顺序复制，避免缓存命中时因纯 Python 算法造成长时间等待。
            while chunk := input_file.read(CHUNK_SIZE):
                mac.update(chunk)
                output_file.write(chunk)
            output_file.write(mac.digest())
            output_file.flush()
            os.fsync(output_file.fileno())

        if os.name != "nt":
            temporary.chmod(0o600)
        os.replace(temporary, destination)
        return destination.stat().st_size
    except Exception:
        temporary.unlink(missing_ok = True)
        raise


def restore_file(source: Path, destination: Path, key: bytes) -> int:
    """校验并还原缓存容器到短暂播放文件，返回明文字节数。"""
    _check_key(key)
    file_size = source.stat().st_size
    header_size = len(MAGIC) + NONCE_SIZE
    if file_size < header_size + MAC_SIZE:
        raise CacheIntegrityError("缓存文件不完整。")

    destination.parent.mkdir(parents = True, exist_ok = True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.part")

    try:
        with source.open("rb") as input_file, temporary.open("wb") as output_file:
            header = input_file.read(header_size)
            if not header.startswith(MAGIC):
                raise CacheIntegrityError("不是可识别的播放器缓存文件。")

            nonce = header[len(MAGIC):]
            mac = hmac.new(key, digestmod = hashlib.sha256)
            mac.update(header)
            stream = _KeyStream(key, nonce)
            remaining = file_size - header_size - MAC_SIZE

            protected_size = min(PROTECTED_PREFIX_SIZE, remaining)
            protected_prefix = input_file.read(protected_size)
            if len(protected_prefix) != protected_size:
                raise CacheIntegrityError("缓存文件读取提前结束。")
            mac.update(protected_prefix)
            output_file.write(stream.xor(protected_prefix))
            remaining -= protected_size

            while remaining > 0:
                chunk = input_file.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    raise CacheIntegrityError("缓存文件读取提前结束。")
                mac.update(chunk)
                output_file.write(chunk)
                remaining -= len(chunk)

            expected_mac = input_file.read(MAC_SIZE)
            if not hmac.compare_digest(mac.digest(), expected_mac):
                raise CacheIntegrityError("缓存文件完整性校验失败。")

            output_file.flush()
            os.fsync(output_file.fileno())

        if os.name != "nt":
            temporary.chmod(0o600)
        os.replace(temporary, destination)
        return destination.stat().st_size
    except Exception:
        temporary.unlink(missing_ok = True)
        raise


def _check_key(key: bytes) -> None:
    if len(key) != 32:
        raise CacheIntegrityError("播放器缓存密钥长度无效。")
