"""
Rule34Video AstrBot 插件
用于获取和解析 rule34video.com 的视频信息
"""

import os
from typing import Optional

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp

from .modules.client import Client
from .modules.errors import VideoNotFound, NetworkError, InvalidURL
from .modules.utils import (
    apply_mosaic, apply_blur, cleanup_temp_files,
    get_temp_dir
)


@register("rule34video", "Rule34Video Plugin", "Rule34Video.com 视频解析插件", "1.0.0")
class Rule34VideoPlugin(Star):
    """Rule34Video 插件主类"""

    def __init__(self, context: Context):
        super().__init__(context)
        self._client: Optional[Client] = None
        self._temp_files: list = []  # 跟踪临时文件
        self._video_url_cache: dict = {}  # 缓存 video_id -> full_url 映射

    async def initialize(self):
        """插件初始化"""
        logger.info("Rule34Video 插件正在初始化...")

        # 获取配置
        config = self.context.get_config()
        proxy = config.get("proxy", "")
        timeout = config.get("request_timeout", 30)

        # 初始化客户端
        self._client = Client(proxy=proxy if proxy else None, timeout=timeout)

        # 清理旧缓存
        cache_ttl = config.get("cache_ttl_hours", 24)
        cleanup_temp_files(max_age_hours=cache_ttl)

        logger.info("Rule34Video 插件初始化完成")

    async def terminate(self):
        """插件销毁"""
        logger.info("Rule34Video 插件正在关闭...")

        # 关闭客户端
        if self._client:
            await self._client.close()

        # 清理临时文件
        self._cleanup_temp_files()

        logger.info("Rule34Video 插件已关闭")

    def _cleanup_temp_files(self):
        """清理临时文件"""
        for filepath in self._temp_files:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.debug(f"已删除临时文件: {filepath}")
            except Exception as e:
                logger.warning(f"删除临时文件失败: {filepath}, 错误: {e}")
        self._temp_files.clear()

    async def _process_thumbnail(self, thumbnail_url: str) -> Optional[str]:
        """
        处理缩略图（下载并应用打码效果）

        Args:
            thumbnail_url: 缩略图URL

        Returns:
            处理后的本地文件路径，或None
        """
        if not thumbnail_url:
            return None

        config = self.context.get_config()
        mosaic_level = config.get("mosaic_level", 70)
        blur_level = config.get("blur_level", 0)

        try:
            import aiohttp
            import hashlib

            async with aiohttp.ClientSession() as session:
                proxy = config.get("proxy", "")
                async with session.get(
                    thumbnail_url,
                    proxy=proxy if proxy else None,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        return None

                    image_data = await response.read()

            # 应用打码效果
            if mosaic_level > 0:
                image_data = await apply_mosaic(image_data, mosaic_level)

            if blur_level > 0:
                image_data = await apply_blur(image_data, blur_level)

            # 保存到临时文件
            temp_dir = get_temp_dir()
            filename = hashlib.md5(thumbnail_url.encode()).hexdigest() + ".jpg"
            filepath = os.path.join(temp_dir, filename)

            with open(filepath, "wb") as f:
                f.write(image_data)

            self._temp_files.append(filepath)
            return filepath

        except Exception as e:
            logger.warning(f"处理缩略图失败: {e}")
            return None

    def _format_video_info(self, video) -> str:
        """
        格式化视频信息为消息文本

        Args:
            video: Video对象

        Returns:
            格式化的文本
        """
        info_parts = [
            f"🎬 {video.title}",
            "",
            f"🔗 ID: {video.video_id}",
            f"⏱️ 时长: {video.duration_formatted}",
            f"👁️ 观看: {video.views:,}",
            f"👍 点赞: {video.likes:,} | 👎 踩: {video.dislikes:,}",
            f"⭐ 评分: {video.rating}%",
        ]

        if video.uploader:
            info_parts.append(f"👤 上传者: {video.uploader}")

        if video.upload_date:
            info_parts.append(f"📅 上传日期: {video.upload_date}")

        if video.tags:
            tags_str = ", ".join(video.tags[:10])
            if len(video.tags) > 10:
                tags_str += f" (+{len(video.tags) - 10})"
            info_parts.append(f"🏷️ 标签: {tags_str}")

        if video.available_qualities:
            qualities_str = ", ".join(video.available_qualities)
            info_parts.append(f"📺 可用质量: {qualities_str}")

        info_parts.append("")
        info_parts.append(f"🔗 链接: {video.url}")

        if video.direct_url:
            info_parts.append(f"📥 直链: {video.direct_url}")

        # 添加零宽字符防止strip
        return "\n".join(info_parts) + "\u200E"

    def _cache_search_results(self, results: list):
        """
        缓存搜索结果的完整URL
        
        Args:
            results: 搜索结果列表
        """
        for result in results:
            video_id = str(result.get('video_id', ''))
            full_url = result.get('url', '')
            
            # 确保缓存有效的完整URL
            if video_id and full_url:
                # 检查URL是否包含完整的slug（不仅仅是ID）
                # 有效的URL应该类似: /videos/123456/video-title-here/
                if '/' in full_url and not full_url.endswith(f'/{video_id}/'):
                    self._video_url_cache[video_id] = full_url
                    logger.debug(f"缓存视频URL: {video_id} -> {full_url}")
                elif video_id not in self._video_url_cache:
                    # 即使是不完整的URL，如果之前没有缓存也保存它
                    self._video_url_cache[video_id] = full_url
                    logger.debug(f"缓存视频URL (备用): {video_id} -> {full_url}")

    def _parse_video_identifier(self, identifier: str) -> tuple:
        """
        解析视频标识符，支持纯ID或id/slug格式
        
        Args:
            identifier: 视频标识符，如 "4167287" 或 "4167287/video-title"
            
        Returns:
            (video_id, full_url) 元组
        """
        identifier = identifier.strip()
        
        if '/' in identifier:
            # 格式: id/slug
            parts = identifier.split('/', 1)
            video_id = parts[0]
            slug = parts[1].rstrip('/')
            full_url = f"https://rule34video.com/video/{video_id}/{slug}/"
            return video_id, full_url
        else:
            # 纯ID格式，尝试从缓存获取
            video_id = identifier
            full_url = self._video_url_cache.get(video_id)
            return video_id, full_url

    @filter.command("rule34video")
    async def cmd_video_info(self, event: AstrMessageEvent, video_id: str = ""):
        """
        获取视频信息
        用法: /rule34video <视频ID> 或 /rule34video <ID/slug>
        """
        if not video_id:
            yield event.plain_result("❌ 请提供视频ID或ID/slug\u200E")
            return

        try:
            # 清理上次的临时文件
            self._cleanup_temp_files()

            # 解析视频标识符
            parsed_id, full_url = self._parse_video_identifier(video_id)
            if full_url:
                logger.debug(f"解析视频URL: {parsed_id} -> {full_url}")
            
            video = await self._client.get_video(parsed_id, full_url=full_url)

            config = self.context.get_config()
            show_thumbnail = config.get("show_thumbnail", True)

            # 准备消息
            info_text = self._format_video_info(video)

            if show_thumbnail and video.thumbnail:
                # 处理并发送缩略图
                thumbnail_path = await self._process_thumbnail(video.thumbnail)

                if thumbnail_path:
                    chain = [
                        Comp.Image.fromFileSystem(thumbnail_path),
                        Comp.Plain(info_text)
                    ]
                    yield event.chain_result(chain)
                else:
                    yield event.plain_result(info_text)
            else:
                yield event.plain_result(info_text)

        except VideoNotFound:
            yield event.plain_result(f"❌ 视频不存在: {video_id}\u200E")
        except NetworkError as e:
            yield event.plain_result(f"❌ 网络错误: {e.message}\u200E")
        except InvalidURL:
            yield event.plain_result(f"❌ 无效的视频ID: {video_id}\u200E")
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            yield event.plain_result(f"❌ 获取视频信息失败: {str(e)}\u200E")

    @filter.command("rule34videosearch")
    async def cmd_search(self, event: AstrMessageEvent, query: str = ""):
        """
        搜索视频
        用法: /rule34videosearch <关键词>
        """
        if not query:
            yield event.plain_result("❌ 请提供搜索关键词\u200E")
            return

        try:
            self._cleanup_temp_files()

            config = self.context.get_config()
            max_results = config.get("max_search_results", 10)

            results = await self._client.search(query, max_results=max_results)

            if not results:
                yield event.plain_result(f"🔍 未找到相关视频: {query}\u200E")
                return

            # 缓存搜索结果
            self._cache_search_results(results)

            # 格式化搜索结果
            result_lines = [f"🔍 搜索结果: {query}", f"共找到 {len(results)} 个视频", ""]

            for i, result in enumerate(results, 1):
                video_id = result['video_id']
                slug = result.get('slug', '').rstrip('/')
                if slug:
                    # 显示 id/slug 格式
                    result_lines.append(f"{i}. {video_id}/{slug}")
                else:
                    result_lines.append(f"{i}. {video_id}")

            result_lines.append("")
            result_lines.append("使用 /rule34video <ID/slug> 查看详情\u200E")

            yield event.plain_result("\n".join(result_lines))

        except NetworkError as e:
            yield event.plain_result(f"❌ 网络错误: {e.message}\u200E")
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            yield event.plain_result(f"❌ 搜索失败: {str(e)}\u200E")

    @filter.command("rule34videorandom")
    async def cmd_random(self, event: AstrMessageEvent):
        """
        获取随机视频
        用法: /rule34videorandom
        """
        try:
            self._cleanup_temp_files()

            video = await self._client.get_random_video()

            config = self.context.get_config()
            show_thumbnail = config.get("show_thumbnail", True)

            info_text = "🎲 随机视频\n\n" + self._format_video_info(video)

            if show_thumbnail and video.thumbnail:
                thumbnail_path = await self._process_thumbnail(video.thumbnail)

                if thumbnail_path:
                    chain = [
                        Comp.Image.fromFileSystem(thumbnail_path),
                        Comp.Plain(info_text)
                    ]
                    yield event.chain_result(chain)
                else:
                    yield event.plain_result(info_text)
            else:
                yield event.plain_result(info_text)

        except VideoNotFound:
            yield event.plain_result("❌ 未找到随机视频\u200E")
        except NetworkError as e:
            yield event.plain_result(f"❌ 网络错误: {e.message}\u200E")
        except Exception as e:
            logger.error(f"获取随机视频失败: {e}")
            yield event.plain_result(f"❌ 获取随机视频失败: {str(e)}\u200E")

    @filter.command("rule34videolatest")
    async def cmd_latest(self, event: AstrMessageEvent, count: str = "5"):
        """
        获取最新视频
        用法: /rule34videolatest [数量]
        """
        try:
            self._cleanup_temp_files()

            try:
                num = int(count)
                num = max(1, min(20, num))  # 限制1-20
            except ValueError:
                num = 5

            results = await self._client.search(sort="latest", max_results=num)

            if not results:
                yield event.plain_result("❌ 未找到最新视频\u200E")
                return

            # 缓存搜索结果
            self._cache_search_results(results)

            result_lines = ["📰 最新视频", ""]

            for i, result in enumerate(results, 1):
                video_id = result['video_id']
                slug = result.get('slug', '').rstrip('/')
                if slug:
                    result_lines.append(f"{i}. {video_id}/{slug}")
                else:
                    result_lines.append(f"{i}. {video_id}")

            result_lines.append("")
            result_lines.append("使用 /rule34video <ID/slug> 查看详情\u200E")

            yield event.plain_result("\n".join(result_lines))

        except NetworkError as e:
            yield event.plain_result(f"❌ 网络错误: {e.message}\u200E")
        except Exception as e:
            logger.error(f"获取最新视频失败: {e}")
            yield event.plain_result(f"❌ 获取最新视频失败: {str(e)}\u200E")

    @filter.command("rule34videopopular")
    async def cmd_popular(self, event: AstrMessageEvent, count: str = "5"):
        """
        获取热门视频
        用法: /rule34videopopular [数量]
        """
        try:
            self._cleanup_temp_files()

            try:
                num = int(count)
                num = max(1, min(20, num))
            except ValueError:
                num = 5

            results = await self._client.search(sort="most_viewed", max_results=num)

            if not results:
                yield event.plain_result("❌ 未找到热门视频\u200E")
                return

            # 缓存搜索结果
            self._cache_search_results(results)

            result_lines = ["🔥 热门视频", ""]

            for i, result in enumerate(results, 1):
                video_id = result['video_id']
                slug = result.get('slug', '').rstrip('/')
                if slug:
                    result_lines.append(f"{i}. {video_id}/{slug}")
                else:
                    result_lines.append(f"{i}. {video_id}")

            result_lines.append("")
            result_lines.append("使用 /rule34video <ID/slug> 查看详情\u200E")

            yield event.plain_result("\n".join(result_lines))

        except NetworkError as e:
            yield event.plain_result(f"❌ 网络错误: {e.message}\u200E")
        except Exception as e:
            logger.error(f"获取热门视频失败: {e}")
            yield event.plain_result(f"❌ 获取热门视频失败: {str(e)}\u200E")

    @filter.command("rule34videotags")
    async def cmd_tags(self, event: AstrMessageEvent, video_id: str = ""):
        """
        获取视频标签
        用法: /rule34videotags <视频ID> 或 /rule34videotags <ID/slug>
        """
        if not video_id:
            yield event.plain_result("❌ 请提供视频ID或ID/slug\u200E")
            return

        try:
            self._cleanup_temp_files()

            # 解析视频标识符
            parsed_id, full_url = self._parse_video_identifier(video_id)
            video = await self._client.get_video(parsed_id, full_url=full_url)

            if not video.tags:
                yield event.plain_result(f"🏷️ 视频 {video_id} 没有标签\u200E")
                return

            tags_str = "\n".join([f"• {tag}" for tag in video.tags])
            result = f"🏷️ 视频 {video_id} 的标签:\n\n{tags_str}\u200E"

            yield event.plain_result(result)

        except VideoNotFound:
            yield event.plain_result(f"❌ 视频不存在: {video_id}\u200E")
        except NetworkError as e:
            yield event.plain_result(f"❌ 网络错误: {e.message}\u200E")
        except Exception as e:
            logger.error(f"获取标签失败: {e}")
            yield event.plain_result(f"❌ 获取标签失败: {str(e)}\u200E")

    @filter.command("rule34videourl")
    async def cmd_direct_url(self, event: AstrMessageEvent, video_id: str = "", quality: str = ""):
        """
        获取视频直链
        用法: /rule34videourl <视频ID> [质量] 或 /rule34videourl <ID/slug> [质量]
        质量可选: best, 720p, 480p, 360p, worst
        """
        if not video_id:
            yield event.plain_result("❌ 请提供视频ID或ID/slug\u200E")
            return

        try:
            self._cleanup_temp_files()

            # 解析视频标识符
            parsed_id, full_url = self._parse_video_identifier(video_id)
            video = await self._client.get_video(parsed_id, full_url=full_url)

            config = self.context.get_config()
            if not quality:
                quality = config.get("default_quality", "best")

            url = video.get_video_url(quality)

            if not url:
                yield event.plain_result(f"❌ 无法获取视频 {video_id} 的直链\u200E")
                return

            result_lines = [
                "📥 视频直链",
                "",
                f"ID: {video_id}",
                f"标题: {video.title}",
                f"请求质量: {quality}",
                f"可用质量: {', '.join(video.available_qualities)}",
                "",
                f"直链: {url}\u200E"
            ]

            yield event.plain_result("\n".join(result_lines))

        except VideoNotFound:
            yield event.plain_result(f"❌ 视频不存在: {video_id}\u200E")
        except NetworkError as e:
            yield event.plain_result(f"❌ 网络错误: {e.message}\u200E")
        except Exception as e:
            logger.error(f"获取直链失败: {e}")
            yield event.plain_result(f"❌ 获取直链失败: {str(e)}\u200E")

    @filter.command("rule34videocat")
    async def cmd_categories(self, event: AstrMessageEvent):
        """
        获取分类列表
        用法: /rule34videocat
        """
        try:
            self._cleanup_temp_files()

            categories = await self._client.get_categories()

            if not categories:
                yield event.plain_result("❌ 未找到分类\u200E")
                return

            # 只显示前30个
            display_cats = categories[:30]
            cats_str = ", ".join([c["name"] for c in display_cats])

            result = f"📂 分类列表 (共 {len(categories)} 个):\n\n{cats_str}"

            if len(categories) > 30:
                result += "\n\n(仅显示前30个)\u200E"
            else:
                result += "\u200E"

            yield event.plain_result(result)

        except NetworkError as e:
            yield event.plain_result(f"❌ 网络错误: {e.message}\u200E")
        except Exception as e:
            logger.error(f"获取分类失败: {e}")
            yield event.plain_result(f"❌ 获取分类失败: {str(e)}\u200E")

    @filter.command("rule34videobytag")
    async def cmd_by_tag(self, event: AstrMessageEvent, tag: str = "", count: str = "5"):
        """
        按标签获取视频
        用法: /rule34videobytag <标签> [数量]
        """
        if not tag:
            yield event.plain_result("❌ 请提供标签名称\u200E")
            return

        try:
            self._cleanup_temp_files()

            try:
                num = int(count)
                num = max(1, min(20, num))
            except ValueError:
                num = 5

            results = await self._client.get_videos_by_tag(tag, max_results=num)

            if not results:
                yield event.plain_result(f"🏷️ 标签 '{tag}' 下没有视频\u200E")
                return

            # 缓存搜索结果
            self._cache_search_results(results)

            result_lines = [f"🏷️ 标签: {tag}", f"找到 {len(results)} 个视频", ""]

            for i, result in enumerate(results, 1):
                video_id = result['video_id']
                slug = result.get('slug', '').rstrip('/')
                if slug:
                    result_lines.append(f"{i}. {video_id}/{slug}")
                else:
                    result_lines.append(f"{i}. {video_id}")

            result_lines.append("")
            result_lines.append("使用 /rule34video <ID/slug> 查看详情\u200E")

            yield event.plain_result("\n".join(result_lines))

        except NetworkError as e:
            yield event.plain_result(f"❌ 网络错误: {e.message}\u200E")
        except Exception as e:
            logger.error(f"按标签获取失败: {e}")
            yield event.plain_result(f"❌ 按标签获取失败: {str(e)}\u200E")

    @filter.command("rule34videobycat")
    async def cmd_by_category(self, event: AstrMessageEvent, category: str = "", count: str = "5"):
        """
        按分类获取视频
        用法: /rule34videobycat <分类> [数量]
        """
        if not category:
            yield event.plain_result("❌ 请提供分类名称\u200E")
            return

        try:
            self._cleanup_temp_files()

            try:
                num = int(count)
                num = max(1, min(20, num))
            except ValueError:
                num = 5

            results = await self._client.get_videos_by_category(category, max_results=num)

            if not results:
                yield event.plain_result(f"📂 分类 '{category}' 下没有视频\u200E")
                return

            # 缓存搜索结果
            self._cache_search_results(results)

            result_lines = [f"📂 分类: {category}", f"找到 {len(results)} 个视频", ""]

            for i, result in enumerate(results, 1):
                video_id = result['video_id']
                slug = result.get('slug', '').rstrip('/')
                if slug:
                    result_lines.append(f"{i}. {video_id}/{slug}")
                else:
                    result_lines.append(f"{i}. {video_id}")

            result_lines.append("")
            result_lines.append("使用 /rule34video <ID/slug> 查看详情\u200E")

            yield event.plain_result("\n".join(result_lines))

        except NetworkError as e:
            yield event.plain_result(f"❌ 网络错误: {e.message}\u200E")
        except Exception as e:
            logger.error(f"按分类获取失败: {e}")
            yield event.plain_result(f"❌ 按分类获取失败: {str(e)}\u200E")

    @filter.command("rule34videothumb")
    async def cmd_thumbnail(self, event: AstrMessageEvent, video_id: str = ""):
        """
        获取视频缩略图
        用法: /rule34videothumb <视频ID> 或 /rule34videothumb <ID/slug>
        """
        if not video_id:
            yield event.plain_result("❌ 请提供视频ID或ID/slug\u200E")
            return

        try:
            self._cleanup_temp_files()

            # 解析视频标识符
            parsed_id, full_url = self._parse_video_identifier(video_id)
            video = await self._client.get_video(parsed_id, full_url=full_url)

            if not video.thumbnail:
                yield event.plain_result(f"❌ 视频 {video_id} 没有缩略图\u200E")
                return

            thumbnail_path = await self._process_thumbnail(video.thumbnail)

            if thumbnail_path:
                chain = [
                    Comp.Image.fromFileSystem(thumbnail_path),
                    Comp.Plain(f"🖼️ 视频 {video_id} 的缩略图\u200E")
                ]
                yield event.chain_result(chain)
            else:
                # 如果处理失败，发送原始URL
                yield event.plain_result(f"🖼️ 缩略图链接: {video.thumbnail}\u200E")

        except VideoNotFound:
            yield event.plain_result(f"❌ 视频不存在: {video_id}\u200E")
        except NetworkError as e:
            yield event.plain_result(f"❌ 网络错误: {e.message}\u200E")
        except Exception as e:
            logger.error(f"获取缩略图失败: {e}")
            yield event.plain_result(f"❌ 获取缩略图失败: {str(e)}\u200E")
