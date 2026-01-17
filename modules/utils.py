"""
Rule34Video API 工具函数
"""

import re
import html
import hashlib
import os
from typing import Optional, Union, List
from urllib.parse import urlencode
from io import BytesIO

try:
    from PIL import Image, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from .consts import ROOT_URL, REGEX_VIDEO_ID, REGEX_VIDEO_ID_ALT


def extract_video_id(url_or_id: str) -> Optional[str]:
    """
    从URL或字符串中提取视频ID
    
    Args:
        url_or_id: 视频URL或ID
        
    Returns:
        视频ID字符串，如果无法提取则返回None
    """
    if not url_or_id:
        return None
    
    url_or_id = str(url_or_id).strip()
    
    # 如果是纯数字，直接返回
    if url_or_id.isdigit():
        return url_or_id
    
    # 尝试从URL中提取
    match = REGEX_VIDEO_ID.search(url_or_id)
    if match:
        return match.group(1)
    
    # 尝试备用模式
    match = REGEX_VIDEO_ID_ALT.search(url_or_id)
    if match:
        return match.group(1)
    
    return None


def build_video_url(video_id: str) -> str:
    """
    构建视频页面URL
    
    Args:
        video_id: 视频ID
        
    Returns:
        完整的视频URL
    """
    # rule34video.com 使用 /videos/ 路径格式
    return f"{ROOT_URL}/videos/{video_id}/"


def clean_text(text: str) -> str:
    """
    清理文本内容，移除多余空白和HTML实体
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    # 解码HTML实体
    text = html.unescape(text)
    
    # 移除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    
    # 规范化空白
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def parse_duration(duration_str: str) -> int:
    """
    解析时长字符串为秒数
    
    Args:
        duration_str: 时长字符串，如 "5:30" 或 "1:23:45" 或 "PT5M30S"
        
    Returns:
        秒数
    """
    if not duration_str:
        return 0
    
    duration_str = str(duration_str).strip()
    
    # ISO 8601 格式 (PT5M30S)
    iso_match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str, re.IGNORECASE)
    if iso_match:
        hours = int(iso_match.group(1) or 0)
        minutes = int(iso_match.group(2) or 0)
        seconds = int(iso_match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds
    
    # 标准时间格式 (HH:MM:SS 或 MM:SS)
    time_match = re.match(r'(\d+):(\d+)(?::(\d+))?', duration_str)
    if time_match:
        if time_match.group(3):
            # HH:MM:SS
            hours = int(time_match.group(1))
            minutes = int(time_match.group(2))
            seconds = int(time_match.group(3))
        else:
            # MM:SS
            hours = 0
            minutes = int(time_match.group(1))
            seconds = int(time_match.group(2))
        return hours * 3600 + minutes * 60 + seconds
    
    # 纯数字（秒）
    if duration_str.isdigit():
        return int(duration_str)
    
    return 0


def format_duration(seconds: int) -> str:
    """
    将秒数格式化为时长字符串
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化的时长字符串 (MM:SS 或 HH:MM:SS)
    """
    if seconds < 0:
        seconds = 0
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def parse_view_count(view_str: str) -> int:
    """
    解析浏览量字符串为数字
    
    Args:
        view_str: 浏览量字符串，如 "1,234" 或 "1.2K" 或 "1.5M"
        
    Returns:
        浏览量数字
    """
    if not view_str:
        return 0
    
    view_str = str(view_str).strip().upper()
    
    # 移除逗号和空格
    view_str = view_str.replace(',', '').replace(' ', '')
    
    # 处理K/M/B后缀
    multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}
    
    for suffix, mult in multipliers.items():
        if view_str.endswith(suffix):
            try:
                return int(float(view_str[:-1]) * mult)
            except ValueError:
                return 0
    
    # 纯数字
    try:
        return int(float(view_str))
    except ValueError:
        return 0


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    清理文件名，移除不安全字符
    
    Args:
        filename: 原始文件名
        max_length: 最大长度
        
    Returns:
        安全的文件名
    """
    if not filename:
        return "video"
    
    # 移除/替换不安全字符
    unsafe_chars = '<>:"/\\|?*\x00'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    
    # 移除首尾空白和点
    filename = filename.strip(' .')
    
    # 截断长度
    if len(filename) > max_length:
        filename = filename[:max_length]
    
    return filename or "video"


def generate_cache_key(*args, **kwargs) -> str:
    """
    生成缓存键
    
    Args:
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        缓存键字符串
    """
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def normalize_quality(quality: Union[str, int]) -> str:
    """
    标准化视频质量参数
    
    Args:
        quality: 质量参数，如 "720p", 720, "best", "worst"
        
    Returns:
        标准化的质量字符串
    """
    if isinstance(quality, int):
        return f"{quality}p"
    
    quality = str(quality).lower().strip()
    
    # 特殊值
    if quality in ("best", "highest", "max"):
        return "best"
    if quality in ("worst", "lowest", "min"):
        return "worst"
    if quality in ("half", "medium", "mid"):
        return "half"
    
    # 提取数字
    match = re.search(r'(\d+)', quality)
    if match:
        return f"{match.group(1)}p"
    
    return "best"


def select_best_quality(available_qualities: List[str], target: str = "best") -> Optional[str]:
    """
    从可用质量列表中选择最佳匹配
    
    Args:
        available_qualities: 可用的质量列表，如 ["720p", "480p", "360p"]
        target: 目标质量
        
    Returns:
        选中的质量字符串
    """
    if not available_qualities:
        return None
    
    # 提取数字并排序
    def get_resolution(q):
        match = re.search(r'(\d+)', str(q))
        return int(match.group(1)) if match else 0
    
    sorted_qualities = sorted(available_qualities, key=get_resolution, reverse=True)
    
    target = normalize_quality(target)
    
    if target == "best":
        return sorted_qualities[0]
    elif target == "worst":
        return sorted_qualities[-1]
    elif target == "half":
        return sorted_qualities[len(sorted_qualities) // 2]
    else:
        # 尝试精确匹配
        target_res = get_resolution(target)
        for q in sorted_qualities:
            if get_resolution(q) == target_res:
                return q
        
        # 找最接近但不超过目标的
        for q in sorted_qualities:
            if get_resolution(q) <= target_res:
                return q
        
        # 返回最低质量
        return sorted_qualities[-1]


async def apply_mosaic(image_data: bytes, mosaic_level: int = 10) -> bytes:
    """
    对图片应用马赛克效果
    
    Args:
        image_data: 图片二进制数据
        mosaic_level: 马赛克程度 (1-100)，越大越模糊
        
    Returns:
        处理后的图片二进制数据
    """
    if not HAS_PIL:
        return image_data
    
    if mosaic_level <= 0:
        return image_data
    
    try:
        # 限制范围
        mosaic_level = max(1, min(100, mosaic_level))
        
        # 打开图片
        img = Image.open(BytesIO(image_data))
        original_size = img.size
        
        # 计算缩小比例
        scale = max(1, mosaic_level)
        small_size = (max(1, original_size[0] // scale), max(1, original_size[1] // scale))
        
        # 缩小再放大实现马赛克效果
        img = img.resize(small_size, Image.Resampling.NEAREST)
        img = img.resize(original_size, Image.Resampling.NEAREST)
        
        # 保存到字节流
        output = BytesIO()
        img_format = img.format or 'JPEG'
        img.save(output, format=img_format, quality=85)
        return output.getvalue()
    
    except Exception:
        return image_data


async def apply_blur(image_data: bytes, blur_radius: int = 10) -> bytes:
    """
    对图片应用模糊效果
    
    Args:
        image_data: 图片二进制数据
        blur_radius: 模糊半径
        
    Returns:
        处理后的图片二进制数据
    """
    if not HAS_PIL:
        return image_data
    
    if blur_radius <= 0:
        return image_data
    
    try:
        img = Image.open(BytesIO(image_data))
        img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        output = BytesIO()
        img_format = img.format or 'JPEG'
        img.save(output, format=img_format, quality=85)
        return output.getvalue()
    
    except Exception:
        return image_data


def get_temp_dir() -> str:
    """获取临时文件目录"""
    import tempfile
    temp_dir = os.path.join(tempfile.gettempdir(), "rule34video_cache")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def cleanup_temp_files(max_age_hours: int = 24):
    """
    清理临时文件
    
    Args:
        max_age_hours: 最大保留时间（小时）
    """
    import time
    
    temp_dir = get_temp_dir()
    if not os.path.exists(temp_dir):
        return
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    for filename in os.listdir(temp_dir):
        filepath = os.path.join(temp_dir, filename)
        try:
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    os.remove(filepath)
        except Exception:
            pass


def build_search_url(
    query: str = "",
    page: int = 1,
    sort: str = "latest",
    tags: List[str] = None,
    categories: List[str] = None
) -> str:
    """
    构建搜索URL
    
    Args:
        query: 搜索关键词
        page: 页码
        sort: 排序方式
        tags: 标签列表
        categories: 分类列表
        
    Returns:
        搜索URL
    """
    params = {}
    
    if query:
        params['q'] = query
    
    if page > 1:
        params['page'] = page
    
    if sort and sort != "latest":
        params['sort'] = sort
    
    if tags:
        params['tags'] = ','.join(tags)
    
    if categories:
        params['categories'] = ','.join(categories)
    
    base_url = f"{ROOT_URL}/search/"
    
    if params:
        return f"{base_url}?{urlencode(params)}"
    
    return base_url


def extract_tags_from_html(html_content: str) -> List[str]:
    """
    从HTML内容中提取标签
    
    Args:
        html_content: HTML内容
        
    Returns:
        标签列表
    """
    from .consts import REGEX_TAGS
    
    tags = []
    matches = REGEX_TAGS.findall(html_content)
    for match in matches:
        tag = clean_text(match)
        if tag and tag not in tags:
            tags.append(tag)
    
    return tags


def extract_categories_from_html(html_content: str) -> List[str]:
    """
    从HTML内容中提取分类
    
    Args:
        html_content: HTML内容
        
    Returns:
        分类列表
    """
    from .consts import REGEX_CATEGORIES
    
    categories = []
    matches = REGEX_CATEGORIES.findall(html_content)
    for match in matches:
        category = clean_text(match)
        if category and category not in categories:
            categories.append(category)
    
    return categories