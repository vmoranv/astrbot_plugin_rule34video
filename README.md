# Rule34Video AstrBot 插件

一个用于解析 rule34video.com 视频信息的 AstrBot 插件。

## 功能特性

- 🎬 获取视频详细信息（标题、时长、观看数、点赞数等）
- 🔍 搜索视频（返回 ID/slug 格式，可直接使用）
- 🎲 获取随机视频
- 📰 获取最新/热门视频
- 🏷️ 按标签/分类浏览视频
- 🖼️ 获取视频缩略图（支持马赛克/模糊处理）
- 📥 获取视频直链（多种质量选择）

## 安装

1. 将此插件目录放入 AstrBot 的插件目录中
2. 重启 AstrBot 或重载插件

## 配置

在 AstrBot 管理面板中配置以下选项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `proxy` | 代理服务器地址 | 空 |
| `mosaic_level` | 图片马赛克程度 (0-100) | 0 |
| `blur_level` | 图片模糊程度 (0-100) | 0 |
| `default_quality` | 默认视频质量 | best |
| `max_search_results` | 搜索结果最大数量 | 10 |
| `request_timeout` | 请求超时时间（秒） | 30 |
| `cache_ttl_hours` | 缓存保留时间（小时） | 24 |
| `show_thumbnail` | 是否显示缩略图 | true |
| `send_video_file` | 是否发送视频文件 | false |

## 命令列表

### 视频信息

```
/rule34video <ID/slug>
```
获取指定视频的详细信息。

**支持两种格式：**
- `/rule34video 3055012/ankha-animation-minus82` - 使用完整的 ID/slug 格式（推荐）
- `/rule34video 3055012` - 仅使用 ID（需要先搜索过该视频）

### 搜索视频

```
/rule34videosearch <关键词>
```
搜索视频，返回 ID/slug 格式的结果列表。

**示例：**
```
/rule34videosearch anime
```

**返回格式：**
```
🔍 搜索结果: anime
共找到 5 个视频

1. 3055012/ankha-animation-minus82
2. 3070351/camotli-animation-compilation
3. 3116754/nsfw-new-isabelle-animal-crossing
...

使用 /rule34video <ID/slug> 查看详情
```

### 随机视频

```
/rule34videorandom
```
获取一个随机视频。

### 最新视频

```
/rule34videolatest [数量]
```
获取最新上传的视频列表，默认5个。

### 热门视频

```
/rule34videopopular [数量]
```
获取热门视频列表，默认5个。

### 视频标签

```
/rule34videotags <ID/slug>
```
获取指定视频的所有标签。

### 视频直链

```
/rule34videourl <ID/slug> [质量]
```
获取视频的直接下载链接。

**质量选项：** best, 1080p, 720p, 480p, 360p, worst

### 分类列表

```
/rule34videocat
```
获取所有视频分类。

### 按标签浏览

```
/rule34videobytag <标签> [数量]
```
获取指定标签下的视频。

### 按分类浏览

```
/rule34videobycat <分类> [数量]
```
获取指定分类下的视频。

### 获取缩略图

```
/rule34videothumb <ID/slug>
```
获取并发送视频缩略图。

## 使用示例

1. **搜索视频**
   ```
   /rule34videosearch overwatch
   ```

2. **查看搜索结果中的视频**
   ```
   /rule34video 3055012/ankha-animation-minus82
   ```

3. **获取视频直链（最高质量）**
   ```
   /rule34videourl 3055012/ankha-animation-minus82 best
   ```

4. **获取随机视频**
   ```
   /rule34videorandom
   ```

## 依赖

- aiohttp>=3.8.0
- Pillow>=9.0.0 (可选，用于图片处理)

## 更新日志

### v1.1.0
- ✨ 搜索结果现在返回 `id/slug` 格式，可直接复制使用
- ✨ `/rule34video` 命令支持 `id/slug` 格式，无需依赖缓存
- 🐛 修复视频直链解析问题
- 🐛 修复上传日期显示错误
- 🐛 改进视频元数据提取

### v1.0.0
- 🎉 初始版本发布

## 注意事项

1. 本插件仅供学习和研究使用
2. 请遵守当地法律法规
3. 建议配置代理以确保访问稳定性
4. 缩略图会在下次命令执行前自动清理

## 许可证

MIT License

## 仓库

https://github.com/vmoranv/astrbot_plugin_rule34video
