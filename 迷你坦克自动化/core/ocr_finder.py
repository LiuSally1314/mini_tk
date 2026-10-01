# ============================================
# OCR 查找模块 - 负责截图、识别文本并计算点击坐标
# 支持：全局查找 / 按坐标区域限定查找
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

    def _snapshot_and_ocr(self, dm: DeviceManager,
                          retry: int = 2,
                          interval: float = 0.3):
        """
        截图 + OCR，带重试。
        返回 RapidOCR 原始结果 [[box, text, score], ...]；
        彻底失败返回 None。
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
                return result

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
                  region: Optional[Tuple[float, float, float, float]] = None
                  ) -> Optional[Tuple[float, float]]:
        result = self._snapshot_and_ocr(dm)
        if not result:
            return None

        for box, text, score in result:
            text_str = str(text).strip()
            is_match = (text_str == target_text) if exact else (target_text in text_str)
            if not is_match:
                continue

            center_x, center_y = self._box_center(box)
            if not self._in_region((center_x, center_y), region):
                continue

            print(f"  🔍 OCR 找到目标「{target_text}」 "
                  f"(匹配结果: {text_str}, 置信度: {score:.2f})")
            return center_x, center_y

        return None

    def find_texts(self, dm, targets, exact=True, region=None):
        found = {k: None for k in targets}
        result = self._snapshot_and_ocr(dm)
        if not result:
            return found

        def _match_one(text_str: str, target) -> bool:
            # ← 这里新增：支持 list（OR 语义）
            if isinstance(target, (list, tuple)):
                if exact:
                    return any(text_str == t for t in target)
                return any(t in text_str for t in target)
            if exact:
                return text_str == target
            return target in text_str

        for box, text, score in result:
            text_str = str(text).strip()
            for alias, target_text in targets.items():
                if found[alias] is not None:
                    continue
                if not _match_one(text_str, target_text):  # ← 改用 _match_one
                    continue

                center_x, center_y = self._box_center(box)
                if not self._in_region((center_x, center_y), region):
                    continue

                found[alias] = (center_x, center_y)
                print(f"  🔍 OCR 找到「{alias}」=「{target_text}」 "
                      f"(实际: {text_str}, 置信度: {score:.2f})")

        return found

    def find_page_text(self, dm: DeviceManager,
                       region: Optional[Tuple[float, float, float, float]] = None
                       ) -> Optional[str]:
        """
        返回整页 OCR 文本（按行合并为 \\n 分隔的字符串）。
        调用方若需精确逐行匹配，自行 splitlines()。
        """
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