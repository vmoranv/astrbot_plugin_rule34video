"""
Rule34Video API 常量定义
"""

import re

# 基础URL
ROOT_URL = "https://rule34video.com"

# API端点 - 注意：rule34video 使用 /videos/ 而不是 /video/
VIDEO_URL = f"{ROOT_URL}/videos/"
SEARCH_URL = f"{ROOT_URL}/search/"
CATEGORY_URL = f"{ROOT_URL}/categories/"
TAG_URL = f"{ROOT_URL}/tags/"

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# 正则表达式 - 视频ID提取 (支持 /video/ 和 /videos/)
REGEX_VIDEO_ID = re.compile(r"/videos?/(\d+)")
REGEX_VIDEO_ID_ALT = re.compile(r"video[_-]?(\d+)")

# 正则表达式 - 视频信息提取
REGEX_VIDEO_TITLE = re.compile(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>', re.IGNORECASE)
REGEX_VIDEO_TITLE_ALT = re.compile(r'<title>([^<]+)</title>', re.IGNORECASE)

# 视频源URL提取 - 支持多种格式
# 标准 source 标签
REGEX_VIDEO_SOURCE = re.compile(r'<source[^>]+src="([^"]+)"[^>]*type="video/mp4"', re.IGNORECASE)
# 通用 source 标签 (无type属性)
REGEX_VIDEO_SOURCE_GENERIC = re.compile(r'<source[^>]+src="([^"]+\.mp4[^"]*)"', re.IGNORECASE)
# JavaScript 变量格式
REGEX_VIDEO_SOURCE_ALT = re.compile(r'video_url\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)
# 质量特定的URL (数字+p格式)
REGEX_VIDEO_SOURCE_720 = re.compile(r'(?:720p?|720)["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)
REGEX_VIDEO_SOURCE_480 = re.compile(r'(?:480p?|480)["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)
REGEX_VIDEO_SOURCE_360 = re.compile(r'(?:360p?|360)["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)
REGEX_VIDEO_SOURCE_1080 = re.compile(r'(?:1080p?|1080)["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)
REGEX_VIDEO_SOURCE_2160 = re.compile(r'(?:2160p?|2160|4k)["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)

# 从文件名提取质量 (如 video_720p.mp4 或 video_720.mp4)
REGEX_QUALITY_FROM_URL = re.compile(r'[_/](\d{3,4})(?:p)?\.mp4', re.IGNORECASE)

# 缩略图提取 - 多种模式
REGEX_THUMBNAIL = re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE)
REGEX_THUMBNAIL_ALT = re.compile(r'poster="([^"]+)"', re.IGNORECASE)
REGEX_PREVIEW_IMAGE = re.compile(r'preview_url\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)
# 从 flashvars 提取
REGEX_THUMBNAIL_FLASHVARS = re.compile(r'preview_url\s*:\s*["\']([^"\']+)["\']', re.IGNORECASE)

# 视频元数据 - 增强版正则
REGEX_DURATION = re.compile(r'<meta[^>]+itemprop="duration"[^>]+content="([^"]+)"', re.IGNORECASE)
REGEX_DURATION_ALT = re.compile(r'duration\s*[:=]\s*["\']?(\d+)["\']?', re.IGNORECASE)
REGEX_DURATION_TEXT = re.compile(r'(\d{1,2}:\d{2}(?::\d{2})?)', re.IGNORECASE)
REGEX_DURATION_SPAN = re.compile(r'<span[^>]*class="[^"]*duration[^"]*"[^>]*>([^<]+)</span>', re.IGNORECASE)

# 观看次数 - 多种模式
REGEX_VIEWS = re.compile(r'(\d[\d,\.]*)\s*(?:views?|Views|播放)', re.IGNORECASE)
REGEX_VIEWS_SPAN = re.compile(r'<span[^>]*class="[^"]*views[^"]*"[^>]*>(\d[\d,\.]*)</span>', re.IGNORECASE)
REGEX_VIEWS_DIV = re.compile(r'<div[^>]*class="[^"]*views[^"]*"[^>]*>.*?(\d[\d,\.]+)', re.IGNORECASE | re.DOTALL)
REGEX_VIEWS_DATA = re.compile(r'data-views="(\d+)"', re.IGNORECASE)
REGEX_VIEWS_META = re.compile(r'interactionCount["\']?\s*[:=]\s*["\']?(\d+)', re.IGNORECASE)

# 点赞/踩 - 多种模式
REGEX_LIKES = re.compile(r'(\d[\d,\.]*)\s*(?:likes?|Likes|赞)', re.IGNORECASE)
REGEX_LIKES_SPAN = re.compile(r'<span[^>]*class="[^"]*like-count[^"]*"[^>]*>(\d[\d,\.]*)</span>', re.IGNORECASE)
REGEX_LIKES_DATA = re.compile(r'data-likes="(\d+)"', re.IGNORECASE)
REGEX_LIKES_BUTTON = re.compile(r'class="[^"]*like-button[^"]*"[^>]*>.*?(\d[\d,\.]+)', re.IGNORECASE | re.DOTALL)

REGEX_DISLIKES = re.compile(r'(\d[\d,\.]*)\s*(?:dislikes?|Dislikes|踩)', re.IGNORECASE)
REGEX_DISLIKES_SPAN = re.compile(r'<span[^>]*class="[^"]*dislike-count[^"]*"[^>]*>(\d[\d,\.]*)</span>', re.IGNORECASE)
REGEX_DISLIKES_DATA = re.compile(r'data-dislikes="(\d+)"', re.IGNORECASE)

# 日期
REGEX_UPLOAD_DATE = re.compile(r'<meta[^>]+itemprop="uploadDate"[^>]+content="([^"]+)"', re.IGNORECASE)
REGEX_DATE_ALT = re.compile(r'(\d{4}-\d{2}-\d{2})', re.IGNORECASE)
REGEX_DATE_SPAN = re.compile(r'<span[^>]*class="[^"]*date[^"]*"[^>]*>([^<]+)</span>', re.IGNORECASE)
REGEX_DATE_UPLOADED = re.compile(r'(?:uploaded|added|posted)\s*:?\s*([^<]+)', re.IGNORECASE)

# 标签提取
REGEX_TAGS = re.compile(r'<a[^>]+href="/tags/[^"]*"[^>]*>([^<]+)</a>', re.IGNORECASE)
REGEX_CATEGORIES = re.compile(r'<a[^>]+href="/categories/[^"]*"[^>]*>([^<]+)</a>', re.IGNORECASE)

# 作者/上传者
REGEX_UPLOADER = re.compile(r'<a[^>]+href="/members/[^"]*"[^>]*>([^<]+)</a>', re.IGNORECASE)
REGEX_UPLOADER_ALT = re.compile(r'uploader\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)
REGEX_UPLOADER_SPAN = re.compile(r'<span[^>]*class="[^"]*uploader[^"]*"[^>]*>([^<]+)</span>', re.IGNORECASE)

# 搜索结果
REGEX_SEARCH_ITEM = re.compile(r'<div[^>]+class="[^"]*thumb[^"]*"[^>]*>.*?<a[^>]+href="(/video/\d+/[^"]*)"', re.IGNORECASE | re.DOTALL)
REGEX_SEARCH_THUMBNAIL = re.compile(r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*thumb[^"]*"', re.IGNORECASE)

# 分页
REGEX_PAGINATION = re.compile(r'<a[^>]+href="[^"]*[?&]page=(\d+)[^"]*"', re.IGNORECASE)
REGEX_TOTAL_PAGES = re.compile(r'page\s*(\d+)\s*of\s*(\d+)', re.IGNORECASE)

# 视频质量选项
QUALITY_OPTIONS = ["2160p", "1080p", "720p", "480p", "360p", "240p"]

# 排序选项
class SortOrder:
    LATEST = "latest"
    MOST_VIEWED = "most_viewed"
    TOP_RATED = "top_rated"
    LONGEST = "longest"
    RANDOM = "random"

# 时间范围
class TimeRange:
    ALL_TIME = "all"
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"