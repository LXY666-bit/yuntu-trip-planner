import math
import re
from typing import List, Dict, Optional


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def _cluster_attractions_by_proximity(attractions: List[Dict], num_days: int) -> List[List[Dict]]:
    """使用 K-Means++ 初始化 + 迭代优化 + 最大簇直径约束的聚类算法

    相比旧的单链聚合层次聚类, 此算法确保:
    1. 同一天内的景点地理上紧凑 (K-Means 天然保证)
    2. 不会出现跨城链条效应 (max_diameter 硬约束)
    3. 每天景点数尽量均衡
    """
    n = len(attractions)
    if n == 0:
        return []
    if n <= num_days:
        return [[a] for a in attractions]

    # 预计算距离矩阵 (所有后续步骤共用)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = _haversine_distance(
                attractions[i]["latitude"], attractions[i]["longitude"],
                attractions[j]["latitude"], attractions[j]["longitude"],
            )
            dist[i][j] = d
            dist[j][i] = d

    # K-Means++ 初始化: 选 K 个互相远离的种子点
    centroids = [0]  # 第一个随机选
    while len(centroids) < min(num_days, n):
        best_idx = -1
        best_min_d = -1.0
        for i in range(n):
            if i in centroids:
                continue
            min_d = min(dist[i][c] for c in centroids)
            if min_d > best_min_d:
                best_min_d = min_d
                best_idx = i
        centroids.append(best_idx)

    # 迭代分配: 每个点归属到最近的中心
    labels = [-1] * n
    for iteration in range(10):  # 最多10轮
        changed = False
        for i in range(n):
            best_c = -1
            best_d = float("inf")
            for ci, c in enumerate(centroids):
                if dist[i][c] < best_d:
                    best_d = dist[i][c]
                    best_c = ci
            if labels[i] != best_c:
                labels[i] = best_c
                changed = True

        if not changed:
            break

        # 重新计算每个簇的中心点 (取离簇内其他点总距离最小的点)
        for ci in range(len(centroids)):
            members = [i for i, lb in enumerate(labels) if lb == ci]
            if not members:
                continue
            best_center = members[0]
            best_total_d = float("inf")
            for m in members:
                total_d = sum(dist[m][other] for other in members)
                if total_d < best_total_d:
                    best_total_d = total_d
                    best_center = m
            centroids[ci] = best_center

    # 构建簇
    clusters_indices = [[] for _ in range(len(centroids))]
    for i, lb in enumerate(labels):
        clusters_indices[lb].append(i)

    # 最大簇直径约束: 如果簇内最大距离 > 阈值, 拆出远点
    MAX_CLUSTER_DIAMETER_KM = 25.0
    for ci in range(len(clusters_indices)):
        cluster = clusters_indices[ci]
        if len(cluster) <= 1:
            continue
        # 找簇内直径最大的点对
        max_d = 0.0
        far_a = far_b = 0
        for a in cluster:
            for b in cluster:
                if a < b and dist[a][b] > max_d:
                    max_d = dist[a][b]
                    far_a, far_b = a, b
        if max_d <= MAX_CLUSTER_DIAMETER_KM:
            continue

        # 超标: 把远的一半点移出本簇, 分配到最近的其他簇
        far_set = {far_a}
        for p in cluster:
            if p != far_a:
                d_to_a = dist[p][far_a]
                d_to_b = dist[p][far_b]
                if d_to_a < d_to_b:
                    far_set.add(p)
        keep = [p for p in cluster if p in far_set]
        remove = [p for p in cluster if p not in far_set]

        if keep:
            clusters_indices[ci] = keep
        # 将移除的点重新分配到最近的其他簇
        for p in remove:
            best_ci = -1
            best_d = float("inf")
            for other_ci, other_cluster in enumerate(clusters_indices):
                if other_ci == ci:
                    continue
                if not other_cluster:
                    best_ci = other_ci
                    break
                d = min(dist[p][q] for q in other_cluster)
                if d < best_d:
                    best_d = d
                    best_ci = other_ci
            if best_ci >= 0:
                clusters_indices[best_ci].append(p)
            else:
                clusters_indices[ci].append(p)  # 无处可去, 保留

    # 去除空簇
    clusters_indices = [c for c in clusters_indices if c]

    return [[attractions[i] for i in cluster] for cluster in clusters_indices]


def _cluster_centroid(cluster: List[Dict]) -> tuple:
    """计算簇的地理质心"""
    if not cluster:
        return (0.0, 0.0)
    lats = [a["latitude"] for a in cluster]
    lons = [a["longitude"] for a in cluster]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def _cluster_total_minutes(cluster: List[Dict], durations: Dict[str, int]) -> int:
    """计算簇内所有景点的预计游玩总时长"""
    return sum(durations.get(a["name"], 0) for a in cluster)


def _rebalance_by_duration(
    clusters: List[List[Dict]],
    durations: Dict[str, int],
    max_minutes: int = 480,
    max_iterations: int = 5,
) -> List[List[Dict]]:
    """若某天总时长超出 max_minutes，把离该天质心最远的景点
    移到时长最少且地理上接近的相邻日。

    最多迭代 max_iterations 轮，无法继续优化时停止。
    每个 cluster 重新做 TSP 排序。
    """
    work = [list(c) for c in clusters]

    for _ in range(max_iterations):
        totals = [_cluster_total_minutes(c, durations) for c in work]
        over_idx = max(range(len(totals)), key=lambda i: totals[i])
        if totals[over_idx] <= max_minutes or len(work[over_idx]) <= 1:
            break

        src_cluster = work[over_idx]
        src_lat, src_lon = _cluster_centroid(src_cluster)

        far_idx, far_dist = 0, -1.0
        for i, attr in enumerate(src_cluster):
            d = _haversine_distance(src_lat, src_lon, attr["latitude"], attr["longitude"])
            if d > far_dist:
                far_dist = d
                far_idx = i
        far_attr = src_cluster[far_idx]
        far_minutes = durations.get(far_attr["name"], 0)

        best_target = None
        best_score = float("inf")
        for j, target_cluster in enumerate(work):
            if j == over_idx:
                continue
            if totals[j] + far_minutes > max_minutes:
                continue
            t_lat, t_lon = _cluster_centroid(target_cluster)
            geo_d = _haversine_distance(t_lat, t_lon, far_attr["latitude"], far_attr["longitude"])
            score = totals[j] + geo_d * 10  # 低 total + 地理接近 优先
            if score < best_score:
                best_score = score
                best_target = j

        if best_target is None:
            break

        work[over_idx].pop(far_idx)
        work[best_target].append(far_attr)

    return [_order_cluster_by_tsp(c) for c in work]


def _order_cluster_by_tsp(cluster: List[Dict]) -> List[Dict]:
    if len(cluster) <= 2:
        return cluster

    ordered = [cluster[0]]
    remaining = list(cluster[1:])

    while remaining:
        last = ordered[-1]
        nearest_idx = 0
        nearest_dist = float("inf")
        for i, attr in enumerate(remaining):
            d = _haversine_distance(last["latitude"], last["longitude"], attr["latitude"], attr["longitude"])
            if d < nearest_dist:
                nearest_dist = d
                nearest_idx = i
        ordered.append(remaining.pop(nearest_idx))

    return ordered


def _select_top_attractions(clusters: List[List[Dict]], max_per_day: int = 3) -> List[List[Dict]]:
    result = []
    for cluster in clusters:
        if len(cluster) <= max_per_day:
            result.append(cluster)
        else:
            if len(cluster) > 1:
                center_lat = sum(a["latitude"] for a in cluster) / len(cluster)
                center_lon = sum(a["longitude"] for a in cluster) / len(cluster)
                scored = []
                for attr in cluster:
                    d = _haversine_distance(center_lat, center_lon, attr["latitude"], attr["longitude"])
                    scored.append((attr, d))
                scored.sort(key=lambda x: x[1])
                result.append([s[0] for s in scored[:max_per_day]])
            else:
                result.append(cluster[:max_per_day])
    return result


def _format_cluster_info(clusters: List[List[Dict]], all_attractions: List[Dict], dist_matrix: List[List[float]], trimmed: bool = False) -> str:
    lines = ["=== 每日景点分组建议（基于地理位置聚类） ===", ""]

    if trimmed:
        lines.append("⚠️ 景点数量超过每天3个的上限，已按距离聚类中心最近的原则筛选，保留每天最多3个景点")
        lines.append("")

    for day_idx, cluster in enumerate(clusters):
        lines.append(f"第{day_idx + 1}天建议景点:")
        for order_idx, attr in enumerate(cluster):
            lines.append(f"  {order_idx + 1}. {attr['name']} ({attr['longitude']:.4f}, {attr['latitude']:.4f})")

        if len(cluster) > 1:
            max_dist = 0
            for i in range(len(cluster)):
                for j in range(i + 1, len(cluster)):
                    ci = all_attractions.index(cluster[i])
                    cj = all_attractions.index(cluster[j])
                    max_dist = max(max_dist, dist_matrix[ci][cj])
            lines.append(f"  组内最大距离: {max_dist:.1f}km")
        lines.append("")

    selected_names = set()
    for cluster in clusters:
        for attr in cluster:
            selected_names.add(attr["name"])

    lines.append("=== 选中景点间距离矩阵 (km) ===")
    lines.append("")

    selected_attrs = [a for a in all_attractions if a["name"] in selected_names]
    if len(selected_attrs) > 1:
        name_col_width = max(len(a["name"]) for a in selected_attrs) + 2
        header = " " * name_col_width
        for attr in selected_attrs:
            header += f"{attr['name'][:6]:>8}"
        lines.append(header)

        for i, attr in enumerate(selected_attrs):
            ci = all_attractions.index(attr)
            row = f"{attr['name'][:name_col_width - 1]:<{name_col_width}}"
            for j, attr_j in enumerate(selected_attrs):
                if i == j:
                    row += f"{'--':>8}"
                else:
                    cj = all_attractions.index(attr_j)
                    row += f"{dist_matrix[ci][cj]:>7.1f}"
            lines.append(row)

    return "\n".join(lines)


def _extract_coordinates_regex(text: str) -> List[Dict]:
    attractions = []

    amap_location_pattern = re.compile(
        r'"?name"?\s*[:=]\s*["\']([^"\']+)["\'].*?'
        r'"?location"?\s*[:=]\s*["\']([\d.]+)\s*,\s*([\d.]+)["\']',
        re.DOTALL | re.IGNORECASE
    )
    for m in amap_location_pattern.finditer(text):
        name = m.group(1).strip()
        try:
            lon = float(m.group(2))
            lat = float(m.group(3))
            if 73 < lon < 136 and 3 < lat < 54:
                attractions.append({"name": name, "longitude": lon, "latitude": lat})
        except ValueError:
            continue

    if attractions:
        return attractions

    name_lon_lat = re.compile(
        r'"?name"?\s*[:=]\s*["\']([^"\']+)["\'].*?'
        r'"?longitude"?\s*[:=]\s*["\']?([\d.]+)["\']?.*?'
        r'"?latitude"?\s*[:=]\s*["\']?([\d.]+)["\']?',
        re.DOTALL | re.IGNORECASE
    )
    for m in name_lon_lat.finditer(text):
        name = m.group(1).strip()
        try:
            lon = float(m.group(2))
            lat = float(m.group(3))
            if 73 < lon < 136 and 3 < lat < 54:
                attractions.append({"name": name, "longitude": lon, "latitude": lat})
        except ValueError:
            continue

    if attractions:
        return attractions

    lon_lat_name = re.compile(
        r'"?longitude"?\s*[:=]\s*["\']?([\d.]+)["\']?.*?'
        r'"?latitude"?\s*[:=]\s*["\']?([\d.]+)["\']?.*?'
        r'"?name"?\s*[:=]\s*["\']([^"\']+)["\']',
        re.DOTALL | re.IGNORECASE
    )
    for m in lon_lat_name.finditer(text):
        name = m.group(3).strip()
        try:
            lon = float(m.group(1))
            lat = float(m.group(2))
            if 73 < lon < 136 and 3 < lat < 54:
                attractions.append({"name": name, "longitude": lon, "latitude": lat})
        except ValueError:
            continue

    if attractions:
        return attractions

    location_pattern = re.compile(
        r'"?(?:location|坐标)"?\s*[:=]\s*\{[^}]*?"?lon(?:gitude)?"?\s*[:=]\s*["\']?([\d.]+)["\']?\s*,\s*"?lat(?:itude)?"?\s*[:=]\s*["\']?([\d.]+)["\']?',
        re.DOTALL | re.IGNORECASE
    )
    name_pattern = re.compile(r'"?name"?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)

    locations = list(location_pattern.finditer(text))
    names = name_pattern.findall(text)

    for i, m in enumerate(locations):
        try:
            lon = float(m.group(1))
            lat = float(m.group(2))
            if 73 < lon < 136 and 3 < lat < 54:
                name = names[i].strip() if i < len(names) else f"景点{i+1}"
                attractions.append({"name": name, "longitude": lon, "latitude": lat})
        except (ValueError, IndexError):
            continue

    return attractions
