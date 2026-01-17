
"""
Rule34Video API - Video 类
用于解析和获取单个视频的详细信息
"""

import re
import json
import logging
from typing import Optional, List, Dict, Any, Union
from functools import cached_property

from .consts import (
    ROOT_URL, HEADERS,
    REGEX_VIDEO_TITLE, REGEX_VIDEO_TITLE_ALT,
    REGEX_VIDEO_SOURCE, REGEX_VIDEO_SOURCE_ALT, REGEX_VIDEO_SOURCE_GENERIC,
    REGEX_VIDEO_SOURCE_720, REGEX_VIDEO_SOURCE_480, 
    REGEX_VIDEO_SOURCE_360, REGEX_VIDEO_SOURCE_1080, REGEX_VIDEO_SOURCE_2160,
    REGEX_QUALITY_FROM_URL,
    REGEX_THUMBNAIL, REGEX_THUMBNAIL_ALT, REGEX_PREVIEW_IMAGE, REGEX_THUMBNAIL_FLASHVARS,
    REGEX_DURATION, REGEX_DURATION_ALT, REGEX_DURATION_TEXT, REGEX_DURATION_SPAN,
    REGEX_VIEWS, REGEX_VIEWS_SPAN, REGEX_VIEWS_DIV, REGEX_VIEWS_DATA, REGEX_VIEWS_META,
    REGEX_LIKES, REGEX_LIKES_SPAN, REGEX_LIKES_DATA, REGEX_LIKES_BUTTON,
    REGEX_DISLIKES, REGEX_DISLIKES_SPAN, REGEX_DISLIKES_DATA,
    REGEX_UPLOAD_DATE, REGEX_DATE_ALT, REGEX_DATE_SPAN, REGEX_DATE_UPLOADED,
    REGEX_TAGS, REGEX_CATEGORIES,
    REGEX_UPLOADER, REGEX_UPLOADER_ALT, REGEX_UPLOADER_SPAN,
)
from .errors import VideoNotFound, InvalidURL, NetworkError
from .utils import (
    extract_video_id, build_video_url, clean_text,
    parse_duration, format_duration, parse_view_count,
    normalize_quality, select_best_quality
)


class Video:
    """
    Rule34Video 视频对象
    
    用于获取和解析单个视频的详细信息
    """
    
    def __init__(self, video_id: str, session=None, proxy: str = None, full_url: str = None):
        """
        初始化视频对象
        
        Args:
            video_id: 视频ID或URL
            session: aiohttp.ClientSession 实例
            proxy: 代理服务器地址
            full_url: 完整的视频URL（包含slug），优先使用
        """
        self._video_id = extract_video_id(video_id)
        if not self._video_id:
            raise InvalidURL(video_id, "无法从输入中提取视频ID")
        
        self._session = session
        self._proxy = proxy
        self._full_url = full_url  # 保存完整URL
        self._html_content: Optional[str] = None
        self._loaded = False
        self._quality_urls: Dict[str, str] = {}
        
        self.logger = logging.getLogger(f"Rule34Video.Video.{self._video_id}")
    
    @property
    def video_id(self) -> str:
        """视频ID"""
        return self._video_id
    
    @property
    def url(self) -> str:
        """视频页面URL"""
        # 优先返回完整URL
        if self._full_url:
            if self._full_url.startswith('http'):
                return self._full_url
            return f"{ROOT_URL}{self._full_url}"
        return build_video_url(self._video_id)
    
    def _get_url_variants(self) -> list:
        """获取所有可能的URL变体"""
        variants = []
        
        # 如果有完整URL，优先使用
        if self._full_url:
            # 判断是否已经是完整URL
            if self._full_url.startswith('http'):
                full_url = self._full_url
            else:
                full_url = f"{ROOT_URL}{self._full_url}"
            
            variants.append(full_url)
            
            # 也尝试 /videos/ 和 /video/ 的变体
            if '/videos/' in full_url:
                variants.append(full_url.replace('/videos/', '/video/'))
            elif '/video/' in full_url:
                variants.append(full_url.replace('/video/', '/videos/'))
        
        # 添加基于ID的变体作为备选
        variants.extend([
            f"{ROOT_URL}/video/{self._video_id}/",
            f"{ROOT_URL}/videos/{self._video_id}/",
            f"{ROOT_URL}/video/{self._video_id}",
            f"{ROOT_URL}/videos/{self._video_id}",
        ])
        
        # 去重但保持顺序
        seen = set()
        unique_variants = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                unique_variants.append(v)
        
        return unique_variants
    
    @property
    def is_loaded(self) -> bool:
        """是否已加载HTML内容"""
        return self._loaded and self._html_content is not None
    
    async def load(self, force: bool = False) -> bool:
        """
        加载视频页面内容
        
        Args:
            force: 是否强制重新加载
            
        Returns:
            是否加载成功
        """
        if self._loaded and not force:
            return True
        
        try:
            import aiohttp
            
            if self._session is None:
                connector = aiohttp.TCPConnector(ssl=False)
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    headers=HEADERS,
                    trust_env=True
                )
                self._own_session = True
            else:
                self._own_session = False
            
            # 尝试多种URL格式
            last_error = None
            url_variants = self._get_url_variants()
            
            for try_url in url_variants:
                try:
                    self.logger.debug(f"尝试加载URL: {try_url}")
                    async with self._session.get(
                        try_url,
                        proxy=self._proxy,
                        timeout=aiohttp.ClientTimeout(total=30),
                        allow_redirects=True
                    ) as response:
                        self.logger.debug(f"响应状态: {response.status}, URL: {response.url}")
                        
                        if response.status == 404:
                            self.logger.debug(f"404错误，跳过: {try_url}")
                            continue  # 尝试下一个URL
                        if response.status != 200:
                            self.logger.debug(f"非200响应 ({response.status})，跳过: {try_url}")
                            continue
                        
                        html_content = await response.text()
                        content_length = len(html_content)
                        self.logger.debug(f"获取到HTML内容，长度: {content_length}")
                        
                        # 检查页面是否是明确的错误页面
                        if "Video not found" in html_content:
                            self.logger.debug("页面包含'Video not found'，跳过")
                            continue
                        if "<title>404" in html_content or "Page not found" in html_content:
                            self.logger.debug("页面是404页面，跳过")
                            continue
                        
                        # 检查页面是否有最小内容
                        if content_length < 1000:
                            self.logger.debug(f"页面内容过短 ({content_length})，跳过")
                            continue
                        
                        # 检查是否是视频页面的各种特征
                        is_video_page = False
                        
                        video_indicators = [
                            '<video', 'video_url', 'sources', 'og:video',
                            'player', 'video-player', 'video_player',
                            'kt_player', 'flashvars', '.mp4', 'video/mp4',
                            'uploadDate', 'duration',
                        ]
                        
                        for indicator in video_indicators:
                            if indicator.lower() in html_content.lower():
                                is_video_page = True
                                self.logger.debug(f"找到视频指标: {indicator}")
                                break
                        
                        if is_video_page or content_length > 5000:
                            self._html_content = html_content
                            self._loaded = True
                            self._parse_quality_urls()
                            self.logger.debug(f"成功加载视频页面，质量选项: {list(self._quality_urls.keys())}")
                            return True
                        else:
                            self.logger.debug("未找到视频页面特征，继续尝试")
                            
                except aiohttp.ClientError as e:
                    self.logger.debug(f"请求错误: {e}")
                    last_error = e
                    continue
            
            # 所有URL都失败了
            self.logger.warning(f"所有URL变体都失败了: {url_variants}")
            if last_error:
                raise NetworkError(str(last_error))
            raise VideoNotFound(self._video_id)
                
        except aiohttp.ClientError as e:
            self.logger.error(f"aiohttp错误: {e}")
            raise NetworkError(str(e))
    
    async def close(self):
        """关闭会话"""
        if hasattr(self, '_own_session') and self._own_session and self._session:
            await self._session.close()
            self._session = None
    
    def _ensure_loaded(self):
        """确保内容已加载"""
        if not self._loaded:
            raise RuntimeError("视频内容未加载，请先调用 load() 方法")
    
    def _clean_video_url(self, url: str) -> Optional[str]:
        """清理视频URL，移除无效前缀"""
        if not url:
            return None
        
        url = url.strip()
        
        # 移除 "function/数字/" 前缀
        func_match = re.match(r'^function/\d+/(https?://.*)', url)
        if func_match:
            url = func_match.group(1)
        
        # 处理可能的双斜杠问题
        url = re.sub(r'([^:])//+', r'\1/', url)
        
        # 确保是有效的URL
        if url.startswith('http://') or url.startswith('https://'):
            return url
        elif url.startswith('//'):
            return 'https:' + url
        elif url.startswith('/'):
            return f"{ROOT_URL}{url}"
        
        return url
    
    def _extract_quality_from_url(self, url: str) -> str:
        """从URL中提取质量标签"""
        if not url:
            return "default"
        
        patterns = [
            r'[_/](\d{3,4})p?\.mp4',
            r'[_/](\d{3,4})p[_/]',
            r'[_/](\d{3,4})[_/]',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                res = match.group(1)
                return f"{res}p"
        
        return "default"
    
    def _parse_quality_urls(self):
        """解析所有可用的视频质量URL"""
        if not self._html_content:
            return
        
        content = self._html_content
        self.logger.debug("开始解析视频质量URL")
        
        # 方法1: 尝试解析 flashvars 配置
        flashvars_match = re.search(r'flashvars\s*=\s*\{([^}]+)\}', content, re.DOTALL)
        if flashvars_match:
            flashvars_content = flashvars_match.group(1)
            self.logger.debug(f"找到 flashvars")
            
            # 提取 video_url 和 video_url_text
            video_url_match = re.search(r"video_url\s*:\s*['\"]([^'\"]+)['\"]", flashvars_content)
            if video_url_match:
                url = self._clean_video_url(video_url_match.group(1))
                if url:
                    quality_match = re.search(r"video_url_text\s*:\s*['\"]([^'\"]+)['\"]", flashvars_content)
                    quality = quality_match.group(1) if quality_match else "default"
                    quality = quality.strip()
                    self._quality_urls[quality] = url
                    self.logger.debug(f"从flashvars提取: {quality}")
            
            # 提取多个质量版本
            alt_patterns = [
                (r"video_alt_url\s*:\s*['\"]([^'\"]+)['\"]", r"video_alt_url_text\s*:\s*['\"]([^'\"]+)['\"]"),
                (r"video_alt_url2\s*:\s*['\"]([^'\"]+)['\"]", r"video_alt_url2_text\s*:\s*['\"]([^'\"]+)['\"]"),
                (r"video_alt_url3\s*:\s*['\"]([^'\"]+)['\"]", r"video_alt_url3_text\s*:\s*['\"]([^'\"]+)['\"]"),
            ]
            
            for url_pattern, text_pattern in alt_patterns:
                url_match = re.search(url_pattern, flashvars_content)
                if url_match:
                    url = self._clean_video_url(url_match.group(1))
                    if url:
                        text_match = re.search(text_pattern, flashvars_content)
                        quality = text_match.group(1).strip() if text_match else "alt"
                        self._quality_urls[quality] = url
        
        # 方法2: 尝试解析 kt_player 配置
        kt_player_match = re.search(r"kt_player\s*\([^)]+\)", content)
        if kt_player_match:
            kt_content = kt_player_match.group(0)
            url_matches = re.findall(r"(https?://[^'\"]+\.mp4[^'\"]*)", kt_content)
            for url in url_matches:
                url = self._clean_video_url(url)
                if url:
                    quality = self._extract_quality_from_url(url)
                    self._quality_urls[quality] = url
        
        # 方法3: 尝试解析JSON格式的 sources 配置
        json_patterns = [
            r'sources\s*:\s*(\[[^\]]+\])',
            r'"sources"\s*:\s*(\[[^\]]+\])',
        ]
        
        for pattern in json_patterns:
            json_match = re.search(pattern, content, re.DOTALL)
            if json_match:
                try:
                    json_str = json_match.group(1)
                    json_str = re.sub(r"'([^']*)'", r'"\1"', json_str)
                    sources = json.loads(json_str)
                    for source in sources:
                        if isinstance(source, dict):
                            label = source.get('label', source.get('quality', source.get('res', '')))
                            src = source.get('src', source.get('file', source.get('url', '')))
                            if src:
                                src = self._clean_video_url(src)
                                if src:
                                    quality = str(label) if label else self._extract_quality_from_url(src)
                                    self._quality_urls[quality] = src
                        elif isinstance(source, str):
                            src = self._clean_video_url(source)
                            if src:
                                quality = self._extract_quality_from_url(src)
                                self._quality_urls[quality] = src
                except (json.JSONDecodeError, Exception):
                    pass
        
        # 方法4: 尝试解析HTML5 video source标签
        source_matches = re.findall(
            r'<source[^>]+src=["\']([^"\']+)["\'][^>]*(?:label=["\']([^"\']+)["\'])?',
            content, re.IGNORECASE
        )
        for match in source_matches:
            url = match[0]
            quality = match[1] if len(match) > 1 else ""
            
            if url and '.mp4' in url:
                url = self._clean_video_url(url)
                if url:
                    if not quality:
                        quality = self._extract_quality_from_url(url)
                    self._quality_urls[quality] = url
        
        # 方法5: 使用预定义的质量正则表达式
        quality_patterns = [
            (REGEX_VIDEO_SOURCE_2160, "2160p"),
            (REGEX_VIDEO_SOURCE_1080, "1080p"),
            (REGEX_VIDEO_SOURCE_720, "720p"),
            (REGEX_VIDEO_SOURCE_480, "480p"),
            (REGEX_VIDEO_SOURCE_360, "360p"),
        ]
        
        for pattern, quality in quality_patterns:
            if quality not in self._quality_urls:
                match = pattern.search(content)
                if match:
                    url = self._clean_video_url(match.group(1))
                    if url:
                        self._quality_urls[quality] = url
        
        # 方法6: 直接搜索.mp4 URL
        if not self._quality_urls:
            mp4_urls = re.findall(r'(https?://[^"\'\s<>]+\.mp4[^"\'\s<>]*)', content)
            seen_urls = set()
            for url in mp4_urls:
                url = self._clean_video_url(url)
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    quality = self._extract_quality_from_url(url)
                    if quality not in self._quality_urls:
                        self._quality_urls[quality] = url
        
        # 方法7: 使用通用视频源正则
        if not self._quality_urls:
            match = REGEX_VIDEO_SOURCE.search(content)
            if match:
                url = self._clean_video_url(match.group(1))
                if url:
                    self._quality_urls["default"] = url
            else:
                match = REGEX_VIDEO_SOURCE_ALT.search(content)
                if match:
                    url = self._clean_video_url(match.group(1))
                    if url:
                        self._quality_urls["default"] = url
                else:
                    match = REGEX_VIDEO_SOURCE_GENERIC.search(content)
                    if match:
                        url = self._clean_video_url(match.group(1))
                        if url:
                            self._quality_urls["default"] = url
        
        self.logger.debug(f"解析完成，找到 {len(self._quality_urls)} 个质量选项")
    
    @cached_property
    def title(self) -> str:
        """视频标题"""
        self._ensure_loaded()
        
        # 尝试从meta标签获取
        match = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', self._html_content, re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
        
        # 尝试从h1标签获取
        match = REGEX_VIDEO_TITLE.search(self._html_content)
        if match:
            return clean_text(match.group(1))
        
        # 尝试从title标签获取
        match = REGEX_VIDEO_TITLE_ALT.search(self._html_content)
        if match:
            title = clean_text(match.group(1))
            title = re.sub(r'\s*[-|]\s*Rule34Video.*$', '', title, flags=re.IGNORECASE)
            return title
        
        return f"Video {self._video_id}"
    
    @cached_property
    def thumbnail(self) -> Optional[str]:
        """视频缩略图URL"""
        self._ensure_loaded()
        
        patterns = [
            REGEX_THUMBNAIL,
            REGEX_THUMBNAIL_ALT,
            REGEX_PREVIEW_IMAGE,
            REGEX_THUMBNAIL_FLASHVARS,
        ]
        
        for pattern in patterns:
            match = pattern.search(self._html_content)
            if match:
                url = match.group(1)
                if url:
                    if url.startswith('//'):
                        url = 'https:' + url
                    elif url.startswith('/'):
                        url = f"{ROOT_URL}{url}"
                    return url
        
        # 尝试从 flashvars 提取
        flashvars_match = re.search(r'flashvars\s*=\s*\{([^}]+)\}', self._html_content, re.DOTALL)
        if flashvars_match:
            preview_match = re.search(r"(?:preview_url|thumb|poster)\s*:\s*['\"]([^'\"]+)['\"]", flashvars_match.group(1))
            if preview_match:
                url = preview_match.group(1)
                if url.startswith('//'):
                    url = 'https:' + url
                elif url.startswith('/'):
                    url = f"{ROOT_URL}{url}"
                return url
        
        return None
    
    @cached_property
    def preview_image(self) -> Optional[str]:
        """预览图片URL (同thumbnail)"""
        return self.thumbnail
    
    @cached_property
    def duration(self) -> int:
        """视频时长（秒）"""
        self._ensure_loaded()
        
        match = REGEX_DURATION.search(self._html_content)
        if match:
            return parse_duration(match.group(1))
        
        match = REGEX_DURATION_SPAN.search(self._html_content)
        if match:
            return parse_duration(match.group(1))
        
        match = REGEX_DURATION_ALT.search(self._html_content)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        
        match = REGEX_DURATION_TEXT.search(self._html_content)
        if match:
            return parse_duration(match.group(1))
        
        # 尝试从 flashvars 提取
        flashvars_match = re.search(r'flashvars\s*=\s*\{([^}]+)\}', self._html_content, re.DOTALL)
        if flashvars_match:
            duration_match = re.search(r"duration\s*:\s*['\"]?(\d+)['\"]?", flashvars_match.group(1))
            if duration_match:
                return int(duration_match.group(1))
        
        return 0
    
    @property
    def duration_formatted(self) -> str:
        """格式化的视频时长"""
        return format_duration(self.duration)
    
    def _get_flashvars(self) -> Optional[str]:
        """获取flashvars内容（缓存）"""
        if not hasattr(self, '_flashvars_cache'):
            flashvars_match = re.search(r'flashvars\s*=\s*\{([^}]+)\}', self._html_content, re.DOTALL)
            self._flashvars_cache = flashvars_match.group(1) if flashvars_match else None
        return self._flashvars_cache
    
    def _get_flashvar_value(self, key: str) -> Optional[str]:
        """从flashvars中获取指定键的值"""
        flashvars = self._get_flashvars()
        if not flashvars:
            return None
        
        # 支持多种格式: key: 'value', key: "value", key: value
        patterns = [
            rf"{key}\s*:\s*['\"]([^'\"]+)['\"]",  # 带引号
            rf"{key}\s*:\s*(\d+)",  # 纯数字
        ]
        
        for pattern in patterns:
            match = re.search(pattern, flashvars, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    @cached_property
    def views(self) -> int:
        """观看次数"""
        self._ensure_loaded()
        
        # 优先从 flashvars 提取
        flashvars_views = self._get_flashvar_value('views')
        if flashvars_views:
            try:
                return int(flashvars_views)
            except ValueError:
                pass
        
        # 尝试多种正则模式
        patterns = [
            REGEX_VIEWS_DATA,
            REGEX_VIEWS_META,
            REGEX_VIEWS_SPAN,
            REGEX_VIEWS_DIV,
            REGEX_VIEWS,
        ]
        
        for pattern in patterns:
            match = pattern.search(self._html_content)
            if match:
                count = parse_view_count(match.group(1))
                if count > 0:
                    return count
        
        return 0
    
    @cached_property
    def likes(self) -> int:
        """点赞数"""
        self._ensure_loaded()
        
        # 优先从 flashvars 提取
        flashvars_likes = self._get_flashvar_value('likes')
        if flashvars_likes:
            try:
                return int(flashvars_likes)
            except ValueError:
                pass
        
        # 尝试从HTML中查找投票按钮相关的数字
        # 常见格式: <span class="votes">123</span> 或 data-votes="123"
        vote_patterns = [
            r'class="[^"]*like[^"]*"[^>]*>\s*(\d+)',  # class="like...">123
            r'id="[^"]*like[^"]*"[^>]*>\s*(\d+)',  # id="like...">123
            r'data-(?:likes?|votes?|count)="(\d+)"',  # data-likes="123"
            r'>\s*(\d+)\s*</[^>]*>.*?(?:like|thumb[^s]|up)',  # >123</span>...like
        ]
        
        for pattern in vote_patterns:
            match = re.search(pattern, self._html_content, re.IGNORECASE)
            if match:
                count = int(match.group(1))
                if count > 0:
                    return count
        
        # 使用预定义正则
        patterns = [
            REGEX_LIKES_DATA,
            REGEX_LIKES_SPAN,
            REGEX_LIKES_BUTTON,
            REGEX_LIKES,
        ]
        
        for pattern in patterns:
            match = pattern.search(self._html_content)
            if match:
                count = parse_view_count(match.group(1))
                if count > 0:
                    return count
        
        return 0
    
    @cached_property
    def dislikes(self) -> int:
        """踩数"""
        self._ensure_loaded()
        
        # 优先从 flashvars 提取
        flashvars_dislikes = self._get_flashvar_value('dislikes')
        if flashvars_dislikes:
            try:
                return int(flashvars_dislikes)
            except ValueError:
                pass
        
        # 尝试从HTML中查找
        vote_patterns = [
            r'class="[^"]*dislike[^"]*"[^>]*>\s*(\d+)',
            r'id="[^"]*dislike[^"]*"[^>]*>\s*(\d+)',
            r'data-(?:dislikes?|down)="(\d+)"',
            r'>\s*(\d+)\s*</[^>]*>.*?(?:dislike|down)',
        ]
        
        for pattern in vote_patterns:
            match = re.search(pattern, self._html_content, re.IGNORECASE)
            if match:
                count = int(match.group(1))
                if count > 0:
                    return count
        
        # 使用预定义正则
        patterns = [
            REGEX_DISLIKES_DATA,
            REGEX_DISLIKES_SPAN,
            REGEX_DISLIKES,
        ]
        
        for pattern in patterns:
            match = pattern.search(self._html_content)
            if match:
                count = parse_view_count(match.group(1))
                if count > 0:
                    return count
        
        return 0
    
    @cached_property
    def rating(self) -> float:
        """评分 (0-100)"""
        total = self.likes + self.dislikes
        if total == 0:
            return 0.0
        return round((self.likes / total) * 100, 2)
    
    @cached_property
    def upload_date(self) -> Optional[str]:
        """上传日期"""
        self._ensure_loaded()
        
        # 优先从 flashvars 提取（最准确）
        flashvars_match = re.search(r'flashvars\s*=\s*\{([^}]+)\}', self._html_content, re.DOTALL)
        if flashvars_match:
            # 尝试多种日期键名
            date_patterns = [
                r"(?:upload_date|date|post_date|added|created)\s*:\s*['\"]([^'\"]+)['\"]",
            ]
            for pattern in date_patterns:
                date_match = re.search(pattern, flashvars_match.group(1), re.IGNORECASE)
                if date_match:
                    date_str = clean_text(date_match.group(1))
                    # 验证是否是有效日期格式
                    if date_str and not date_str.lower().startswith('by'):
                        return date_str
        
        # 从meta标签获取
        match = REGEX_UPLOAD_DATE.search(self._html_content)
        if match:
            date_str = clean_text(match.group(1))
            if date_str and len(date_str) > 4 and not date_str.lower().startswith('by'):
                return date_str
        
        # 从HTML中查找日期格式
        # 匹配常见日期格式: 2024-01-15, Jan 15 2024, 15 Jan 2024, etc.
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # 2024-01-15
            r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})',  # 15 Jan 2024
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})',  # Jan 15, 2024
            r'(\d{1,2}/\d{1,2}/\d{4})',  # 01/15/2024
            r'(\d{1,2}\.\d{1,2}\.\d{4})',  # 15.01.2024
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, self._html_content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    @cached_property
    def uploader(self) -> Optional[str]:
        """上传者"""
        self._ensure_loaded()
        
        patterns = [
            REGEX_UPLOADER,
            REGEX_UPLOADER_SPAN,
            REGEX_UPLOADER_ALT,
        ]
        
        for pattern in patterns:
            match = pattern.search(self._html_content)
            if match:
                uploader = clean_text(match.group(1))
                if uploader:
                    return uploader
        
        # 尝试从 flashvars 提取
        flashvars_match = re.search(r'flashvars\s*=\s*\{([^}]+)\}', self._html_content, re.DOTALL)
        if flashvars_match:
            uploader_match = re.search(r"(?:uploader|author|user)\s*:\s*['\"]([^'\"]+)['\"]", flashvars_match.group(1))
            if uploader_match:
                return clean_text(uploader_match.group(1))
        
        return None
    
    @cached_property
    def tags(self) -> List[str]:
        """标签列表"""
        self._ensure_loaded()
        
        tags = []
        matches = REGEX_TAGS.findall(self._html_content)
        for match in matches:
            tag = clean_text(match)
            if tag and tag not in tags:
                tags.append(tag)
        
        return tags
    
    @cached_property
    def categories(self) -> List[str]:
        """分类列表"""
        self._ensure_loaded()
        
        categories = []
        matches = REGEX_CATEGORIES.findall(self._html_content)
        for match in matches:
            category = clean_text(match)
            if category and category not in categories:
                categories.append(category)
        
        return categories
    
    @property
    def available_qualities(self) -> List[str]:
        """可用的视频质量列表"""
        self._ensure_loaded()
        return list(self._quality_urls.keys())
    
    def get_video_url(self, quality: Union[str, int] = "best") -> Optional[str]:
        """
        获取指定质量的视频URL
        
        Args:
            quality: 质量参数，如 "720p", 720, "best", "worst"
            
        Returns:
            视频URL
        """
        self._ensure_loaded()
        
        if not self._quality_urls:
            return None
        
        quality = normalize_quality(quality)
        
        # 尝试精确匹配
        if quality in self._quality_urls:
            return self._quality_urls[quality]
        
        # 使用选择算法
        selected = select_best_quality(list(self._quality_urls.keys()), quality)
        if selected:
            return self._quality_urls.get(selected)
        
        # 返回第一个可用的
        return next(iter(self._quality_urls.values()), None)
    
    @property
    def direct_url(self) -> Optional[str]:
        """最佳质量的直接下载URL"""
        return self.get_video_url("best")
    
    @property
    def source_url(self) -> Optional[str]:
        """视频源URL (同direct_url)"""
        return self.direct_url
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将视频信息转换为字典
        
        Returns:
            包含视频信息的字典
        """
        self._ensure_loaded()
        
        return {
            "video_id": self.video_id,
            "url": self.url,
            "title": self.title,
            "thumbnail": self.thumbnail,
            "duration": self.duration,
            "duration_formatted": self.duration_formatted,
            "views": self.views,
            "likes": self.likes,
            "dislikes": self.dislikes,
            "rating": self.rating,
            "upload_date": self.upload_date,
            "uploader": self.uploader,
            "tags": self.tags,
            "categories": self.categories,
            "available_qualities": self.available_qualities,
            "direct_url": self.direct_url,
        }
    
    def __repr__(self) -> str:
        return f"<Video id={self._video_id} loaded={self._loaded}>"
    
    def __str__(self) -> str:
        if self._loaded:
            return f"Video: {self.title} ({self.video_id})"
        return f"Video: {self._video_id} (not loaded)"