# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import shutil
import os
from pathlib import Path

from iotaxmedia import logger


def ensure_dirs():
    """
    Ensure that the necessary directories exist.
    """

    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        logger.info("Added static_ffmpeg binaries to PATH.")
    except ImportError:
        logger.warning("static_ffmpeg not installed; using system binaries.")

    for dir in ["cache", "downloads"]:
        Path(dir).mkdir(parents=True, exist_ok=True)
    logger.info("Cache directories updated.")
