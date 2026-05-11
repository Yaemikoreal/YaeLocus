"""TSP 求解器：贪心最近邻 + 2-opt 局部搜索"""
from typing import Callable, List, Optional, Tuple

from ..coords import haversine_km


def _build_distance_matrix(
    points: List[Tuple[float, float]],
    dist_func: Callable = None,
) -> List[List[float]]:
    """构建距离矩阵"""
    if dist_func is None:
        dist_func = haversine_km
    n = len(points)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = dist_func(points[i][0], points[i][1], points[j][0], points[j][1])
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def solve_tsp_greedy(
    points: List[Tuple[float, float]],
    start_idx: int = 0,
    dist_matrix: Optional[List[List[float]]] = None,
) -> List[int]:
    """贪心最近邻 TSP

    从起点出发，每次选择最近的未访问点。
    时间复杂度: O(n²)

    Returns:
        访问顺序（索引列表）
    """
    n = len(points)
    if n <= 2:
        return list(range(n))

    if dist_matrix is None:
        dist_matrix = _build_distance_matrix(points)

    unvisited = set(range(n))
    unvisited.discard(start_idx)
    order = [start_idx]
    current = start_idx

    while unvisited:
        nearest = min(unvisited, key=lambda j: dist_matrix[current][j])
        order.append(nearest)
        unvisited.discard(nearest)
        current = nearest

    return order


def solve_tsp_farthest_insertion(
    points: List[Tuple[float, float]],
    start_idx: int = 0,
    dist_matrix: Optional[List[List[float]]] = None,
) -> List[int]:
    """最远插入启发式 TSP

    每次选择距离当前路线最远的点，插入到代价最小的位置。
    时间复杂度: O(n³)

    Returns:
        访问顺序（索引列表）
    """
    n = len(points)
    if n <= 2:
        return list(range(n))

    if dist_matrix is None:
        dist_matrix = _build_distance_matrix(points)

    remaining = set(range(n))
    remaining.discard(start_idx)

    # 从距离起点最远的点开始构建初始环
    farthest = max(remaining, key=lambda j: dist_matrix[start_idx][j])
    remaining.discard(farthest)
    tour = [start_idx, farthest, start_idx]  # 闭环

    while remaining:
        # 找到距离当前路线任意点最远的点
        best_point = None
        best_dist = -1
        for p in remaining:
            min_dist = min(dist_matrix[p][q] for q in tour)
            if min_dist > best_dist:
                best_dist = min_dist
                best_point = p

        # 找到插入代价最小的位置
        best_pos = 0
        best_cost = float("inf")
        for i in range(len(tour) - 1):
            cost = (dist_matrix[tour[i]][best_point] +
                    dist_matrix[best_point][tour[i + 1]] -
                    dist_matrix[tour[i]][tour[i + 1]])
            if cost < best_cost:
                best_cost = cost
                best_pos = i + 1

        tour.insert(best_pos, best_point)
        remaining.discard(best_point)

    return tour[:-1]  # 移除闭合的起点


def two_opt_improve(
    order: List[int],
    dist_matrix: List[List[float]],
    max_iterations: int = 1000,
) -> List[int]:
    """2-opt 局部搜索优化

    对每条不相邻的边对 (i,i+1) 和 (j,j+1)：
    若交换后的总距离更短，则反转子路径 [i+1, j]。

    时间复杂度: O(n²·m)，其中 m 为迭代次数（通常 < 10）
    对于 n ≤ 20，运行时间 < 0.1 秒

    Args:
        order: 初始访问顺序（索引列表）
        dist_matrix: 距离矩阵
        max_iterations: 最大迭代次数

    Returns:
        优化后的访问顺序
    """
    n = len(order)
    if n <= 3:
        return order[:]

    tour = order[:]
    improved = True
    iteration = 0

    while improved and iteration < max_iterations:
        improved = False
        iteration += 1

        # 开放路径：不连接首尾，仅检查内部边
        for i in range(n - 2):
            i_next = i + 1
            for j in range(i + 2, n - 1):
                j_next = j + 1

                # 2-opt 交换条件
                current_cost = dist_matrix[tour[i]][tour[i_next]] + dist_matrix[tour[j]][tour[j_next]]
                new_cost = dist_matrix[tour[i]][tour[j]] + dist_matrix[tour[i_next]][tour[j_next]]

                if new_cost < current_cost:
                    # 反转子路径 [i+1, j]
                    rev_start = i + 1
                    rev_end = j
                    while rev_start < rev_end:
                        tour[rev_start], tour[rev_end] = tour[rev_end], tour[rev_start]
                        rev_start += 1
                        rev_end -= 1
                    improved = True

    return tour


def solve_tsp(
    points: List[Tuple[float, float]],
    method: str = "2opt",
    start_idx: int = 0,
    dist_matrix: Optional[List[List[float]]] = None,
) -> List[int]:
    """统一 TSP 求解入口

    Args:
        points: 经纬度坐标列表 [(lat, lon), ...]
        method: 求解方法
            - "greedy": 贪心最近邻（快速，近似解）
            - "farthest": 最远插入（贪心替代）
            - "2opt": 贪心 + 2-opt 优化（质量最优，推荐）
        start_idx: 起始点索引，默认 0
        dist_matrix: 预计算的距离矩阵（可选，传入可复用）

    Returns:
        访问顺序（索引列表）

    Example:
        points = [(39.9, 116.4), (31.2, 121.5), (23.1, 113.3)]
        order = solve_tsp(points, method="2opt")
        # order = [0, 2, 1]  按此顺序访问总距离最短
    """
    n = len(points)
    if n <= 2:
        return list(range(n))

    if dist_matrix is None:
        dist_matrix = _build_distance_matrix(points)

    if method == "farthest":
        tour = solve_tsp_farthest_insertion(points, start_idx, dist_matrix)
    else:
        tour = solve_tsp_greedy(points, start_idx, dist_matrix)

    if method == "2opt":
        tour = two_opt_improve(tour, dist_matrix)

    return tour


def tour_distance(
    order: List[int],
    dist_matrix: List[List[float]],
    closed: bool = False,
) -> float:
    """计算路线总距离

    Args:
        order: 访问顺序
        dist_matrix: 距离矩阵
        closed: 是否闭合（返回起点）

    Returns:
        总距离
    """
    total = 0.0
    for i in range(len(order) - 1):
        total += dist_matrix[order[i]][order[i + 1]]
    if closed and len(order) > 1:
        total += dist_matrix[order[-1]][order[0]]
    return total
