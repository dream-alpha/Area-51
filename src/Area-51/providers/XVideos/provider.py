#!/usr/bin/env python3
# Copyright (C) 2018-2025 by dream-alpha
# License: GNU General Public License v3.0 (see LICENSE file for details)

"""
XVideos Site Implementation - Modular Provider

This module contains the XVideos provider coordinator that delegates to
specialized category and video managers for better code organization.
"""

from __future__ import annotations

from typing import Any
from pathlib import Path
from base_provider import BaseProvider
from debug import get_logger
from session_utils import get_session
from .category import CategoryManager
from .video import VideoManager

logger = get_logger(__file__)


class Provider(BaseProvider):
    """XVideos provider coordinator - delegates to specialized managers"""

    def __init__(self, provider_id: str, data_dir: Path = None):
        super().__init__()
        self.provider_id = provider_id
        self.data_dir = data_dir
        self.base_url = "https://www.xvideos.com/"

        # Create session for HTTP requests
        self.session = get_session()

        # Initialize modular components
        self.category_manager = CategoryManager(self.session, self)
        self.video_manager = VideoManager(self.session, self)

    def get_categories(self) -> list[dict[str, str]]:
        """Get XVideos categories - delegates to category manager"""
        return self.category_manager.get_categories()

    def get_latest_videos(self, page: int = 1, limit: int = 28) -> dict[str, Any]:
        """Get latest videos - delegates to video manager"""
        return self.video_manager.get_latest_videos(page, limit)

    def get_media_items(self, category: dict, page: int = 1, limit: int = 28) -> list[dict[str, Any]]:
        """Get videos from category - delegates to video manager"""
        return self.video_manager.get_media_items(category, page, limit)

    def search_videos(self, term: str, page: int = 1, limit: int = 28) -> dict[str, Any]:
        """Search videos - delegates to video manager"""
        return self.video_manager.search_videos(term, page, limit)

    def resolve_video_url(self, video_url: str) -> dict[str, Any]:
        """Resolve video URL - delegates to video manager"""
        return self.video_manager.resolve_video_url(video_url)
