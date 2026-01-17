"""
Rule34Video API 错误定义
"""


class Rule34VideoError(Exception):
    """Rule34Video API 基础异常类"""
    pass


class VideoNotFound(Rule34VideoError):
    """视频未找到"""
    def __init__(self, video_id: str = None, message: str = None):
        self.video_id = video_id
        self.message = message or f"Video not found: {video_id}"
        super().__init__(self.message)


class InvalidURL(Rule34VideoError):
    """无效的URL"""
    def __init__(self, url: str = None, message: str = None):
        self.url = url
        self.message = message or f"Invalid URL: {url}"
        super().__init__(self.message)


class NetworkError(Rule34VideoError):
    """网络请求错误"""
    def __init__(self, message: str = None, status_code: int = None):
        self.status_code = status_code
        self.message = message or f"Network error occurred (status: {status_code})"
        super().__init__(self.message)


class ParseError(Rule34VideoError):
    """解析错误"""
    def __init__(self, message: str = None, field: str = None):
        self.field = field
        self.message = message or f"Failed to parse: {field}"
        super().__init__(self.message)


class VideoDisabled(Rule34VideoError):
    """视频已被禁用/删除"""
    def __init__(self, video_id: str = None, message: str = None):
        self.video_id = video_id
        self.message = message or f"Video has been disabled or removed: {video_id}"
        super().__init__(self.message)


class RateLimitError(Rule34VideoError):
    """请求频率限制"""
    def __init__(self, message: str = None, retry_after: int = None):
        self.retry_after = retry_after
        self.message = message or f"Rate limit exceeded. Retry after {retry_after} seconds"
        super().__init__(self.message)


class ConfigurationError(Rule34VideoError):
    """配置错误"""
    def __init__(self, message: str = None, key: str = None):
        self.key = key
        self.message = message or f"Configuration error: {key}"
        super().__init__(self.message)