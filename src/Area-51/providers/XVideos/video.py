#!/usr/bin/env python3
# Copyright (C) 2018-2025 by dream-alpha
# License: GNU General Public License v3.0 (see LICENSE file for details)

"""
XVideos Video Management

This module handles video extraction, metadata parsing, and URL processing for XVideos provider.
Supports both old and new XVideos URL structures with search-video pattern detection.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, quote_plus
from typing import Any
from bs4 import BeautifulSoup
from auth_utils import get_headers
from debug import get_logger
from constants import MAX_VIDEOS

logger = get_logger(__file__)


class VideoManager:
    """Manages XVideos video extraction and processing"""

    def __init__(self, session, base_provider):
        """Initialize video manager with session and base provider utilities"""
        self.session = session
        self.base_provider = base_provider
        self.base_url = "https://www.xvideos.com/"
        self.provider_id = "xvideos"

    def get_latest_videos(self, page: int = 1, limit: int = 28) -> dict[str, Any]:
        """Get latest videos from XVideos"""
        url = f"{self.base_url}?p={page - 1}"  # XVideos uses 0-based pages
        return self._get_video_list(url, page, limit)

    def get_media_items(self, category: dict, page: int = 1, limit: int = 28) -> list[dict[str, Any]]:
        """Get videos from XVideos category"""
        category_url = category.get("url", "none")
        if "?" in category_url:
            url = f"{category_url}&p={page - 1}"
        else:
            url = f"{category_url}?p={page - 1}"

        result = self._get_video_list(url, page, limit)
        videos = result.get("videos", [])

        # SAFETY CHECK: Log search URLs but allow them through for debugging XVideos structure change
        filtered_videos = []
        search_url_count = 0

        for video in videos:
            video_url = video.get("url", "")
            if "/search-video/" in video_url:
                search_url_count += 1
                logger.info("XVideos structure change - found search-video URL pattern")
                # Keep the video for now to see what happens
            filtered_videos.append(video)

        if search_url_count > 0:
            logger.info("XVideos returned %d search-video URLs out of %d total videos", search_url_count, len(videos))
            logger.info("This suggests XVideos has changed their page structure")

        # Sort videos alphabetically by title
        filtered_videos.sort(key=lambda x: x['title'].lower())

        # Apply natural capping - return up to MAX_VIDEOS if available
        return filtered_videos[:MAX_VIDEOS] if len(filtered_videos) > MAX_VIDEOS else filtered_videos

    def search_videos(self, term: str, page: int = 1, limit: int = 28) -> dict[str, Any]:
        """Search videos on XVideos"""
        search_url = f"{self.base_url}?k={quote_plus(term)}&p={page - 1}"
        return self._get_video_list(search_url, page, limit)

    def _get_video_list(self, url: str, page: int, limit: int = 28) -> dict[str, Any]:
        """Parse video list from XVideos page"""
        try:
            headers = get_headers("browser")
            response = self.session.get(url, headers=headers, timeout=30)
            html = response.text

            soup = BeautifulSoup(html, 'html.parser')
            videos = []

            # Look for video thumbnails with multiple selectors
            video_elements = (
                soup.find_all('div', class_='thumb-block')
                + soup.find_all('div', class_='thumb')
                + soup.find_all('div', class_='mozaique')
            )

            for element in video_elements[:limit]:
                try:
                    # Extract video link
                    link_elem = element.find('a')
                    if not link_elem or not link_elem.get('href'):
                        continue

                    href = link_elem.get('href')
                    video_url = urljoin(self.base_url, href)

                    # Handle both old and new XVideos URL structures
                    if '/search-video/' in video_url:
                        logger.info("XVideos new structure: converting search URL to video format")
                        # Mark this as needing special handling by the resolver
                        needs_search_resolution = True
                    else:
                        needs_search_resolution = False

                    # Extract title
                    title_elem = (
                        element.find('p', class_='title')
                        or element.find('a', {'title': True})
                        or link_elem
                    )
                    title = (title_elem.get('title', '') or title_elem.get_text()).strip()
                    if not title:
                        continue

                    # Clean and sanitize title for JSON
                    title = self.base_provider.sanitize_for_json(title)

                    # Extract duration
                    duration_elem = element.find('span', class_='duration')
                    duration = duration_elem.get_text().strip() if duration_elem else "N/A"

                    # Extract thumbnail
                    img_elem = element.find('img')
                    thumbnail = img_elem.get('data-src') or img_elem.get('src') if img_elem else ""

                    # Instead of resolving immediately, store the original video URL
                    # and parse the metadata directly from HTML
                    videos.append({
                        "title": title,
                        "duration": duration,
                        "url": video_url,  # Store original page URL
                        "page_url": video_url,
                        "thumbnail": thumbnail,
                        "site": "xvideos",
                        "provider_id": self.provider_id,  # Include provider ID for recording
                        "streaming_url": "",  # Will be resolved on playback
                        "streaming_sources": [],  # Will be resolved on playback
                        "quality": "adaptive",  # Default adaptive quality - actual quality selected during resolution
                        "format": "mp4",  # Default format
                        "resolved": False,  # Mark as not resolved
                        "requires_resolution": True,  # Flag that this needs resolution before playback
                        "resolver": "xvideos",
                        "needs_search_resolution": needs_search_resolution,  # New XVideos structure flag
                    })

                except Exception as e:
                    logger.info("Error parsing video element: %s", e)
                    continue

        except Exception as e:
            logger.info("Error getting video list: %s", e)
            videos = []

        # Check for next page
        has_next = bool(
            re.search(r'href="([^"]+)" class="no-page next-page', html, re.IGNORECASE)
        )

        return {
            "videos": videos,
            "page": page,
            "has_next_page": has_next,
            "total_results": len(videos),
        }

    def resolve_video_url(self, video_url: str) -> dict[str, Any]:
        """Extract metadata for GUI display and return video page URL for later resolution"""
        try:
            # Provider fetches metadata for GUI display and returns page URL
            # Actual streaming URL resolution happens later during playback
            headers = get_headers("browser")
            headers["Referer"] = "https://www.xvideos.com/"

            response = self.session.get(video_url, headers=headers, timeout=30)

            if response.status_code == 200:
                # Extract metadata for GUI display
                metadata = self.extract_metadata(response.text)

                return {
                    "resolved": True,
                    "video_urls": [{
                        "url": video_url,  # Return the video page URL for later resolution
                        "quality": "adaptive",
                        "format": "page"  # Indicate this is a page URL, not a stream URL
                    }],
                    "title": metadata.get("title", ""),
                    "duration": metadata.get("duration", ""),
                    "thumbnail": metadata.get("thumbnail", ""),
                }
            return {
                "resolved": False,
                "video_urls": [],
                "error": f"Could not fetch page for metadata: HTTP {response.status_code}"
            }

        except Exception as e:
            return {
                "resolved": False,
                "video_urls": [],
                "error": f"Metadata extraction failed: {str(e)}"
            }

    def extract_metadata(self, html: str) -> dict[str, Any]:
        """Extract video metadata from XVideos HTML"""
        metadata = {
            "title": None,
            "duration": None,
            "duration_seconds": None,
            "thumbnail": None,
        }

        try:
            # Extract title
            title_patterns = [
                r'<meta property="og:title" content="([^"]+)"',
                r'<title>([^<]+)</title>',
                r'html5player\.setVideoTitle\(\'([^\']+)\'\)',
            ]

            for pattern in title_patterns:
                match = re.search(pattern, html)
                if match:
                    title = match.group(1).strip()
                    # Clean up common title suffixes
                    title = re.sub(r' - XVIDEOS.COM$', '', title)
                    metadata["title"] = self.base_provider.sanitize_for_json(title)
                    break

            # Extract duration
            duration_pattern = r'<meta property="og:duration" content="(\d+)"'
            duration_match = re.search(duration_pattern, html)
            if duration_match:
                try:
                    seconds = int(duration_match.group(1))
                    metadata["duration_seconds"] = seconds

                    # Convert to MM:SS or HH:MM:SS format
                    minutes, secs = divmod(seconds, 60)
                    hours, minutes = divmod(minutes, 60)

                    if hours > 0:
                        metadata["duration"] = f"{hours:02d}:{minutes:02d}:{secs:02d}"
                    else:
                        metadata["duration"] = f"{minutes:02d}:{secs:02d}"
                except (ValueError, IndexError):
                    pass

            # Extract thumbnail
            thumb_pattern = r'html5player\.setThumbUrl\(\'([^\']+)\'\)'
            thumb_match = re.search(thumb_pattern, html)
            if thumb_match:
                metadata["thumbnail"] = thumb_match.group(1)

            return metadata

        except Exception as e:
            logger.error("Error extracting metadata: %s", e)
            return metadata
