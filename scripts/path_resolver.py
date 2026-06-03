#!/usr/bin/env python3
"""
path_resolver.py — Flexible Path Resolver v0.4.5

Problem: v0.4.0 hardcodes novels_root/slug/第NN卷/ structure, forcing
users to maintain parallel directory trees.

Solution: Support custom templates via config.json paths section.
Default layout stays compatible (slug_volume). Custom layout supports
{novel_title}, {volume_no_cn}, {volume_title}, {chapter_no}, {safe_title}.
"""

import json
from pathlib import Path
from typing import Optional


# Map digits to Chinese numerals for volume numbers
_CN_NUM = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def to_chinese_num(n: int) -> str:
    """Convert integer to Chinese numeral (1-99)."""
    if n <= 10:
        return _CN_NUM[n]
    elif n < 20:
        return f"十{_CN_NUM[n - 10]}"
    else:
        tens = n // 10
        ones = n % 10
        if ones == 0:
            return f"{_CN_NUM[tens]}十"
        return f"{_CN_NUM[tens]}十{_CN_NUM[ones]}"


def safe_filename(title: str) -> str:
    """Strip punctuation from title for safe filenames."""
    import re
    # Remove Chinese/English punctuation but keep Chinese chars and alphanumeric
    safe = re.sub(r'[，、。！？：；""''「」『』【】《》（）\s,.!?:;"\'()\[\]<>]',
                  '', title)
    return safe


class PathResolver:
    """
    Resolve chapter file paths based on configured templates.

    config.json example:
    {
      "paths": {
        "layout": "custom",
        "novels_root": "D:/小说",
        "novel_dir_template": "{novel_title}",
        "volume_dir_template": "第{volume_no_cn}卷_{volume_title}",
        "chapter_filename_template": "第{chapter_no}章_{safe_title}.txt"
      }
    }

    Default (layout: "slug_volume"):
      novels_root / novel_slug / 第NN卷 / 第N章_title.txt
    """

    def __init__(self, config: dict = None):
        config = config or {}
        paths_cfg = config.get("paths", {})

        self.layout = paths_cfg.get("layout", "slug_volume")
        self.novels_root = Path(paths_cfg.get("novels_root",
                                config.get("novels_root", "./novels")))
        self.novel_title = config.get("default_novel_title", "")
        self.novel_slug = config.get("default_novel_slug", "")

        # Templates
        self.novel_dir_template = paths_cfg.get("novel_dir_template",
                                                 "{novel_slug}")
        self.volume_dir_template = paths_cfg.get("volume_dir_template",
                                                  "第{volume_no:02d}卷")
        self.chapter_filename_template = paths_cfg.get("chapter_filename_template",
                                                        "第{chapter_no}章_{safe_title}.txt")

    def novel_dir(self) -> Path:
        """Get the novel root directory."""
        if self.layout == "slug_volume":
            return self.novels_root / self.novel_slug
        else:
            name = self.novel_dir_template.format(
                novel_title=self.novel_title,
                novel_slug=self.novel_slug)
            return self.novels_root / name

    def volume_dir(self, volume_no: int, volume_title: str = "") -> Path:
        """Get the volume directory."""
        if self.layout == "slug_volume":
            return self.novel_dir() / f"第{volume_no:02d}卷"

        return self.novel_dir() / self.volume_dir_template.format(
            volume_no=volume_no,
            volume_no_cn=to_chinese_num(volume_no),
            volume_title=volume_title,
            novel_title=self.novel_title,
            novel_slug=self.novel_slug)

    def chapter_path(self, chapter_no: int, title: str = "",
                     volume_no: int = 1, volume_title: str = "") -> Path:
        """Get the full path to a chapter TXT file."""
        safe_title = safe_filename(title) if title else f"第{chapter_no}章"
        filename = self.chapter_filename_template.format(
            chapter_no=chapter_no,
            safe_title=safe_title,
            title=title,
            volume_no=volume_no,
            volume_no_cn=to_chinese_num(volume_no),
            volume_title=volume_title)
        return self.volume_dir(volume_no, volume_title) / filename

    def find_chapter(self, chapter_no: int,
                     volume_no: int = None,
                     volume_title: str = "") -> Optional[Path]:
        """
        Find a chapter file by chapter number.
        If volume_no is None, searches all volume dirs.
        """
        if volume_no is not None:
            vol_dir = self.volume_dir(volume_no, volume_title)
            if vol_dir.exists():
                matches = list(vol_dir.glob(f"第{chapter_no}章*.txt"))
                if matches:
                    return matches[0]
            return None

        # Search all volume dirs
        novel_dir = self.novel_dir()
        if not novel_dir.exists():
            return None

        for vol_dir in sorted(novel_dir.iterdir()):
            if vol_dir.is_dir():
                matches = list(vol_dir.glob(f"第{chapter_no}章*.txt"))
                if matches:
                    return matches[0]
        return None

    def find_all_chapters(self, volume_no: int = None,
                          volume_title: str = "") -> list[Path]:
        """Find all chapter TXT files in a volume."""
        if volume_no is not None:
            vol_dir = self.volume_dir(volume_no, volume_title)
            if not vol_dir.exists():
                return []
            return sorted(vol_dir.glob("第*章*.txt"))

        # All volumes
        all_chapters = []
        novel_dir = self.novel_dir()
        if novel_dir.exists():
            for vol_dir in sorted(novel_dir.iterdir()):
                if vol_dir.is_dir():
                    all_chapters.extend(sorted(vol_dir.glob("第*章*.txt")))
        return all_chapters

    @classmethod
    def create_output_dirs(cls, resolver: "PathResolver", volume_no: int,
                           volume_title: str = "") -> Path:
        """Create the volume output directory if it doesn't exist."""
        vol_dir = resolver.volume_dir(volume_no, volume_title)
        vol_dir.mkdir(parents=True, exist_ok=True)
        return vol_dir
