"""
异常类定义

提供详细的错误码和修复建议
"""


class GeocodeError(Exception):
    """基础异常类"""

    def __init__(self, message: str, code: str, suggestion: str = ""):
        self.message = message
        self.code = code
        self.suggestion = suggestion
        super().__init__(message)


class ConfigError(GeocodeError):
    """配置错误"""
    pass


class APIError(GeocodeError):
    """API调用错误"""
    pass


class FileError(GeocodeError):
    """文件错误"""
    pass


class NetworkError(GeocodeError):
    """网络错误"""
    pass


# 预定义错误实例
NO_API_KEY = ConfigError(
    "未配置任何API密钥",
    "NO_API_KEY",
    "运行 'geocode-tool config' 配置API密钥，或检查 .env 文件"
)

FILE_NOT_FOUND = FileError(
    "输入文件不存在",
    "FILE_NOT_FOUND",
    "请检查文件路径，确保文件存在"
)

COLUMN_NOT_FOUND = FileError(
    "地址列不存在",
    "COLUMN_NOT_FOUND",
    "请使用 -c 参数指定正确的列名"
)

API_QUOTA_EXCEEDED = APIError(
    "API配额已耗尽",
    "API_QUOTA_EXCEEDED",
    "请等待配额重置或配置其他API密钥"
)

NETWORK_ERROR = NetworkError(
    "网络连接失败",
    "NETWORK_ERROR",
    "请检查网络连接或稍后重试"
)

INVALID_API_KEY = ConfigError(
    "API密钥格式错误",
    "INVALID_API_KEY",
    "请检查密钥是否正确复制，高德密钥应为32位字符"
)