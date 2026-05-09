"""
Agent 友好的 JSON Schema 定义

定义所有 CLI 命令的结构化输出格式，供 AI 工具解析。
"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class CommandStatus(str, Enum):
    """命令执行状态"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"  # 部分成功（如批量处理中有失败项）


@dataclass
class AgentError:
    """Agent 可理解的错误结构"""
    code: str
    message: str
    suggestion: str
    recoverable: bool  # 是否可自动恢复
    auto_fix_action: Optional[str] = None  # 自动修复建议命令

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentResponse:
    """统一的 Agent 响应结构"""
    command: str
    status: CommandStatus
    results: Optional[List[Dict]] = None
    stats: Optional[Dict[str, Any]] = None
    output_files: Optional[Dict[str, str]] = None
    error: Optional[AgentError] = None

    def to_dict(self) -> dict:
        data = {
            "command": self.command,
            "status": self.status.value,
        }
        if self.results:
            data["results"] = self.results
        if self.stats:
            data["stats"] = self.stats
        if self.output_files:
            data["output_files"] = self.output_files
        if self.error:
            data["error"] = self.error.to_dict()
        return data

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ── 各命令的 JSON Schema 定义 ───────────────────────────────────────

GEOCODE_SINGLE_SCHEMA = {
    "type": "object",
    "required": ["command", "status", "address"],
    "properties": {
        "command": {"const": "geocode_single", "description": "命令名称"},
        "status": {"enum": ["success", "error"], "description": "执行状态"},
        "address": {"type": "string", "description": "输入的地址"},
        "longitude": {"type": "number", "description": "经度 (WGS-84)"},
        "latitude": {"type": "number", "description": "纬度 (WGS-84)"},
        "formatted_address": {"type": "string", "description": "标准化地址"},
        "province": {"type": "string", "description": "省份"},
        "city": {"type": "string", "description": "城市"},
        "district": {"type": "string", "description": "区县"},
        "source": {"type": "string", "enum": ["amap", "tianditu", "baidu"], "description": "数据来源 API"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 100, "description": "置信度分数"},
        "error": {
            "type": "object",
            "description": "错误信息（仅在 status=error 时存在）",
            "properties": {
                "code": {"type": "string", "description": "错误码"},
                "message": {"type": "string", "description": "错误消息"},
                "suggestion": {"type": "string", "description": "修复建议"},
                "recoverable": {"type": "boolean", "description": "是否可自动恢复"},
                "auto_fix_action": {"type": "string", "description": "自动修复命令"}
            },
            "required": ["code", "message", "recoverable"]
        }
    }
}

GEOCODE_BATCH_SCHEMA = {
    "type": "object",
    "required": ["command", "status", "stats"],
    "properties": {
        "command": {"const": "geocode_batch", "description": "命令名称"},
        "status": {"enum": ["success", "error", "partial"], "description": "执行状态"},
        "results": {
            "type": "array",
            "description": "地理编码结果数组",
            "items": {
                "type": "object",
                "properties": {
                    "original_address": {"type": "string", "description": "原始输入地址"},
                    "formatted_address": {"type": "string", "description": "标准化地址"},
                    "longitude": {"type": "number", "description": "经度"},
                    "latitude": {"type": "number", "description": "纬度"},
                    "province": {"type": "string"},
                    "city": {"type": "string"},
                    "district": {"type": "string"},
                    "source": {"type": "string", "enum": ["amap", "tianditu", "baidu"]},
                    "confidence": {"type": "number"},
                    "success": {"type": "boolean"}
                }
            }
        },
        "stats": {
            "type": "object",
            "description": "统计信息",
            "properties": {
                "total": {"type": "integer", "description": "总地址数"},
                "success": {"type": "integer", "description": "成功数"},
                "failed": {"type": "integer", "description": "失败数"},
                "discarded": {"type": "integer", "description": "丢弃数（低置信度）"},
                "success_rate": {"type": "number", "description": "成功率 (%)"},
                "cache_hit_rate": {"type": "number", "description": "缓存命中率 (%)"},
                "api_usage": {
                    "type": "object",
                    "description": "API 使用统计",
                    "properties": {
                        "amap": {"type": "integer"},
                        "tianditu": {"type": "integer"},
                        "baidu": {"type": "integer"}
                    }
                }
            },
            "required": ["total", "success", "failed"]
        },
        "output_files": {
            "type": "object",
            "description": "输出文件路径",
            "properties": {
                "result": {"type": "string", "description": "结果文件 (CSV/XLSX)"},
                "map": {"type": "string", "description": "地图文件 (HTML)"},
                "cache": {"type": "string", "description": "缓存数据库路径"}
            }
        },
        "error": {
            "type": "object",
            "description": "错误信息",
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "suggestion": {"type": "string"},
                "recoverable": {"type": "boolean"},
                "auto_fix_action": {"type": "string"}
            }
        }
    }
}

GEOCODE_REVERSE_SCHEMA = {
    "type": "object",
    "required": ["command", "status", "latitude", "longitude"],
    "properties": {
        "command": {"const": "geocode_reverse", "description": "命令名称"},
        "status": {"enum": ["success", "error"], "description": "执行状态"},
        "latitude": {"type": "number", "description": "输入纬度"},
        "longitude": {"type": "number", "description": "输入经度"},
        "formatted_address": {"type": "string", "description": "解析出的地址"},
        "province": {"type": "string"},
        "city": {"type": "string"},
        "district": {"type": "string"},
        "source": {"type": "string", "enum": ["amap", "tianditu", "baidu"]},
        "error": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "suggestion": {"type": "string"},
                "recoverable": {"type": "boolean"},
                "auto_fix_action": {"type": "string"}
            }
        }
    }
}

GEOCODE_CONVERT_SCHEMA = {
    "type": "object",
    "required": ["command", "status", "input", "output"],
    "properties": {
        "command": {"const": "geocode_convert", "description": "命令名称"},
        "status": {"const": "success", "description": "坐标转换不依赖 API，总是成功"},
        "input": {
            "type": "object",
            "description": "输入坐标",
            "properties": {
                "lat": {"type": "number", "description": "纬度"},
                "lon": {"type": "number", "description": "经度"},
                "coordinate_system": {"type": "string", "enum": ["wgs84", "gcj02", "bd09"]}
            },
            "required": ["lat", "lon", "coordinate_system"]
        },
        "output": {
            "type": "object",
            "description": "输出坐标",
            "properties": {
                "lat": {"type": "number", "description": "纬度"},
                "lon": {"type": "number", "description": "经度"},
                "coordinate_system": {"type": "string", "enum": ["wgs84", "gcj02", "bd09"]}
            },
            "required": ["lat", "lon", "coordinate_system"]
        }
    }
}

CACHE_STATS_SCHEMA = {
    "type": "object",
    "required": ["command", "status"],
    "properties": {
        "command": {"const": "cache_stats", "description": "命令名称"},
        "status": {"const": "success", "description": "缓存统计总是成功"},
        "total_entries": {"type": "integer", "description": "缓存总条目数"},
        "hits": {"type": "integer", "description": "命中次数"},
        "misses": {"type": "integer", "description": "未命中次数"},
        "hit_rate": {"type": "number", "description": "命中率 (%)"},
        "size_mb": {"type": "number", "description": "数据库大小 (MB)"},
        "db_path": {"type": "string", "description": "数据库路径"}
    }
}

CONFIG_CHECK_SCHEMA = {
    "type": "object",
    "required": ["command", "status", "apis"],
    "properties": {
        "command": {"const": "config_check", "description": "命令名称"},
        "status": {"const": "success", "description": "配置检查总是成功"},
        "apis": {
            "type": "array",
            "description": "API 配置状态",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "enum": ["amap", "tianditu", "baidu"]},
                    "available": {"type": "boolean", "description": "是否可用"},
                    "key_configured": {"type": "boolean", "description": "密钥是否配置"},
                    "quota_remaining": {"type": "integer", "description": "剩余配额（未知时为 null）"}
                }
            }
        },
        "cache": {
            "type": "object",
            "description": "缓存状态",
            "properties": {
                "entries": {"type": "integer"},
                "hit_rate": {"type": "number"},
                "size_mb": {"type": "number"}
            }
        },
        "ai": {
            "type": "object",
            "description": "AI 配置状态",
            "properties": {
                "enabled": {"type": "boolean"},
                "provider": {"type": "string"},
                "model": {"type": "string"}
            }
        },
        "warnings": {
            "type": "array",
            "description": "警告信息",
            "items": {"type": "string"}
        }
    }
}

FILE_LIST_SCHEMA = {
    "type": "object",
    "required": ["command", "status", "files"],
    "properties": {
        "command": {"const": "map_list", "description": "命令名称"},
        "status": {"const": "success"},
        "files": {
            "type": "array",
            "description": "可处理文件列表",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "文件名"},
                    "path": {"type": "string", "description": "相对路径"},
                    "size_kb": {"type": "number"},
                    "modified": {"type": "number", "description": "修改时间戳"},
                    "columns": {
                        "type": "array",
                        "description": "文件列名（仅 --detail 模式）",
                        "items": {"type": "string"}
                    },
                    "rows": {"type": "integer", "description": "行数（仅 --detail 模式）"}
                }
            }
        },
        "count": {"type": "integer", "description": "文件数量"}
    }
}


# Schema 注册表
SCHEMA_REGISTRY: Dict[str, Dict] = {
    "geocode_single": GEOCODE_SINGLE_SCHEMA,
    "geocode_batch": GEOCODE_BATCH_SCHEMA,
    "geocode_reverse": GEOCODE_REVERSE_SCHEMA,
    "geocode_convert": GEOCODE_CONVERT_SCHEMA,
    "cache_stats": CACHE_STATS_SCHEMA,
    "config_check": CONFIG_CHECK_SCHEMA,
    "map_list": FILE_LIST_SCHEMA,
}


def get_schema(command: str) -> Optional[Dict]:
    """获取指定命令的 JSON schema"""
    return SCHEMA_REGISTRY.get(command)


def get_all_schemas() -> Dict[str, Dict]:
    """获取所有已注册的 schema"""
    return SCHEMA_REGISTRY.copy()


def validate_response(response: Dict, command: str) -> bool:
    """验证响应是否符合指定命令的 schema（简单验证）"""
    schema = get_schema(command)
    if not schema:
        return False

    required = schema.get("required", [])
    for field in required:
        if field not in response:
            return False

    return True
