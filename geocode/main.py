"""
主程序入口

支持命令行和模块调用两种方式
"""

import argparse
import sys
from pathlib import Path
from typing import List

import pandas as pd

from .cache import CacheManager
from .config import Config, PROJECT_DIR
from .geocoder import Geocoder
from .logger import APILogger
from .map_visualizer import create_map


def resolve_path(file_path: str) -> Path:
    """解析路径，相对路径基于项目根目录"""
    path = Path(file_path)
    if path.is_absolute():
        return path
    return PROJECT_DIR / path


def load_addresses(input_file: str, address_column: str) -> List[str]:
    """
    从文件加载地址列表

    Args:
        input_file: 输入文件路径
        address_column: 地址列名

    Returns:
        地址列表
    """
    input_path = resolve_path(input_file)
    suffix = input_path.suffix.lower()

    if suffix in [".xlsx", ".xls"]:
        engine = "openpyxl" if suffix == ".xlsx" else "xlrd"
        df = pd.read_excel(input_path, engine=engine)
    else:
        df = pd.read_csv(input_path, encoding="utf-8-sig")

    if address_column not in df.columns:
        raise ValueError(f"列 '{address_column}' 不存在，可用列: {list(df.columns)}")

    return df[address_column].dropna().astype(str).tolist()


def save_results(results: List[dict], output_csv: str) -> None:
    """保存结果到CSV"""
    output_data = []
    for r in results:
        output_data.append({
            "原始地址": r.get("original_address", ""),
            "标准化地址": r.get("formatted_address", ""),
            "经度": r.get("longitude", ""),
            "纬度": r.get("latitude", ""),
            "省": r.get("province", ""),
            "市": r.get("city", ""),
            "区": r.get("district", ""),
            "数据来源": r.get("source", ""),
            "坐标系": r.get("coordinate_system", ""),
            "状态": "成功" if r.get("success") else "失败",
        })

    output_df = pd.DataFrame(output_data)
    output_path = resolve_path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_path, index=False, encoding="utf-8-sig")


def main(
    input_file: str = "data/清单.xlsx",
    output_csv: str = "output/地址_经纬度_结果.csv",
    output_map: str = "output/地图输出.html",
    cache_file: str = "output/geocache.db",
    log_file: str = "output/api调用日志.csv",
    address_column: str = "地址",
    use_cluster: bool = True,
    use_heatmap: bool = True,
    cache_ttl: float = None,
    batch_size: int = 100,
    cleanup_cache: bool = False,
) -> None:
    """
    主函数

    Args:
        input_file: 输入文件路径
        output_csv: 输出CSV路径
        output_map: 输出地图HTML路径
        cache_file: 缓存文件路径
        log_file: 日志文件路径
        address_column: 地址列名
        use_cluster: 是否使用点聚类
        use_heatmap: 是否使用热力图
        cache_ttl: 缓存过期时间(秒)
        batch_size: 缓存批量提交阈值
        cleanup_cache: 是否清理过期缓存
    """
    print("=" * 60)
    print("地址转经纬度 + 地图标注工具 v1.2")
    print("=" * 60)

    # 检查配置
    if not Config.validate():
        print("错误: 未配置任何API密钥，请检查 .env 文件")
        print(f"配置文件位置: {PROJECT_DIR / '.env'}")
        return

    available_apis = Config.get_available_apis()
    print(f"可用API: {', '.join(available_apis)}")

    # 初始化缓存（精简版：单层SQLite，批量提交）
    cache_manager = CacheManager(
        cache_file=str(resolve_path(cache_file)),
        default_ttl=cache_ttl,
        batch_size=batch_size
    )

    # 显示缓存状态
    cache_stats = cache_manager.get_stats()
    print(f"缓存状态: {cache_stats['total_entries']} 条记录")

    # 清理过期缓存
    if cleanup_cache:
        cleaned = cache_manager.cleanup()
        print(f"清理过期缓存: {cleaned} 条")

    # 加载数据
    try:
        addresses = load_addresses(input_file, address_column)
        print(f"\n读取地址数据: {resolve_path(input_file)}")
        print(f"共读取 {len(addresses)} 条地址数据")
    except FileNotFoundError:
        print(f"错误: 输入文件不存在 - {resolve_path(input_file)}")
        cache_manager.close()
        return
    except ValueError as e:
        print(f"错误: {e}")
        cache_manager.close()
        return

    # 初始化
    api_logger = APILogger(str(resolve_path(log_file)))
    geocoder = Geocoder(cache_manager, api_logger, cache_ttl=cache_ttl)

    print("开始地理编码...")

    # 执行地理编码
    results = geocoder.batch_geocode(addresses, progress=True)

    # 保存结果
    save_results(results, output_csv)
    print(f"\n结果已保存: {resolve_path(output_csv)}")

    # 生成地图
    valid_results = [r for r in results if r.get("success")]
    if valid_results:
        map_path = create_map(
            data=valid_results,
            output_file=str(resolve_path(output_map)),
            title="地址分布地图",
            use_cluster=use_cluster,
            use_heatmap=use_heatmap,
        )
        print(f"地图已生成: {map_path}")

    # 统计信息
    success_count = len(valid_results)
    api_stats = api_logger.get_stats()
    cache_stats = geocoder.get_cache_stats()

    print("\n" + "=" * 60)
    print("处理完成统计")
    print("=" * 60)
    print(f"总地址数: {len(addresses)}")
    print(f"成功转换: {success_count}")
    print(f"转换失败: {len(addresses) - success_count}")
    print(f"成功率: {success_count / len(addresses) * 100:.1f}%")

    if api_stats["api_usage"]:
        print(f"\nAPI调用统计:")
        for api, count in api_stats["api_usage"].items():
            print(f"  - {api}: {count} 次")

    print(f"\n缓存统计:")
    print(f"  - 命中率: {cache_stats['hit_rate']}%")
    print(f"  - 缓存条目: {cache_stats['total_entries']} 条")

    print(f"\n输出文件:")
    print(f"  - 结果CSV: {resolve_path(output_csv)}")
    print(f"  - 地图HTML: {resolve_path(output_map)}")
    print(f"  - 缓存数据库: {resolve_path(cache_file)}")
    print(f"  - API日志: {resolve_path(log_file)}")

    # 关闭资源
    geocoder.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="地址转经纬度 + 地图标注工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m geocode                           # 使用默认配置
  python -m geocode -i data/地址.xlsx         # 指定输入文件
  python -m geocode -i input.xlsx -c "详细地址"  # 指定列名
  python -m geocode --ttl 604800               # 缓存7天后过期
  python -m geocode --cleanup                  # 清理过期缓存
  python -m geocode --batch-size 50            # 每50条提交一次
        """
    )
    parser.add_argument("-i", "--input", default="data/清单.xlsx", help="输入文件 (支持CSV/Excel)")
    parser.add_argument("-o", "--output", default="output/地址_经纬度_结果.csv", help="输出CSV文件")
    parser.add_argument("-m", "--map", default="output/地图输出.html", help="输出地图HTML")
    parser.add_argument("-c", "--column", default="地址", help="地址列名")
    parser.add_argument("--cache", default="output/geocache.db", help="缓存数据库文件")
    parser.add_argument("--ttl", type=float, default=None, help="缓存过期时间(秒)")
    parser.add_argument("--batch-size", type=int, default=100, help="缓存批量提交阈值")
    parser.add_argument("--cleanup", action="store_true", help="清理过期缓存")
    parser.add_argument("--no-cluster", action="store_true", help="禁用点聚类")
    parser.add_argument("--no-heatmap", action="store_true", help="禁用热力图")

    args = parser.parse_args()

    main(
        input_file=args.input,
        output_csv=args.output,
        output_map=args.map,
        cache_file=args.cache,
        address_column=args.column,
        use_cluster=not args.no_cluster,
        use_heatmap=not args.no_heatmap,
        cache_ttl=args.ttl,
        batch_size=args.batch_size,
        cleanup_cache=args.cleanup,
    )