"""
API调用日志模块

记录每次API调用的详细信息，便于调试和统计
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from .models import APILog


class APILogger:
    """API调用日志记录器"""

    def __init__(self, log_file: str = "output/api调用日志.csv"):
        self.log_file = Path(log_file)
        self._logs: List[APILog] = []
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """确保日志目录存在"""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        address: str,
        api_name: str,
        status: str,
        latitude: float = None,
        longitude: float = None,
        formatted_address: str = None,
        time_cost: float = 0.0,
        error_message: str = None
    ) -> None:
        """
        记录一次API调用

        Args:
            address: 查询地址
            api_name: API名称 (amap/tianditu/baidu)
            status: 状态 (success/failed/error)
            latitude: 纬度
            longitude: 经度
            formatted_address: 格式化地址
            time_cost: 耗时(秒)
            error_message: 错误信息
        """
        entry = APILog(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            address=address,
            api_name=api_name,
            status=status,
            latitude=latitude,
            longitude=longitude,
            formatted_address=formatted_address,
            time_cost=round(time_cost, 3),
            error_message=error_message
        )
        self._logs.append(entry)

    def save(self) -> None:
        """保存日志到CSV文件"""
        if not self._logs:
            return

        file_exists = self.log_file.exists()
        fieldnames = [
            "timestamp", "address", "api_name", "status",
            "latitude", "longitude", "formatted_address",
            "time_cost", "error_message"
        ]

        with open(self.log_file, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            for log in self._logs:
                writer.writerow(log.to_dict())

        # 清空已保存的日志，防止重复写入
        self._logs = []

    def get_stats(self) -> Dict:
        """
        获取统计信息

        Returns:
            统计字典: {total, success, failed, success_rate, api_usage}
        """
        total = len(self._logs)
        if total == 0:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "success_rate": 0.0,
                "api_usage": {}
            }

        success = sum(1 for log in self._logs if log.status == "success")
        api_counts: Dict[str, int] = {}

        for log in self._logs:
            api_counts[log.api_name] = api_counts.get(log.api_name, 0) + 1

        return {
            "total": total,
            "success": success,
            "failed": total - success,
            "success_rate": round(success / total * 100, 2),
            "api_usage": api_counts
        }

    def clear(self) -> None:
        """清空内存中的日志"""
        self._logs = []