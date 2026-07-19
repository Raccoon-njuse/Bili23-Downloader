from ..common.io.directory import Directory
from ..common.enum import FFmpegSource
from ..common.config import config

from pathlib import Path
import logging
import shutil
import subprocess
import sys
import os

logger = logging.getLogger(__name__)

# 确定不同平台 FFmpeg 可执行文件名
if sys.platform == "win32":
    ffmpeg_executable = "ffmpeg.exe"

else:
    ffmpeg_executable = "ffmpeg"

def set_ffmpeg_environment(path: str | Path):
    """验证 FFmpeg 可实际运行后再加入 PATH，避免合并时才暴露损坏二进制。"""
    executable_path = Path(path)
    if not _is_runnable(executable_path):
        return False

    os.environ["PATH"] = str(executable_path.parent) + os.pathsep + os.environ["PATH"]

    logger.info(f"已将 FFmpeg 路径 {executable_path} 添加到环境变量")

    config.no_ffmpeg_available = False
    return True


def _is_runnable(path: Path) -> bool:
    """以无副作用的版本查询验证二进制，而不是只检查文件是否存在。"""
    try:
        result = subprocess.run(
            [str(path), "-hide_banner", "-version"],
            stdout = subprocess.DEVNULL,
            stderr = subprocess.PIPE,
            text = True,
            encoding = "utf-8",
            errors = "replace",
            timeout = 5,
            check = False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("FFmpeg 可执行文件无法启动：%s (%s)", path, error)
        return False

    if result.returncode == 0:
        return True

    logger.warning("FFmpeg 版本检查失败：%s (exit code %s)", path, result.returncode)
    return False

def try_system_ffmpeg():
    ffmpeg_path = shutil.which(ffmpeg_executable)

    if ffmpeg_path and set_ffmpeg_environment(ffmpeg_path):
        logger.info(f"环境变量中找到 FFmpeg 可执行文件：{ffmpeg_path}")
        return True
    
    logger.warning("环境变量中未找到 FFmpeg 可执行文件")
    return False

def try_bundled_ffmpeg():
    if config.bundle_ffmpeg_exist and set_ffmpeg_environment(bundle_ffmpeg_path):
        logger.info(f"找到附带的 FFmpeg 可执行文件：{bundle_ffmpeg_path}")
        return True
        
    logger.warning("没有找到附带的 FFmpeg 可执行文件")
    return False

def on_ffmpeg_not_found():
    logger.error("没有可用的 FFmpeg 可执行文件")
    config.no_ffmpeg_available = True
    return False

cwd = Directory.get_cwd()

config.ffmpeg_executable = ffmpeg_executable
bundle_ffmpeg_path = cwd / "bundle" / ffmpeg_executable
config.bundle_ffmpeg_exist = bundle_ffmpeg_path.exists()

match config.get(config.ffmpeg_source):
    case FFmpegSource.BUNDLED:
        if not try_bundled_ffmpeg():
            logger.warning("附带的 FFmpeg 不存在，将尝试使用环境变量中的 FFmpeg")
            
            if try_system_ffmpeg():
                # 自动回退只影响当前进程，避免播放器启动时改写原下载器的偏好。
                config.set(config.ffmpeg_source, FFmpegSource.SYSTEM, save = False)
            else:
                on_ffmpeg_not_found()
                
    case FFmpegSource.SYSTEM:
        if not try_system_ffmpeg():
            logger.warning("环境变量中无 FFmpeg，将尝试使用附带的 FFmpeg")
            
            if try_bundled_ffmpeg():
                config.set(config.ffmpeg_source, FFmpegSource.BUNDLED, save = False)
            else:
                on_ffmpeg_not_found()
            
    case FFmpegSource.CUSTOM:
        custom_ffmpeg_path = Path(config.get(config.custom_ffmpeg_path))

        if custom_ffmpeg_path.exists() and set_ffmpeg_environment(custom_ffmpeg_path):
            pass
        else:
            logger.warning(f"自定义 FFmpeg 路径无效：{custom_ffmpeg_path}，将尝试 fallback")

            if try_bundled_ffmpeg():
                config.set(config.ffmpeg_source, FFmpegSource.BUNDLED, save = False)

            elif try_system_ffmpeg():
                config.set(config.ffmpeg_source, FFmpegSource.SYSTEM, save = False)
                
            else:
                on_ffmpeg_not_found()
