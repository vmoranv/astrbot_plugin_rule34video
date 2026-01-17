"""
Rule34Video API - Client 类
主要的API客户端，用于搜索视频和获取视频信息
"""

import re
import asyncio
import logging
from typing import List, Dict, Any, Union

from .consts import (
    ROOT_URL, HEADERS, SortOrder
)
from .errors import NetworkError, VideoNotFound
from .video import Video
from .utils import (
    clean_text
)


class Client:
    """
    Rule34Video API 客户端
    
    用于搜索视频、获取分类列表等功能
    """
    
    def __init__(self, proxy: str = None, timeout: int = 30):
        """
        初始化客户端
        
        Args:
            proxy: 代理服务器地址，如 "http://127.0.0.1:7890"
            timeout: 请求超时时间（秒）
        """
        self._proxy = proxy
        self._timeout = timeout
        self._session = None
        self._own_session = False
        
        self.logger = logging.getLogger("Rule34Video.Client")
    
    async def _ensure_session(self):
        """确保会话已创建"""
        if self._session is None:
            import aiohttp
            
            connector = aiohttp.TCPConnector(ssl=False, limit=10)
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers=HEADERS,
                timeout=timeout,
                trust_env=True
            )
            self._own_session = True
    
    async def close(self):
        """关闭客户端会话"""
        if self._own_session and self._session:
            await self._session.close()
            self._session = None
    
    async def __aenter__(self):
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _fetch(self, url: str) -> str:
        """
        获取页面内容
        
        Args:
            url: 页面URL
            
        Returns:
            页面HTML内容
        """
        await self._ensure_session()
        
        try:
            async with self._session.get(url, proxy=self._proxy) as response:
                if response.status == 404:
                    raise VideoNotFound(message=f"Page not found: {url}")
                if response.status != 200:
                    raise NetworkError(f"HTTP {response.status}", response.status)
                
                return await response.text()
                
        except Exception as e:
            if isinstance(e, (VideoNotFound, NetworkError)):
                raise
            raise NetworkError(str(e))
    
    async def get_video(self, video_id: str, full_url: str = None) -> Video:
        """
        获取视频对象
        
        Args:
            video_id: 视频ID或URL
            full_url: 完整的视频URL（包含slug）
            
        Returns:
            Video对象
        """
        await self._ensure_session()
        
        video = Video(video_id, session=self._session, proxy=self._proxy, full_url=full_url)
        await video.load()
        
        return video
    
    async def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """
        获取视频信息字典
        
        Args:
            video_id: 视频ID或URL
            
        Returns:
            视频信息字典
        """
        video = await self.get_video(video_id)
        return video.to_dict()
    
    async def search(
        self,
        query: str = "",
        page: int = 1,
        sort: str = SortOrder.LATEST,
        tags: List[str] = None,
        max_results: int = 20
    ) -> List[Dict[str, str]]:
        """
        搜索视频
        
        Args:
            query: 搜索关键词
            page: 页码
            sort: 排序方式
            tags: 标签过滤
            max_results: 最大结果数
            
        Returns:
            搜索结果列表，每个结果包含 video_id, url 和 full_path
        """
        # 构建搜索URL - 使用正确的搜索路径
        from urllib.parse import quote
        
        if query:
            # 尝试多种搜索URL格式
            encoded_query = quote(query)
            search_url = f"{ROOT_URL}/search/{encoded_query}/"
        else:
            search_url = ROOT_URL
        
        if page > 1:
            search_url += f"?from={page}" if "?" not in search_url else f"&from={page}"
        
        if sort and sort != SortOrder.LATEST:
            sep = "&" if "?" in search_url else "?"
            search_url += f"{sep}sort_by={sort}"
        
        if tags:
            for tag in tags:
                sep = "&" if "?" in search_url else "?"
                search_url += f"{sep}tag[]={tag}"
        
        self.logger.debug(f"搜索URL: {search_url}")
        html_content = await self._fetch(search_url)
        self.logger.debug(f"搜索返回内容长度: {len(html_content)}")
        
        # 解析搜索结果 - 需要保存完整的URL路径（包括slug）
        results = []
        seen_ids = set()
        
        # 多种正则模式提取完整的视频链接
        # 模式1: href属性中的完整链接 (带slug)
        patterns = [
            # 标准格式: href="/video/123456/title-here/"
            r'href=["\'](/videos?/(\d+)/([^"\']+))["\']',
            # 完整URL格式: href="https://rule34video.com/video/123456/title/"
            r'href=["\'](?:https?://[^/]+)?(/videos?/(\d+)/([^"\']+))["\']',
        ]
        
        for pattern in patterns:
            full_matches = re.findall(pattern, html_content, re.IGNORECASE)
            self.logger.debug(f"模式 {pattern[:30]}... 匹配到 {len(full_matches)} 个结果")
            
            for full_path, video_id, slug in full_matches:
                if video_id and video_id.isdigit() and video_id not in seen_ids and len(results) < max_results:
                    seen_ids.add(video_id)
                    # 规范化路径：确保使用 /video/ 格式
                    if full_path.startswith('/videos/'):
                        normalized_path = full_path.replace('/videos/', '/video/', 1)
                    else:
                        normalized_path = full_path
                    # 确保路径以/结尾
                    if not normalized_path.endswith('/'):
                        normalized_path += '/'
                    results.append({
                        "video_id": video_id,
                        "url": f"{ROOT_URL}{normalized_path}",
                        "full_path": normalized_path,
                        "slug": slug.rstrip('/')
                    })
                    self.logger.debug(f"找到视频: ID={video_id}, path={normalized_path}")
            
            if results:
                break  # 如果找到结果就停止
        
        # 如果没有找到带slug的链接，尝试从data-video-id或其他属性提取
        if not results:
            self.logger.debug("未找到带slug的链接，尝试其他方法")
            
            # 尝试从缩略图链接提取
            thumb_pattern = r'<a[^>]+href=["\']([^"\']*?/videos?/(\d+)/[^"\']*)["\'][^>]*>'
            thumb_matches = re.findall(thumb_pattern, html_content, re.IGNORECASE | re.DOTALL)
            
            for full_path, video_id in thumb_matches:
                if video_id and video_id.isdigit() and video_id not in seen_ids and len(results) < max_results:
                    seen_ids.add(video_id)
                    # 提取路径部分
                    if full_path.startswith('http'):
                        # 从完整URL提取路径
                        path_match = re.search(r'/videos?/\d+/[^"\']*', full_path)
                        if path_match:
                            normalized_path = path_match.group(0)
                        else:
                            normalized_path = f"/video/{video_id}/"
                    else:
                        normalized_path = full_path
                    
                    if '/videos/' in normalized_path:
                        normalized_path = normalized_path.replace('/videos/', '/video/', 1)
                    if not normalized_path.endswith('/'):
                        normalized_path += '/'
                    
                    results.append({
                        "video_id": video_id,
                        "url": f"{ROOT_URL}{normalized_path}",
                        "full_path": normalized_path,
                        "slug": None
                    })
        
        # 最后的备选：只提取ID（这种情况下URL可能无法访问）
        if not results:
            self.logger.debug("使用备选方法：只提取ID")
            id_pattern = r'/videos?/(\d+)(?:/|["\'])'
            id_matches = re.findall(id_pattern, html_content, re.IGNORECASE)
            
            for video_id in id_matches:
                if video_id and video_id.isdigit() and video_id not in seen_ids and len(results) < max_results:
                    seen_ids.add(video_id)
                    results.append({
                        "video_id": video_id,
                        "url": f"{ROOT_URL}/video/{video_id}/",
                        "full_path": f"/video/{video_id}/",
                        "slug": None
                    })
        
        self.logger.debug(f"搜索到 {len(results)} 个视频")
        return results
    
    async def search_videos(
        self,
        query: str = "",
        page: int = 1,
        sort: str = SortOrder.LATEST,
        max_results: int = 10,
        load_details: bool = False
    ) -> List[Union[Dict[str, str], Video]]:
        """
        搜索视频并可选加载详细信息
        
        Args:
            query: 搜索关键词
            page: 页码
            sort: 排序方式
            max_results: 最大结果数
            load_details: 是否加载视频详细信息
            
        Returns:
            搜索结果列表
        """
        results = await self.search(query, page, sort, max_results=max_results)
        
        if not load_details:
            return results
        
        # 并发加载视频详情
        videos = []
        tasks = [self.get_video(r["video_id"]) for r in results]
        
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result, video_or_error in zip(results, completed):
            if isinstance(video_or_error, Exception):
                self.logger.warning(f"Failed to load video {result['video_id']}: {video_or_error}")
            else:
                videos.append(video_or_error)
        
        return videos
    
    async def get_random_video(self) -> Video:
        """
        获取随机视频
        
        Returns:
            随机视频对象
        """
        import random as random_module
        
        # 尝试多种获取随机视频的方式
        random_urls = [
            f"{ROOT_URL}/?random=1",
            ROOT_URL,  # 从首页随机选择
        ]
        
        all_videos = []  # 保存 (video_id, full_path) 元组
        
        for random_url in random_urls:
            try:
                self.logger.debug(f"尝试获取随机视频从: {random_url}")
                html_content = await self._fetch(random_url)
                
                # 使用与search相同的正则模式提取完整的视频链接
                full_link_pattern = r'href=["\'](?:https?://[^/]+)?(/videos?/(\d+)/([^"\']+))["\']'
                full_matches = re.findall(full_link_pattern, html_content, re.IGNORECASE)
                
                self.logger.debug(f"从 {random_url} 找到 {len(full_matches)} 个完整视频链接")
                
                seen_ids = set()
                for full_path, video_id, slug in full_matches:
                    if video_id not in seen_ids:
                        seen_ids.add(video_id)
                        # 规范化路径
                        if full_path.startswith('/videos/'):
                            normalized_path = full_path.replace('/videos/', '/video/', 1)
                        else:
                            normalized_path = full_path
                        # 确保路径以/结尾
                        if not normalized_path.endswith('/'):
                            normalized_path += '/'
                        all_videos.append((video_id, normalized_path))
                        
            except Exception as e:
                self.logger.debug(f"获取随机视频失败 ({random_url}): {e}")
                continue
        
        if all_videos:
            video_id, full_path = random_module.choice(all_videos)
            full_url = f"{ROOT_URL}{full_path}"
            self.logger.debug(f"随机选择视频: ID={video_id}, URL={full_url}")
            return await self.get_video(video_id, full_url=full_url)
        
        self.logger.warning("无法找到任何随机视频")
        raise VideoNotFound(message="No random video found")
    
    async def get_latest_videos(self, count: int = 10) -> List[Video]:
        """
        获取最新视频
        
        Args:
            count: 获取数量
            
        Returns:
            视频对象列表
        """
        results = await self.search(sort=SortOrder.LATEST, max_results=count)
        
        videos = []
        for result in results:
            try:
                video = await self.get_video(result["video_id"])
                videos.append(video)
            except Exception as e:
                self.logger.warning(f"Failed to load video {result['video_id']}: {e}")
        
        return videos
    
    async def get_popular_videos(self, count: int = 10) -> List[Video]:
        """
        获取热门视频
        
        Args:
            count: 获取数量
            
        Returns:
            视频对象列表
        """
        results = await self.search(sort=SortOrder.MOST_VIEWED, max_results=count)
        
        videos = []
        for result in results:
            try:
                video = await self.get_video(result["video_id"])
                videos.append(video)
            except Exception as e:
                self.logger.warning(f"Failed to load video {result['video_id']}: {e}")
        
        return videos
    
    async def get_categories(self) -> List[Dict[str, str]]:
        """
        获取所有分类
        
        Returns:
            分类列表
        """
        html_content = await self._fetch(f"{ROOT_URL}/categories/")
        
        categories = []
        
        # 提取分类链接
        cat_links = re.findall(
            r'<a[^>]+href="/categories/([^"/]+)/"[^>]*>([^<]+)</a>',
            html_content,
            re.IGNORECASE
        )
        
        seen = set()
        for slug, name in cat_links:
            if slug not in seen:
                seen.add(slug)
                categories.append({
                    "slug": slug,
                    "name": clean_text(name),
                    "url": f"{ROOT_URL}/categories/{slug}/"
                })
        
        return categories
    
    async def get_tags(self, page: int = 1) -> List[Dict[str, str]]:
        """
        获取标签列表
        
        Args:
            page: 页码
            
        Returns:
            标签列表
        """
        url = f"{ROOT_URL}/tags/"
        if page > 1:
            url += f"?page={page}"
        
        html_content = await self._fetch(url)
        
        tags = []
        
        # 提取标签链接
        tag_links = re.findall(
            r'<a[^>]+href="/tags/([^"/]+)/"[^>]*>([^<]+)</a>',
            html_content,
            re.IGNORECASE
        )
        
        seen = set()
        for slug, name in tag_links:
            if slug not in seen:
                seen.add(slug)
                tags.append({
                    "slug": slug,
                    "name": clean_text(name),
                    "url": f"{ROOT_URL}/tags/{slug}/"
                })
        
        return tags
    
    async def get_videos_by_category(
        self,
        category: str,
        page: int = 1,
        max_results: int = 20
    ) -> List[Dict[str, str]]:
        """
        获取分类下的视频
        
        Args:
            category: 分类slug
            page: 页码
            max_results: 最大结果数
            
        Returns:
            视频列表
        """
        url = f"{ROOT_URL}/categories/{category}/"
        if page > 1:
            url += f"?page={page}"
        
        html_content = await self._fetch(url)
        
        results = []
        seen_ids = set()
        
        # 提取完整的视频链接（包含slug）
        full_link_pattern = r'href="(/videos?/(\d+)/([^"]+))"'
        full_matches = re.findall(full_link_pattern, html_content, re.IGNORECASE)
        
        for full_path, video_id, slug in full_matches:
            if video_id not in seen_ids and len(results) < max_results:
                seen_ids.add(video_id)
                if full_path.startswith('/videos/'):
                    normalized_path = full_path.replace('/videos/', '/video/', 1)
                else:
                    normalized_path = full_path
                results.append({
                    "video_id": video_id,
                    "url": f"{ROOT_URL}{normalized_path}",
                    "full_path": normalized_path,
                    "slug": slug.rstrip('/')
                })
        
        return results
    
    async def get_videos_by_tag(
        self,
        tag: str,
        page: int = 1,
        max_results: int = 20
    ) -> List[Dict[str, str]]:
        """
        获取标签下的视频
        
        Args:
            tag: 标签slug
            page: 页码
            max_results: 最大结果数
            
        Returns:
            视频列表
        """
        url = f"{ROOT_URL}/tags/{tag}/"
        if page > 1:
            url += f"?page={page}"
        
        html_content = await self._fetch(url)
        
        results = []
        seen_ids = set()
        
        # 提取完整的视频链接（包含slug）
        full_link_pattern = r'href="(/videos?/(\d+)/([^"]+))"'
        full_matches = re.findall(full_link_pattern, html_content, re.IGNORECASE)
        
        for full_path, video_id, slug in full_matches:
            if video_id not in seen_ids and len(results) < max_results:
                seen_ids.add(video_id)
                if full_path.startswith('/videos/'):
                    normalized_path = full_path.replace('/videos/', '/video/', 1)
                else:
                    normalized_path = full_path
                results.append({
                    "video_id": video_id,
                    "url": f"{ROOT_URL}{normalized_path}",
                    "full_path": normalized_path,
                    "slug": slug.rstrip('/')
                })
        
        return results
    
    def __repr__(self) -> str:
        return f"<Rule34VideoClient proxy={self._proxy}>"