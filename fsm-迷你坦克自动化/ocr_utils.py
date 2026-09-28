import re
import yaml
from rapidocr import RapidOCR

from keyword_matcher import check_keywords_match


# =========================================================
# OCR 引擎单例（避免反复重建）
# =========================================================
_ocr_engine = None


def _get_engine():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine


# =========================================================
# 页面配置读取
# =========================================================
def load_pages_config(pages_yaml: str) -> dict:
    """读取统一的 pages.yaml，返回 {page_name: page_cfg}"""
    with open(pages_yaml, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("pages", {})


# =========================================================
# OCR 基础
# =========================================================
def _run_ocr(image):
    """
    对图像执行 OCR。

    image 可以是：
      - 文件路径 str
      - numpy.ndarray（实时截图）
      - PIL.Image

    返回 [{text, box, cx, cy, h}, ...]；无文字返回 []
    """
    engine = _get_engine()
    result = engine(image)

    if not result or not result.txts:
        return []

    items = []
    for txt, box in zip(result.txts, result.boxes):
        pts = [[int(x), int(y)] for x, y in box.tolist()]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        items.append({
            "text": txt,
            "box": [min(xs), min(ys), max(xs), max(ys)],
            "cx": (min(xs) + max(xs)) // 2,
            "cy": (min(ys) + max(ys)) // 2,
            "h": max(ys) - min(ys),
        })
    return items


def _get_image_height(image, items=None) -> int:
    """获取图像高度，兼容 numpy / 路径 / PIL。"""
    try:
        return int(image.shape[0])
    except AttributeError:
        pass

    if isinstance(image, str):
        import cv2
        arr = cv2.imread(image)
        if arr is not None:
            return int(arr.shape[0])

    # 兜底：用 OCR 结果估计
    if items:
        return int(max(it["cy"] for it in items) * 2)
    return 0


# =========================================================
# 通用文本匹配（统一 match_mode 约定）
# =========================================================
def _text_matches(t: str, text: str, match_mode: str = "exact") -> bool:
    """
    判断单条 OCR 文本是否命中目标文本。

    match_mode:
      - exact    : strip 后完全相等
      - contains : 包含即可
      - regex    : text 作为正则 pattern 去 search
    """
    if match_mode == "regex":
        return re.search(text, t) is not None

    stripped = t.strip()
    if match_mode == "contains":
        return text in stripped
    # 默认 exact
    return stripped == text


def find_text_items(items, text: str, match_mode: str = "exact"):
    """
    在 OCR 结果 items 中查找文本，返回所有命中的 item 列表。

    Args:
        items: _run_ocr 返回的列表
        text: 目标文本
        match_mode: exact / contains / regex

    Returns:
        命中的 item 列表（可能为空）
    """
    return [it for it in items if _text_matches(it["text"], text, match_mode)]


def find_text(items, text: str, match_mode: str = "exact"):
    """
    在 OCR 结果 items 中查找文本，返回第一个命中项 (text, (cx, cy)) 或 (None, None)。

    注意：若页面有多个候选，建议改用 find_text_items + 自行排序（如取离中心最近）。
    """
    hits = find_text_items(items, text, match_mode)
    if not hits:
        return None, None
    it = hits[0]
    return it["text"], (it["cx"], it["cy"])


# =========================================================
# 页面校验
# =========================================================
def check_page(image, page_cfg: dict, debug: bool = False) -> bool:
    """用 page_cfg['confirm_keyword'] 校验截图是否为该页面。"""
    confirm_keyword = page_cfg.get("confirm_keyword")
    if not confirm_keyword:
        return True

    items = _run_ocr(image)
    texts = [it["text"] for it in items]

    matched = any(check_keywords_match(t, confirm_keyword) for t in texts)

    if debug:
        page_name = page_cfg.get("page_name", "?")
        print(f"[Page] 校验页面 '{page_name}' -> {'通过' if matched else '未通过'}")
        print(f"[Page] OCR 文本: {texts}")

    return matched


# =========================================================
# 技能数据（主界面）
# =========================================================
def load_skills_from_ocr(
    image,
    lv_pattern: str,
    icon_offset: int = 0,
    row_tol_mode: str = "auto",
    row_tol_manual: float = 0.0,
    debug: bool = False,
):
    """
    从主界面截图识别技能等级，返回 (skills, max_level)。

    skills: [{
        id, current_clicks, target_clicks, box, center
    }, ...]
    """
    pattern = re.compile(lv_pattern)
    items = _run_ocr(image)

    skills = []
    for it in items:
        m = pattern.search(it["text"])
        if not m:
            continue
        skills.append({
            "current": int(m.group(1)),
            "target": int(m.group(2)),
            "text": it["text"],
            "box": it["box"],
            "cx": it["cx"],
            "cy": it["cy"],
            "h": it["h"],
        })

    if not skills:
        raise RuntimeError("未识别到任何 LV.x/y 技能等级文本")

    # 行容差
    if row_tol_mode == "auto":
        heights = [s["h"] for s in skills if s["h"] > 0]
        row_tol = float(sum(heights) / len(heights)) if heights else 0.0
    else:
        row_tol = float(row_tol_manual)

    # 按行分组：先按 cy 排序，再按行聚合
    skills.sort(key=lambda e: e["cy"])
    rows = []
    for e in skills:
        placed = False
        for row in rows:
            if abs(row[0]["cy"] - e["cy"]) < row_tol:
                row.append(e)
                placed = True
                break
        if not placed:
            rows.append([e])

    # 行内按 cx 排序
    for row in rows:
        row.sort(key=lambda e: e["cx"])

    ordered = [e for row in rows for e in row]

    result_skills = []
    for i, s in enumerate(ordered, 1):
        result_skills.append({
            "id": i,
            "current_clicks": s["current"],
            "target_clicks": s["target"],
            "box": s["box"],
            "center": (s["cx"], max(0, s["cy"] - icon_offset)),
        })

    max_level = max(s["target_clicks"] for s in result_skills)

    if debug:
        print(f"[OCR] 共识别到 {len(result_skills)} 个技能:")
        for s in result_skills:
            print(f"  技能 {s['id']}: {s['current_clicks']}/{s['target_clicks']} "
                  f"box={s['box']} center={s['center']}")
        print(f"[OCR] max_level = {max_level}")

    return result_skills, max_level


# =========================================================
# 升级按钮（弹窗）
# =========================================================
def find_upgrade_button(
    image,
    button_text: str = "升级",
    y_band: tuple = None,
    match_mode: str = "exact",
    debug: bool = False,
):
    """
    从弹窗截图找「升级」按钮。

    策略：
      1. 按 match_mode 找候选；
      2. 若指定 y_band，只保留垂直比例落在该区间的候选；
      3. 在剩余候选中，取 cy 最接近图像垂直中心 H/2 的那个。

    Args:
        image: numpy / 路径 / PIL
        button_text: 按钮文字，默认「升级」
        y_band: (y0_ratio, y1_ratio) 或 None
        match_mode: exact / contains / regex
        debug: 打印调试信息

    Returns:
        (cx, cy) 或 None
    """
    items = _run_ocr(image)

    candidates = find_text_items(items, button_text, match_mode)

    if not candidates:
        if debug:
            print(f"[OCR] 未找到「{button_text}」(mode={match_mode})")
            print(f"[OCR] 当前识别文本: {[it['text'] for it in items]}")
        return None

    H = _get_image_height(image, items)
    center_y = H / 2.0 if H else 0.0

    # y_band 过滤（过滤后为空则回退全部候选）
    if y_band and H:
        y0 = H * float(y_band[0])
        y1 = H * float(y_band[1])
        filtered = [c for c in candidates if y0 <= c["cy"] <= y1]
        if filtered:
            candidates = filtered
        elif debug:
            print(f"[OCR] y_band={y_band} 内无候选，回退到全部候选")

    # 取离图像垂直中心最近的
    candidates.sort(key=lambda e: abs(e["cy"] - center_y))
    btn = candidates[0]
    coord = (btn["cx"], btn["cy"])

    if debug:
        print(f"[OCR] 选中「{btn['text']}」center={coord} "
              f"(H={H}, center_y={center_y:.0f}, y_band={y_band}, mode={match_mode})")
        print(f"[OCR] 全部候选({len(candidates)}): "
              f"{[(c['text'], (c['cx'], c['cy'])) for c in candidates]}")

    return coord