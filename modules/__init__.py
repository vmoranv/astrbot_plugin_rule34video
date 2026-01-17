"""
Rule34Video API 模块
用于解析和获取 rule34video.com 的视频信息
"""

from .consts import ROOT_URL, HEADERS, SortOrder, TimeRange
from .errors import (
    Rule34VideoError,
    VideoNotFound,
    InvalidURL,
    NetworkError,
    ParseError,
    VideoDisabled,
    RateLimitError,
    ConfigurationError,
)
from .video import Video
from .client import Client

__all__ = [
    "Video",
    "Client",
    "ROOT_URL",
    "HEADERS",
    "SortOrder",
    "TimeRange",
    "Rule34VideoError",
    "VideoNotFound",
    "InvalidURL",
    "NetworkError",
    "ParseError",
    "VideoDisabled",
    "RateLimitError",
    "ConfigurationError",
]