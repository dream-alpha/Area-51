#!/usr/bin/env python3
# Copyright (C) 2018-2025 by dream-alpha
# License: GNU General Public License v3.0 (see LICENSE file for details)

"""
xHamster Provider - Refactored

This module contains the main xHamster provider class that orchestrates
category and video management through dedicated classes.
"""

from __future__ import annotations

import re
from typing import Any
from pathlib import Path
from base_provider import BaseProvider
from debug import get_logger
from .category import Category
from .video import Video

logger = get_logger(__file__)


class Provider(BaseProvider):
    """xHamster provider class with modular architecture"""

    def __init__(self, provider_id, data_dir: Path = None):
        """Initialize the xHamster provider with modular components"""
        super().__init__(provider_id, data_dir)

        # Provider properties
        self.name = "xHamster"
        self.base_url = "https://xhamster.com/"
        self.supports_categories = True
        self.supports_search = True

        # Ensure xHamster-specific headers are set
        self.session.headers.update({
            "Referer": "https://xhamster.com/",
            "Origin": "https://xhamster.com"
        })

        # Initialize modular components
        self.category_manager = Category(self)
        self.video_manager = Video(self)

    def get_categories(self) -> list[dict[str, Any]]:
        """Get xHamster categories using the category manager"""
        return self.category_manager.get_categories()

    def get_media_items(self, category: dict, page: int = 1, limit: int = 28) -> list[dict[str, Any]]:
        """Get videos from specific category using the video manager"""
        return self.video_manager.get_media_items(category, page, limit)

    def get_latest_videos(self, page: int = 1, limit: int = 28) -> list[dict[str, Any]]:
        """Get latest videos using the video manager"""
        return self.video_manager.get_latest_videos(page, limit)

    def search_videos(self, term: str, page: int = 1, limit: int = 28) -> list[dict[str, Any]]:
        """Search for videos using the video manager"""
        return self.video_manager.search_videos(term, page, limit)

    def extract_video_page_metadata(self, video_url: str) -> dict[str, Any]:
        """Extract metadata from video page using the video manager"""
        return self.video_manager.extract_video_page_metadata(video_url)

    def extract_video_id(self, url: str) -> str:
        """Extract video ID from xHamster URL"""
        if not url:
            return "unknown"

        # xHamster video URL patterns
        patterns = [
            r'/videos/([^/?]+)',
            r'xhamster\.com/videos/([^/?]+)',
            r'/(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return "unknown"

    def extract_metadata(self, html: str) -> dict[str, Any]:
        """Extract video metadata from xHamster HTML using the video manager"""
        return self.video_manager.extract_metadata(html)
