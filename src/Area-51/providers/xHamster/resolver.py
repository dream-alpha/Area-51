#!/usr/bin/env python3
# Copyright (C) 2018-2025 by dream-alpha
# License: GNU General Public License v3.0 (see LICENSE file for details)

"""
xHamster Resolver Implementation

This module contains the xHamster resolver class with methods for:
- Resolving xHamster video page URLs to streaming URLs
- Extracting video metadata and quality options
- Handling advanced anti-403 protections
"""

from __future__ import annotations

import os
import sys
import re
import json
from typing import Any
from base_resolver import BaseResolver
from auth_utils import AuthTokens
from quality_utils import select_best_source, extract_metadata_from_url
from debug import get_logger

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = get_logger(__file__)


class Resolver(BaseResolver):
    """xHamster URL resolver with anti-403 protection"""

    def __init__(self):
        super().__init__()
        self.name = "xhamster"
        self.auth_tokens = AuthTokens()

    def _get_video_id(self, args) -> str:
        """Extract video ID from URL for caching purposes"""
        url = args.get("url", "")
        match = re.search(r'xhamster\.com/videos/([^/]+)-(\d+)', url)
        if match:
            return match.group(2)
        return ""

    def determine_recorder_type(self, url: str) -> str:
        """
        Determine the appropriate recorder type based on URL characteristics.

        Optimized for xHamster to use hls_basic for regular HLS playlists
        and only use hls_m4s for actual fragmented MP4 streams.

        Args:
            url: The resolved URL

        Returns:
            str: One of 'mp4', 'hls_basic', 'hls_live', 'hls_m4s'
        """
        url_lower = url.lower()

        # Check for HLS formats
        if '.m3u8' in url_lower:
            # Use base resolver logic which properly handles MP4/M4S segments
            # This includes .av1.mp4.m3u8, .mp4.m3u8, and .m4s.m3u8 formats
            return super().determine_recorder_type(url)

        # Default to MP4 for direct video files (xHamster typically uses MP4)
        return 'mp4'

    def resolve_url(self, args: dict) -> dict[str, Any] | None:
        """
        Resolve xHamster video URL to streaming sources using centralized auth utilities.

        Args:
            args (dict): Input arguments containing the URL etc.
        """
        url = args.get("url", "")
        quality = args.get("quality", "best")
        av1 = args.get("av1", False)  # Whether to include AV1 codecs (None=use global setting, True=force enable, False=force disable)
        logger.info("Resolving xHamster URL: %s", url)

        # Use centralized authentication with fallback methods
        html = self.auth_tokens.fetch_with_fallback(url, "https://xhamster.com")

        if html:
            sources = self._parse_html_for_sources(html)
            if sources:
                logger.info("URL resolution successful using method: %s", self.auth_tokens.method)

                # Select the optimal quality URL from available sources using quality preference
                best_source = select_best_source(sources, quality, codec_aware=True, av1=av1)
                resolved_url = best_source["url"] if best_source else url

                # Check if the resolved URL is a template URL and use base resolver template resolution
                if self._is_template_url(resolved_url):
                    logger.info("Detected template URL, using base resolver template resolution")
                    template_resolved_url = self._resolve_template_url(resolved_url, quality)
                    if template_resolved_url and template_resolved_url != resolved_url:
                        resolved_url = template_resolved_url
                        logger.info("Template resolved: %s", resolved_url[:100] + "..." if len(resolved_url) > 100 else resolved_url)

                logger.info("Selected quality: %s (requested: %s) - %s",
                            best_source.get("quality", "Unknown") if best_source else "None",
                            quality,
                            resolved_url)

                # Additional debugging for xHamster CDN URLs
                if "xhcdn.com" in resolved_url:
                    logger.info("xHamster CDN URL detected - ensuring proper headers are set")
                    if "referer=" in resolved_url.lower():
                        logger.info("URL contains referer validation - headers are critical for playback")

                # Determine recorder type based on URL characteristics
                recorder_id = self.determine_recorder_type(resolved_url)

                # Create FFmpeg headers from auth tokens for M4S recorder
                auth_tokens_dict = self.auth_tokens.to_dict()

                # Ensure critical headers are set for xHamster CDN access
                if not auth_tokens_dict.get("headers"):
                    auth_tokens_dict["headers"] = {}

                # xHamster CDN requires proper Referer header - use proper case
                auth_tokens_dict["headers"]["Referer"] = "https://xhamster.com/"

                # Add additional headers required for CDN access - use proper case
                auth_tokens_dict["headers"]["Origin"] = "https://xhamster.com"

                # Ensure User-Agent is properly cased (fix lowercase from auth_tokens)
                headers = auth_tokens_dict["headers"]
                if "user-agent" in headers and "User-Agent" not in headers:
                    headers["User-Agent"] = headers.pop("user-agent")

                # Fix other common lowercase headers
                header_fixes = {
                    "accept": "Accept",
                    "accept-encoding": "Accept-Encoding",
                    "accept-language": "Accept-Language",
                    "connection": "Connection",
                    "cache-control": "Cache-Control"
                }

                for old_key, new_key in header_fixes.items():
                    if old_key in headers and new_key not in headers:
                        headers[new_key] = headers.pop(old_key)

                # Convert to FFmpeg format
                ffmpeg_headers = self.auth_tokens.get_ffmpeg_headers()

                # Ensure the session has the updated headers
                session = self.auth_tokens.session
                if session and auth_tokens_dict.get("headers"):
                    # Remove any existing Cookie headers to prevent duplicates
                    session.headers.pop('Cookie', None)
                    session.headers.pop('cookie', None)

                    # Filter out Cookie headers from auth_tokens before updating session
                    headers_to_update = {k: v for k, v in auth_tokens_dict["headers"].items() if k.lower() != 'cookie'}
                    session.headers.update(headers_to_update)
                    logger.info("Updated session headers with auth tokens for recording")

                return {
                    "resolved_url": resolved_url,
                    "auth_tokens": auth_tokens_dict,
                    "session": session,  # Include authenticated session for recording
                    "ffmpeg_headers": ffmpeg_headers,  # Include FFmpeg headers for M4S recorder
                    "resolved": True,
                    "resolver": self.name,
                    "recorder_id": recorder_id,
                    "quality": quality,  # Pass through the originally requested quality
                }

        # If all methods failed
        logger.error("All resolution methods failed for xHamster URL")
        return None

    def _parse_html_for_sources(self, html: str) -> list[dict[str, Any]]:
        """Parse HTML content to extract video sources"""
        if not html:
            return []

        sources = []

        # Method 1: Pattern for JSON url/label pairs (most common in xHamster)
        json_pattern = r'"url":"([^"]+)"[^}]*"label":"([^"]+)"'
        json_matches = re.findall(json_pattern, html, re.IGNORECASE)

        for video_url, quality_label in json_matches:
            # Clean up the URL (unescape JSON)
            clean_url = (
                video_url.replace("\\/", "/").replace("\\\\", "").replace("\\", "")
            )

            # Skip non-video URLs (filter out thumbnails and ads)
            if not clean_url or not any(
                indicator in clean_url.lower()
                for indicator in ("mp4", "m3u8", "video")
            ):
                continue

            # Skip thumbnail URLs
            if "thumb" in clean_url.lower():
                continue

            # Skip preview/trailer URLs - these are usually short clips
            # Look for indicators like "preview", "trailer", "sample" in the URL
            if any(indicator in clean_url.lower() for indicator in ("preview", "trailer", "sample", "promo")):
                logger.info("Skipping preview/trailer URL: %s", clean_url)
                continue

            # Determine quality
            quality = (
                quality_label
                if quality_label and quality_label != "adaptive"
                else "Unknown"
            )

            # Extract metadata from URL, using quality from data if available
            metadata = extract_metadata_from_url(clean_url)
            if quality != "Unknown":
                metadata["quality"] = quality

            sources.append({"url": clean_url, **metadata})

        # Method 2: Look for xHamster's newer player format (newer site versions)
        player_json_pattern = r'window\.initPlayer\(\s*({[^}]+})\s*\)'
        player_match = re.search(player_json_pattern, html)
        if player_match:
            try:
                player_data_str = player_match.group(1)
                # Fix potential JSON issues
                player_data_str = re.sub(r'([{,])\s*(\w+):', r'\1"\2":', player_data_str)
                player_data_str = player_data_str.replace("'", '"')

                player_data = json.loads(player_data_str)

                if "sources" in player_data:
                    for source in player_data["sources"]:
                        if "url" in source:
                            url = source["url"].replace("\\/", "/")
                            metadata = extract_metadata_from_url(url)
                            # Override with quality from JSON if available
                            if source.get("quality"):
                                metadata["quality"] = source["quality"]
                            sources.append({"url": url, **metadata})
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning("Failed to parse player JSON: %s", e)

        # Method 3: Direct MP4 URLs (main video streams only)
        mp4_pattern = (
            r'(https?://video[^\s"<>]*\.mp4[^\s"<>]*)'  # Focus on video CDN URLs
        )
        mp4_matches = re.findall(mp4_pattern, html, re.IGNORECASE)

        for mp4_url in mp4_matches:
            if mp4_url and mp4_url not in [s["url"] for s in sources]:
                # Skip if this is actually an HLS URL (ends with .m3u8)
                if mp4_url.lower().endswith('.m3u8'):
                    continue

                # Skip thumbnails
                if "thumb" in mp4_url.lower():
                    continue

                # Skip preview/trailer URLs
                if any(indicator in mp4_url.lower() for indicator in ("preview", "trailer", "sample", "promo")):
                    logger.info("Skipping preview/trailer URL: %s", mp4_url[:80])
                    continue

                # Extract metadata from URL with fallback quality
                metadata = extract_metadata_from_url(mp4_url)
                if not metadata["quality"]:
                    metadata["quality"] = "480p"  # Fallback quality

                sources.append({"url": mp4_url, **metadata})

        # Method 4: HLS manifest URLs (for adaptive streaming)
        hls_pattern = r'(https?://[^\s"<>]*\.m3u8[^\s"<>]*)'
        hls_matches = re.findall(hls_pattern, html, re.IGNORECASE)

        for hls_url in hls_matches:
            if hls_url and hls_url not in [s["url"] for s in sources]:
                # Skip thumbnails
                if "thumb" in hls_url.lower():
                    continue

                # Skip preview/trailer URLs
                if any(indicator in hls_url.lower() for indicator in ("preview", "trailer", "sample", "promo")):
                    logger.info("Skipping preview/trailer HLS URL: %s", hls_url)
                    continue

                # For template URLs, let the base resolver handle template resolution
                # We'll mark them as adaptive for proper quality selection
                metadata = extract_metadata_from_url(hls_url)
                if not metadata["quality"]:
                    metadata["quality"] = "adaptive"  # HLS adaptive streaming - highest priority
                if "_TPL_" in hls_url and "multi=" in hls_url:
                    logger.info("Found HLS template URL, will be resolved by base template resolver")

                sources.append({"url": hls_url, **metadata})

        if sources:
            # Remove duplicates and sort by quality
            seen_urls = set()
            unique_sources = []
            for source in sources:
                if source["url"] not in seen_urls:
                    seen_urls.add(source["url"])
                    unique_sources.append(source)

            # Sorting is now handled internally by select_best_source()
            logger.info("Found %d sources through HTML parsing", len(unique_sources))
            return unique_sources
        return None
