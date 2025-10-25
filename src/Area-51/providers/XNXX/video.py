#!/usr/bin/env python3
# Copyright (C) 2018-2025 by dream-alpha
# License: GNU General Public License v3.0 (see LICENSE file for details)

"""
XNXX Video Processing

This module handles all video-related functionality for the XNXX provider,
including video discovery, extraction, and metadata processing.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
from debug import get_logger
from auth_utils import get_headers

logger = get_logger(__file__)


class Video:
    """Handles XNXX video processing and extraction"""

    def __init__(self, provider):
        """Initialize with reference to parent provider"""
        self.provider = provider

    def get_media_items(self, category: dict, page: int = 1, _limit: int = 28) -> list[dict[str, Any]]:
        """Get media items for a specific category"""
        category_url = category.get("url", "none")
        result = self._get_video_list(category_url, page)
        return result.get("videos", [])

    def get_latest_videos(self, page: int = 1, _limit: int = 28) -> dict[str, Any]:
        """Get latest videos from XNXX"""
        # XNXX latest videos are at the root, page 1 is just the base URL
        if page == 1:
            latest_url = self.provider.base_url
        else:
            latest_url = f"{self.provider.base_url}{page}"
        return self._get_video_list(latest_url, page)

    def search_videos(self, term: str, page: int = 1, _limit: int = 28) -> dict[str, Any]:
        """Search videos"""
        search_url = f"{self.provider.base_url}search/{quote(term)}?page={page}"
        return self._get_video_list(search_url, page)

    def _get_video_list(self, url: str, page: int) -> dict[str, Any]:
        """Try to scrape XNXX video list"""
        try:
            headers = get_headers("browser")

            response = self.provider.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            videos = []

            # Try to find video containers - XNXX uses .mozaique .thumb-block structure
            containers = soup.select(".mozaique .thumb-block") or soup.select(".thumb-block")

            if containers:
                for container in containers:
                    try:
                        # XNXX structure: .thumb-under p a contains the title and URL
                        title_link = container.select_one(".thumb-under p a")
                        if not title_link:
                            continue

                        href = title_link.get("href", "")
                        if not href:
                            continue

                        if not href.startswith("http"):
                            href = urljoin(self.provider.base_url, href)

                        # Get title from title attribute or text content
                        title = title_link.get("title", "") or title_link.get_text(strip=True)
                        if not title:
                            continue

                        # Get thumbnail from .thumb img with data-src attribute
                        img = container.select_one(".thumb img")
                        thumbnail = ""
                        if img:
                            thumbnail = img.get("data-src", img.get("src", ""))
                            if thumbnail and not thumbnail.startswith("http"):
                                thumbnail = f"https:{thumbnail}" if thumbnail.startswith("//") else thumbnail

                        # Get metadata (duration, views)
                        duration = "Unknown"
                        views = "0"

                        metadata = container.select_one(".metadata")
                        if metadata:
                            # Views are in .right span
                            views_elem = metadata.select_one(".right")
                            if views_elem:
                                views_text = views_elem.get_text(strip=True)
                                views = views_text.split()[0] if views_text else "0"

                        # Extract video title and clean it
                        clean_title = self.provider.sanitize_for_json(title)

                        # Add the video without resolving the URL
                        video_data = {
                            "title": clean_title,
                            "duration": duration,
                            "url": href,
                            "page_url": href,           # Keep original page URL for reference
                            "thumbnail": thumbnail,
                            "views": views,
                            "site": self.provider.name,
                            "provider_id": self.provider.provider_id,  # Include provider ID for recording
                            "quality": "adaptive",      # Default adaptive quality - actual quality selected during resolution
                            "format": "mp4",            # Assume mp4 as default format
                            "needs_resolution": True,   # Mark that this URL needs resolution
                            "category": "Unknown",
                        }

                        videos.append(video_data)
                        logger.debug("Prepared video: %s", video_data)

                    except Exception as e:
                        logger.debug("Error processing video container: %s", e)
                        continue

                logger.info("Found %d videos from XNXX", len(videos))
            else:
                logger.info("No video containers found on XNXX page")

            return {
                "videos": videos,
                "has_next_page": len(videos) >= 28,  # Assume more pages if we got a full page
                "page": page
            }

        except Exception as e:
            logger.info("Error getting video list from XNXX: %s", e)
            return {"videos": [], "has_next_page": False, "page": page}

    def get_video_details(self, video_url: str) -> dict[str, Any]:
        """Get detailed information for a specific video"""
        try:
            headers = get_headers("browser")
            response = self.provider.session.get(video_url, headers=headers, timeout=30)
            response.raise_for_status()

            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            # Extract additional metadata if needed
            details = {
                "resolved_url": video_url,
                "description": "",
                "tags": [],
                "upload_date": "",
                "uploader": "",
            }

            # Try to extract description
            desc_elem = soup.select_one(".video-description") or soup.select_one("#video-description")
            if desc_elem:
                details["description"] = self.provider.sanitize_for_json(desc_elem.get_text(strip=True))

            # Try to extract tags
            tag_elements = soup.select(".video-tags a") or soup.select(".tags a")
            details["tags"] = [self.provider.sanitize_for_json(tag.get_text(strip=True)) for tag in tag_elements[:10]]

            return details

        except Exception as e:
            logger.debug("Error getting video details from %s: %s", video_url, e)
            return {"resolved_url": video_url}
