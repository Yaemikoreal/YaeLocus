"""
异常类测试

测试自定义异常类的定义和使用：
- GeocodeError 基类
- ConfigError, APIError, FileError, NetworkError 子类
- 预定义错误实例
"""

import pytest
from geocode.errors import (
    GeocodeError,
    ConfigError,
    APIError,
    FileError,
    NetworkError,
    NO_API_KEY,
    FILE_NOT_FOUND,
    COLUMN_NOT_FOUND,
    API_QUOTA_EXCEEDED,
    NETWORK_ERROR,
    INVALID_API_KEY,
)


# ============================================
# 基础异常类测试
# ============================================

class TestGeocodeError:
    """测试基础异常类"""

    def test_geocode_error_basic(self):
        """基本异常创建"""
        error = GeocodeError("测试错误", "TEST_ERROR")
        assert error.message == "测试错误"
        assert error.code == "TEST_ERROR"
        assert error.suggestion == ""

    def test_geocode_error_with_suggestion(self):
        """带建议的异常"""
        error = GeocodeError(
            message="配置错误",
            code="CONFIG_ERROR",
            suggestion="请检查配置文件"
        )
        assert error.message == "配置错误"
        assert error.code == "CONFIG_ERROR"
        assert error.suggestion == "请检查配置文件"

    def test_geocode_error_inheritance(self):
        """继承自 Exception"""
        error = GeocodeError("错误", "CODE")
        assert isinstance(error, Exception)

    def test_geocode_error_str_representation(self):
        """字符串表示"""
        error = GeocodeError("测试错误消息", "TEST_CODE")
        error_str = str(error)
        assert "测试错误消息" in error_str

    def test_geocode_error_attributes(self):
        """错误属性访问"""
        error = GeocodeError("消息", "代码", "建议")
        assert hasattr(error, 'message')
        assert hasattr(error, 'code')
        assert hasattr(error, 'suggestion')


# ============================================
# 异常子类测试
# ============================================

class TestConfigError:
    """测试配置错误"""

    def test_config_error_is_geocode_error(self):
        """继承自 GeocodeError"""
        error = ConfigError("配置错误", "CONFIG_ERROR")
        assert isinstance(error, GeocodeError)
        assert isinstance(error, Exception)

    def test_config_error_creation(self):
        """创建配置错误"""
        error = ConfigError(
            message="API密钥无效",
            code="INVALID_KEY",
            suggestion="请检查密钥格式"
        )
        assert error.message == "API密钥无效"
        assert error.code == "INVALID_KEY"
        assert error.suggestion == "请检查密钥格式"


class TestAPIError:
    """测试 API 错误"""

    def test_api_error_is_geocode_error(self):
        """继承自 GeocodeError"""
        error = APIError("API错误", "API_ERROR")
        assert isinstance(error, GeocodeError)

    def test_api_error_creation(self):
        """创建 API 错误"""
        error = APIError(
            message="API调用失败",
            code="API_FAILED",
            suggestion="请稍后重试"
        )
        assert error.message == "API调用失败"


class TestFileError:
    """测试文件错误"""

    def test_file_error_is_geocode_error(self):
        """继承自 GeocodeError"""
        error = FileError("文件错误", "FILE_ERROR")
        assert isinstance(error, GeocodeError)

    def test_file_error_creation(self):
        """创建文件错误"""
        error = FileError(
            message="文件不存在",
            code="FILE_NOT_FOUND",
            suggestion="请检查文件路径"
        )
        assert error.message == "文件不存在"


class TestNetworkError:
    """测试网络错误"""

    def test_network_error_is_geocode_error(self):
        """继承自 GeocodeError"""
        error = NetworkError("网络错误", "NETWORK_ERROR")
        assert isinstance(error, GeocodeError)

    def test_network_error_creation(self):
        """创建网络错误"""
        error = NetworkError(
            message="连接超时",
            code="TIMEOUT",
            suggestion="请检查网络连接"
        )
        assert error.message == "连接超时"


# ============================================
# 预定义错误实例测试
# ============================================

class TestPredefinedErrors:
    """测试预定义错误实例"""

    def test_no_api_key_error(self):
        """NO_API_KEY 错误"""
        assert NO_API_KEY.message == "未配置任何API密钥"
        assert NO_API_KEY.code == "NO_API_KEY"
        assert "config" in NO_API_KEY.suggestion.lower() or "配置" in NO_API_KEY.suggestion
        assert isinstance(NO_API_KEY, ConfigError)
        assert isinstance(NO_API_KEY, GeocodeError)

    def test_file_not_found_error(self):
        """FILE_NOT_FOUND 错误"""
        assert FILE_NOT_FOUND.message == "输入文件不存在"
        assert FILE_NOT_FOUND.code == "FILE_NOT_FOUND"
        assert "检查" in FILE_NOT_FOUND.suggestion or "路径" in FILE_NOT_FOUND.suggestion
        assert isinstance(FILE_NOT_FOUND, FileError)

    def test_column_not_found_error(self):
        """COLUMN_NOT_FOUND 错误"""
        assert COLUMN_NOT_FOUND.message == "地址列不存在"
        assert COLUMN_NOT_FOUND.code == "COLUMN_NOT_FOUND"
        assert "-c" in COLUMN_NOT_FOUND.suggestion or "列名" in COLUMN_NOT_FOUND.suggestion
        assert isinstance(COLUMN_NOT_FOUND, FileError)

    def test_api_quota_exceeded_error(self):
        """API_QUOTA_EXCEEDED 错误"""
        assert API_QUOTA_EXCEEDED.message == "API配额已耗尽"
        assert API_QUOTA_EXCEEDED.code == "API_QUOTA_EXCEEDED"
        assert "配额" in API_QUOTA_EXCEEDED.suggestion or "重置" in API_QUOTA_EXCEEDED.suggestion
        assert isinstance(API_QUOTA_EXCEEDED, APIError)

    def test_network_error_instance(self):
        """NETWORK_ERROR 错误"""
        assert NETWORK_ERROR.message == "网络连接失败"
        assert NETWORK_ERROR.code == "NETWORK_ERROR"
        assert "网络" in NETWORK_ERROR.suggestion or "连接" in NETWORK_ERROR.suggestion
        assert isinstance(NETWORK_ERROR, NetworkError)

    def test_invalid_api_key_error(self):
        """INVALID_API_KEY 错误"""
        assert INVALID_API_KEY.message == "API密钥格式错误"
        assert INVALID_API_KEY.code == "INVALID_API_KEY"
        assert "32" in INVALID_API_KEY.suggestion or "密钥" in INVALID_API_KEY.suggestion
        assert isinstance(INVALID_API_KEY, ConfigError)


# ============================================
# 异常使用场景测试
# ============================================

class TestErrorUsage:
    """测试错误在实际场景中的使用"""

    def test_catch_by_base_class(self):
        """按基类捕获异常"""
        try:
            raise ConfigError("配置错误", "CONFIG_ERROR")
        except GeocodeError as e:
            assert e.code == "CONFIG_ERROR"

    def test_catch_by_specific_class(self):
        """按具体类捕获异常"""
        try:
            raise APIError("API错误", "API_ERROR")
        except APIError as e:
            assert e.code == "API_ERROR"

    def test_catch_config_error_as_geocode_error(self):
        """ConfigError 可以作为 GeocodeError 捕获"""
        try:
            raise ConfigError("测试", "TEST")
        except GeocodeError:
            pass  # 成功捕获

    def test_catch_file_error_as_geocode_error(self):
        """FileError 可以作为 GeocodeError 捕获"""
        try:
            raise FileError("测试", "TEST")
        except GeocodeError:
            pass  # 成功捕获

    def test_error_attributes_preserved_after_raise(self):
        """抛出后属性保留"""
        error = ConfigError("消息", "代码", "建议")
        try:
            raise error
        except ConfigError as e:
            assert e.message == "消息"
            assert e.code == "代码"
            assert e.suggestion == "建议"

    def test_multiple_exception_types(self):
        """区分不同类型的异常"""
        errors = [
            ConfigError("配置", "CONFIG"),
            APIError("API", "API"),
            FileError("文件", "FILE"),
            NetworkError("网络", "NETWORK")
        ]

        for error in errors:
            try:
                raise error
            except ConfigError:
                assert error.code == "CONFIG"
            except APIError:
                assert error.code == "API"
            except FileError:
                assert error.code == "FILE"
            except NetworkError:
                assert error.code == "NETWORK"


# ============================================
# 错误信息格式测试
# ============================================

class TestErrorFormatting:
    """测试错误信息格式"""

    def test_error_str_contains_message(self):
        """字符串包含消息"""
        error = GeocodeError("这是错误消息", "CODE")
        assert "这是错误消息" in str(error)

    def test_error_repr(self):
        """repr 表示"""
        error = GeocodeError("消息", "CODE")
        repr_str = repr(error)
        assert "GeocodeError" in repr_str or "消息" in repr_str

    def test_predefined_error_has_all_fields(self):
        """预定义错误有所有字段"""
        predefined_errors = [
            NO_API_KEY,
            FILE_NOT_FOUND,
            COLUMN_NOT_FOUND,
            API_QUOTA_EXCEEDED,
            NETWORK_ERROR,
            INVALID_API_KEY
        ]

        for error in predefined_errors:
            assert error.message is not None and error.message != ""
            assert error.code is not None and error.code != ""
            assert error.suggestion is not None and error.suggestion != ""


# ============================================
# 异常继承结构测试
# ============================================

class TestExceptionHierarchy:
    """测试异常继承结构"""

    def test_inheritance_chain(self):
        """继承链正确"""
        error = ConfigError("测试", "CODE")

        assert isinstance(error, ConfigError)
        assert isinstance(error, GeocodeError)
        assert isinstance(error, Exception)

    def test_all_subclasses_inherit_from_geocode_error(self):
        """所有子类都继承自 GeocodeError"""
        subclasses = [ConfigError, APIError, FileError, NetworkError]

        for subclass in subclasses:
            assert issubclass(subclass, GeocodeError)
            assert issubclass(subclass, Exception)

    def test_subclasses_are_distinct(self):
        """子类之间是不同的类型"""
        assert ConfigError is not APIError
        assert APIError is not FileError
        assert FileError is not NetworkError
        assert NetworkError is not ConfigError

    def test_catch_order_matters(self):
        """捕获顺序重要（具体类应在基类前）"""
        try:
            raise ConfigError("测试", "CODE")
        except APIError:
            assert False, "不应该被 APIError 捕获"
        except ConfigError:
            pass  # 正确捕获
        except GeocodeError:
            assert False, "不应该被 GeocodeError 捕获（ConfigError 已捕获）"


# ============================================
# 边界条件测试
# ============================================

class TestEdgeCases:
    """测试边界条件"""

    def test_empty_message(self):
        """空消息"""
        error = GeocodeError("", "CODE")
        assert error.message == ""

    def test_empty_code(self):
        """空错误码"""
        error = GeocodeError("消息", "")
        assert error.code == ""

    def test_empty_suggestion(self):
        """空建议"""
        error = GeocodeError("消息", "CODE", "")
        assert error.suggestion == ""

    def test_none_suggestion(self):
        """None 建议"""
        error = GeocodeError("消息", "CODE", None)
        assert error.suggestion is None

    def test_unicode_message(self):
        """Unicode 消息"""
        error = GeocodeError("错误消息 🔥", "CODE", "建议 💡")
        assert "🔥" in error.message
        assert "💡" in error.suggestion

    def test_long_message(self):
        """长消息"""
        long_message = "这是一个很长的错误消息" * 100
        error = GeocodeError(long_message, "CODE")
        assert error.message == long_message

    def test_special_characters_in_code(self):
        """错误码包含特殊字符"""
        error = GeocodeError("消息", "ERROR_123_CODE")
        assert error.code == "ERROR_123_CODE"