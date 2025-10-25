#!/usr/bin/env python3
# Copyright (C) 2018-2025 by dream-alpha
# License: GNU General Public License v3.0 (see LICENSE file for details)

"""
XNXX Site Implementation

This module contains the XNXX provider class that coordinates:
- Category management via category.py
- Video processing via video.py
- URL resolution via resolver.py
"""

from __future__ import annotations

from typing import Any
from pathlib import Path
from base_provider import BaseProvider
from debug import get_logger
from session_utils import get_session
from .category import Category
from .video import Video

logger = get_logger(__file__)


class Provider(BaseProvider):
    """XNXX provider class - modular implementation"""

    def __init__(self, provider_id: str, data_dir: Path = None):
        super().__init__()
        self.provider_id = provider_id
        self.data_dir = data_dir
        self.base_url = "https://www.xnxx.com/"

        # Create session for HTTP requests
        self.session = get_session()

        # Initialize modular components
        self.category_manager = Category(self)
        self.video_manager = Video(self)

    def get_categories(self) -> list[dict[str, str]]:
        """Get XNXX categories using modular category manager"""
        return self.category_manager.get_categories()

    def get_latest_videos(self, page: int = 1, limit: int = 28) -> dict[str, Any]:
        """Get latest videos using modular video manager"""
        return self.video_manager.get_latest_videos(page, limit)

    def get_media_items(self, category: dict, page: int = 1, limit: int = 28) -> list[dict[str, Any]]:
        """Get media items using modular video manager"""
        return self.video_manager.get_media_items(category, page, limit)

    def search_videos(self, term: str, page: int = 1, limit: int = 28) -> dict[str, Any]:
        """Search videos using modular video manager"""
        return self.video_manager.search_videos(term, page, limit)

    def get_video_details(self, video_url: str) -> dict[str, Any]:
        """Get video details using modular video manager"""
        return self.video_manager.get_video_details(video_url)
