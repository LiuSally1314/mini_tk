# ============================================
# OCR 查找模块 - 负责截图、识别文本并计算点击坐标
# 支持：全局查找 / 按坐标区域限定查找 / 顺序排列与索引选择
# ============================================

import os
import time
import threading
from typing import Optional, Tuple, Dict, List
from rapidocr_onnxruntime import RapidOCR
from core.device import DeviceManager


class OcrFinder:
    """结合 DeviceManager 截图并通过 RapidOCR 查找文字坐标"""

    def __init__(self, base_dir: str = "截屏"):
        self.base_dir = base_dir
        self.engine = RapidOCR()
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir, exist_ok=True)

    @staticmethod
    def sort_boxes_top_to_bottom_left_to_right(ocr_results, row_threshold: float = 15.0):
        """
        将 OCR 识别到的列表按照「从上到下，从左到右」的规则排序。
        :param row_threshold: 判定为同一行的 y 坐标最大相差像素值（容差）
        """
        if not ocr_results:
            return []

        # 1. 提取中心点坐标 (cx, cy)
        items = []
        for item in ocr_results:
            box = item[0]
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            items.append({
                "cx": cx,
                "cy": cy,
                "raw": item
            })

        # 2. 先按 cy 排序
        items.sort(key=lambda x: x["cy"])

        # 3. 按行分组（y 距离小于 row_threshold 归为同一行）
        rows = []
        for item in items:
            placed = False
            for row in rows:
                if abs(item["cy"] - row[0]["cy"]) < row_threshold:
                    row.append(item)
                    placed = True
                    break
            if not placed:
                rows.append([item])

        # 4. 每行按 cx 从左到右排序并平铺返回
        sorted_results = []
        for row in rows:
            row.sort(key=lambda x: x["cx"])
            for item in row:
                sorted_results.append(item["raw"])

        return sorted_results

    def _snapshot_and_ocr(self, dm: DeviceManager,
                          retry: int = 2,
                          interval: float = 0.3):
        """
        截图 + OCR，带重试。
        返回 RapidOCR 原始结果 [[box, text, score], ...]（已按从上到下、从左到右排序）；
        失败返回 None。
        """
        for attempt in range(retry + 1):
            ts = time.strftime("%Y%m%d_%H%M%S")
            ms = int(time.time() * 1000) % 1000
            tid = threading.get_ident()
            img_path = os.path.join(
                self.base_dir, f"ocr_{ts}_{ms:03d}_{tid}.png"
            )

            saved_path = dm.snapshot(img_path)
            if not saved_path or not os.path.exists(saved_path):
                print(f"  ⚠️ 截图失败（{attempt + 1}/{retry + 1}）")
                if attempt < retry:
                    time.sleep(interval)
                continue

            try:
                result, _ = self.engine(saved_path)
            except Exception as e:
                print(f"  ⚠️ OCR 引擎异常（{attempt + 1}/{retry + 1}）: {e}")
                result = None
            finally:
                try:
                    os.remove(saved_path)
                except Exception:
                    pass

            if result:
                # 按从上到下，从左到右排序后返回
                return self.sort_boxes_top_to_bottom_left_to_right(result)

            if attempt < retry:
                time.sleep(interval)

        print("  ❌ 截图/OCR 最终失败")
        return None

    @staticmethod
    def _box_center(box) -> Tuple[float, float]:
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        return sum(xs) / len(xs), sum(ys) / len(ys)

    @staticmethod
    def _in_region(coord: Tuple[float, float],
                   region: Optional[Tuple[float, float, float, float]]) -> bool:
        if region is None:
            return True
        x, y = coord
        x1, y1, x2, y2 = region
        return x1 <= x <= x2 and y1 <= y <= y2

    @staticmethod
    def make_region(center: Tuple[float, float],
                    half_w: float, half_h: float
                    ) -> Tuple[float, float, float, float]:
        cx, cy = center
        return cx - half_w, cy - half_h, cx + half_w, cy + half_h

    def find_text(self, dm: DeviceManager, target_text: str,
                  exact: bool = True,
                  region: Optional[Tuple[float, float, float, float]] = None,
                  index: int = 0
                  ) -> Optional[Tuple[float, float]]:
        result = self._snapshot_and_ocr(dm)
        if not result:
            return None

        matched_coords = []
        for box, text, score in result:
            text_str = str(text).strip()
            is_match = (text_str == target_text) if exact else (target_text in text_str)
            if not is_match:
                continue

            center_x, center_y = self._box_center(box)
            if not self._in_region((center_x, center_y), region):
                continue

            matched_coords.append((center_x, center_y, text_str, score))

        if not matched_coords:
            return None

        # 校验 index 是否越界
        if index >= len(matched_coords) or index < -len(matched_coords):
            print(f"  ⚠️ OCR 找到 {len(matched_coords)} 个「{target_text}」，但指定索引 index={index} 超出范围")
            return None

        target_x, target_y, text_str, score = matched_coords[index]
        print(f"  🔍 OCR 找到 {len(matched_coords)} 个「{target_text}」，"
              f"选中第 {index if index >= 0 else len(matched_coords) + index + 1} 个 ({target_x:.0f}, {target_y:.0f}) "
              f"(匹配结果: {text_str}, 置信度: {score:.2f})")
        return target_x, target_y

    def find_texts(self, dm, targets, exact=True, region=None, indexes=None):
        if indexes is None:
            indexes = {}

        found = {k: None for k in targets}
        result = self._snapshot_and_ocr(dm)
        if not result:
            return found

        def _match_one(text_str: str, target) -> bool:
            if isinstance(target, (list, tuple)):
                if exact:
                    return any(text_str == t for t in target)
                return any(t in text_str for t in target)
            if exact:
                return text_str == target
            return target in text_str

        matches_dict = {k: [] for k in targets}

        for box, text, score in result:
            text_str = str(text).strip()
            for alias, target_text in targets.items():
                if not _match_one(text_str, target_text):
                    continue

                center_x, center_y = self._box_center(box)
                if not self._in_region((center_x, center_y), region):
                    continue

                matches_dict[alias].append((center_x, center_y, text_str, score))

        for alias, matches in matches_dict.items():
            if not matches:
                continue
            idx = indexes.get(alias, 0)
            if idx >= len(matches) or idx < -len(matches):
                print(f"  ⚠️ OCR 找到 {len(matches)} 个「{alias}」，但指定索引 index={idx} 超出范围")
                continue

            cx, cy, text_str, score = matches[idx]
            found[alias] = (cx, cy)
            print(f"  🔍 OCR 找到 {len(matches)} 个「{alias}」，"
                  f"选中第 {idx + 1 if idx >= 0 else len(matches) + idx + 1} 个 ({cx:.0f}, {cy:.0f}) "
                  f"(实际: {text_str}, 置信度: {score:.2f})")

        return found

    def find_page_text(self, dm: DeviceManager,
                       region: Optional[Tuple[float, float, float, float]] = None
                       ) -> Optional[str]:
        result = self._snapshot_and_ocr(dm)
        if result is None:
            return None

        lines: List[str] = []
        for box, text, score in result:
            text_str = str(text).strip()
            if not text_str:
                continue
            if region is not None:
                cx, cy = self._box_center(box)
                if not self._in_region((cx, cy), region):
                    continue
            lines.append(text_str)

        return "\n".join(lines)

    def get_page_ocr_data(self, dm: DeviceManager):
        return self._snapshot_and_ocr(dm)