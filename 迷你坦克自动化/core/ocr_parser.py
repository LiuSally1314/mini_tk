# ============================================
# OCR 通用初次处理
#
# 只做与业务无关的清洗与结构化：
#   - 文本清洗（去空白 / Unicode 归一化 / 可选去标点）
#   - 四点包围盒 → 中心点 + 左上/右下边界
#   - 区域 / 范围 / 谓词过滤
#   - 关键词查找 / 最近邻查找
#   - 按 y 基线分组 / 按 y 聚类成行
#
# 不包含任何业务字段（建筑、时间、资源……）。
# 业务解析请写在各 core/flows/<name>.py 里。
# ============================================

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


# ------------------------------------------------------------
# 数据结构
# ------------------------------------------------------------
@dataclass
class OcrItem:
    text: str                 # 清洗后文本
    raw_text: str             # 原始文本
    cx: float                 # 中心 x
    cy: float                 # 中心 y
    x1: float                 # 左上 x
    y1: float                 # 左上 y
    x2: float                 # 右下 x
    y2: float                 # 右下 y
    score: float = 1.0        # 置信度
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "raw_text": self.raw_text,
            "cx": self.cx, "cy": self.cy,
            "x1": self.x1, "y1": self.y1,
            "x2": self.x2, "y2": self.y2,
            "score": self.score,
        }

    def __repr__(self):
        return f"<OcrItem '{self.text}' @({self.cx:.0f},{self.cy:.0f})>"


# ------------------------------------------------------------
# 文本清洗
# ------------------------------------------------------------
def clean_text(text: str,
               strip_space: bool = True,
               normalize_unicode: bool = True,
               remove_punct: bool = False) -> str:
    """通用文本清洗，不带任何业务含义"""
    if not text:
        return ""
    text = str(text)

    if normalize_unicode:
        text = unicodedata.normalize("NFKC", text)

    if strip_space:
        text = re.sub(r"\s+", "", text)

    if remove_punct:
        text = re.sub(r"[，。！？：；、,.!?:;·…—\-_/\\|]+", "", text)

    return text.strip()


# ------------------------------------------------------------
# 坐标工具
# ------------------------------------------------------------
def box_to_bounds(box) -> Tuple[float, float, float, float]:
    """四点 → (x1, y1, x2, y2)"""
    xs = [float(p[0]) for p in box]
    ys = [float(p[1]) for p in box]
    return min(xs), min(ys), max(xs), max(ys)


def box_to_center(box) -> Tuple[float, float]:
    """四点 → 中心点"""
    xs = [float(p[0]) for p in box]
    ys = [float(p[1]) for p in box]
    return sum(xs) / len(xs), sum(ys) / len(ys)


# ------------------------------------------------------------
# 主入口：原始 OCR → OcrItem 列表
# ------------------------------------------------------------
def parse_page_data(
    page_data,
    strip_space: bool = True,
    normalize_unicode: bool = True,
    drop_empty: bool = True,
    min_score: float = 0.0,
    sort_by: Optional[str] = "y",     # "y" / "x" / None
) -> List[OcrItem]:
    """
    RapidOCR 原始输出 → OcrItem 列表。

    兼容两种输入：
      A. [[box, text, score], ...]                 （ocr_finder.get_page_ocr_data）
      B. [[text, [cx,cy], [x1,y1], ...], ...]      （texts_with_boxes 形式）
    """
    if not page_data:
        return []

    items: List[OcrItem] = []

    for row in page_data:
        # ---------- 形态 A：RapidOCR 原生 ----------
        if len(row) == 3 and not isinstance(row[0], str):
            box, text, score = row
            cx, cy = box_to_center(box)
            x1, y1, x2, y2 = box_to_bounds(box)
            raw_text = str(text)

        # ---------- 形态 B：texts_with_boxes ----------
        elif len(row) >= 2 and isinstance(row[0], str):
            raw_text = row[0]
            cx, cy = float(row[1][0]), float(row[1][1])
            if len(row) >= 6:
                pts = row[2:6]
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
            else:
                x1, y1, x2, y2 = cx, cy, cx, cy
            score = 1.0

        else:
            continue

        text = clean_text(raw_text,
                          strip_space=strip_space,
                          normalize_unicode=normalize_unicode)

        if drop_empty and not text:
            continue
        if score < min_score:
            continue

        items.append(OcrItem(
            text=text, raw_text=raw_text,
            cx=cx, cy=cy, x1=x1, y1=y1, x2=x2, y2=y2,
            score=float(score),
        ))

    if sort_by == "y":
        items.sort(key=lambda it: (it.cy, it.cx))
    elif sort_by == "x":
        items.sort(key=lambda it: (it.cx, it.cy))

    return items


# ------------------------------------------------------------
# 通用过滤
# ------------------------------------------------------------
def filter_by_region(
    items: List[OcrItem],
    region: Tuple[float, float, float, float],
) -> List[OcrItem]:
    """按矩形区域过滤（判断中心点是否在区域内）"""
    x1, y1, x2, y2 = region
    return [it for it in items if x1 <= it.cx <= x2 and y1 <= it.cy <= y2]


def filter_by_range(
    items: List[OcrItem],
    x_min: Optional[float] = None, x_max: Optional[float] = None,
    y_min: Optional[float] = None, y_max: Optional[float] = None,
) -> List[OcrItem]:
    """按 x / y 数值范围过滤"""
    out = []
    for it in items:
        if x_min is not None and it.cx < x_min:
            continue
        if x_max is not None and it.cx > x_max:
            continue
        if y_min is not None and it.cy < y_min:
            continue
        if y_max is not None and it.cy > y_max:
            continue
        out.append(it)
    return out


def filter_by_predicate(
    items: List[OcrItem],
    predicate: Callable[[OcrItem], bool],
) -> List[OcrItem]:
    return [it for it in items if predicate(it)]


# ------------------------------------------------------------
# 通用查找
# ------------------------------------------------------------
def find_by_text(
    items: List[OcrItem],
    keyword: str,
    exact: bool = True,
    region: Optional[Tuple[float, float, float, float]] = None,
) -> List[OcrItem]:
    """按文本查（可精确/模糊，可限定区域）"""
    out = []
    for it in items:
        ok = (it.text == keyword) if exact else (keyword in it.text)
        if not ok:
            continue
        if region:
            x1, y1, x2, y2 = region
            if not (x1 <= it.cx <= x2 and y1 <= it.cy <= y2):
                continue
        out.append(it)
    return out


def find_nearest(
    items: List[OcrItem],
    target: Tuple[float, float],
    region: Optional[Tuple[float, float, float, float]] = None,
) -> Optional[OcrItem]:
    """在可选区域内找离 target 最近的 item"""
    tx, ty = target
    best, best_d = None, float("inf")
    for it in items:
        if region:
            x1, y1, x2, y2 = region
            if not (x1 <= it.cx <= x2 and y1 <= it.cy <= y2):
                continue
        d = (it.cx - tx) ** 2 + (it.cy - ty) ** 2
        if d < best_d:
            best_d, best = d, it
    return best


# ------------------------------------------------------------
# 通用分组 / 行聚类
# ------------------------------------------------------------
def group_by_row(
    items: List[OcrItem],
    base_y: float,
    row_height: float = 127.0,
    offset: float = 50.0,
) -> Dict[int, List[OcrItem]]:
    """
    以 base_y 为基线，按固定行高把 items 分组。
    返回 {row_key: [item, ...]}，row_key 从 0 开始，行内按 x 排序。
    """
    rows: Dict[int, List[OcrItem]] = {}
    for it in items:
        if it.cy <= base_y + offset:
            continue
        row_key = round((it.cy - base_y) / row_height)
        rows.setdefault(row_key, []).append(it)
    for k in rows:
        rows[k].sort(key=lambda it: it.cx)
    return rows


def merge_lines(
    items: List[OcrItem],
    y_tolerance: float = 15.0,
    x_gap: float = 40.0,
) -> List[List[OcrItem]]:
    """
    通用行聚类：把 y 相近的 items 归到一行。
    返回 [[item, item, ...], ...]，按 y 从上到下。
    """
    if not items:
        return []

    sorted_items = sorted(items, key=lambda it: (it.cy, it.cx))
    lines: List[List[OcrItem]] = []
    cur_line: List[OcrItem] = []
    cur_y: Optional[float] = None

    for it in sorted_items:
        if cur_y is None or abs(it.cy - cur_y) <= y_tolerance:
            cur_line.append(it)
            cur_y = it.cy if cur_y is None else (cur_y + it.cy) / 2
        else:
            lines.append(sorted(cur_line, key=lambda x: x.cx))
            cur_line = [it]
            cur_y = it.cy

    if cur_line:
        lines.append(sorted(cur_line, key=lambda x: x.cx))
    return lines


def lines_to_text(lines: List[List[OcrItem]],
                  sep: str = " ",
                  join_vertical: str = "\n") -> str:
    """把行聚类结果拼成多行文本"""
    return join_vertical.join(sep.join(it.text for it in ln) for ln in lines)