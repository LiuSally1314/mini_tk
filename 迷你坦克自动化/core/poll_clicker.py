# ============================================
# 轮询点击模块（通用）
#
# 用途：
#   反复点击同一坐标（或坐标列表中的每一项），直到页面出现/消失指定文本。
#
# 典型场景：
#   - 「常规技能」区域 2×2 技能依次升级：点一下技能 → 点「升级」→ 页面自动关闭
#   - 一个技能点满后换下一个坐标
#
# 与业务无关，只认文本与坐标，不认"技能"概念。
# ============================================

import time
from typing import Optional, Tuple, List, Union

from core.device import DeviceManager
from core.ocr_finder import OcrFinder
from core.keyword_matcher import check_keywords_match


RESULT_OK = "ok"
RESULT_FINISHED = "finished"
RESULT_ERROR = "error"


class PollClicker:
    """
    轮询点击器：
      1. 若提供 coords_list，遍历每个坐标；
      2. 每个坐标反复点击，直到「expect_text 消失」或达到 max_times；
      3. 若提供 start_text / end_text，则用它们自动推算 2×2 坐标（兼容原技能布局算法）。
    """

    def __init__(self, dm: DeviceManager, finder: OcrFinder,
                 click_coords: Optional[Tuple[float, float]] = None,
                 start_text: Optional[str] = None,
                 end_text: Optional[str] = None,
                 expect_text: Union[str, list, dict] = "升级",
                 click_text: str = "升级",
                 coords_list: Optional[List] = None,
                 max_times: int = 20,
                 interval: float = 1.0,
                 offset_range: int = 30):
        self.dm = dm
        self.finder = finder
        self.click_coords = click_coords
        self.start_text = start_text
        self.end_text = end_text
        self.expect_text = expect_text
        self.click_text = click_text
        self.coords_list = coords_list or []
        self.max_times = max_times
        self.interval = interval
        self.offset_range = offset_range

        self.stats = {
            "processed": 0,
            "finished": 0,
            "clicks": 0,
            "errors": 0,
        }

    # ---------- 兼容原 SkillUpgrader 的 2×2 坐标推算 ----------
    def _apply_offset(self, coord: Tuple[float, float],
                      dx: int = 0, dy: int = 0) -> Tuple[float, float]:
        x, y = coord
        offset_x = max(-self.offset_range, min(self.offset_range, dx))
        offset_y = max(-self.offset_range, min(self.offset_range, dy))
        return x + offset_x, y + offset_y

    def locate_coords(self) -> List[Tuple[float, float]]:
        """根据 start_text / end_text 推算 2×2 区域的四个中心点"""
        if not self.start_text or not self.end_text:
            return []

        page_data = self.finder.get_page_ocr_data(self.dm)
        if not page_data:
            print("  ❌ 无法获取页面 OCR 数据")
            return []

        y_start = None
        y_end = None
        x_split = None

        for box, text, _ in page_data:
            cx, cy = self.finder._box_center(box)
            text_str = str(text).strip()

            if self.start_text in text_str:
                y_start = cy
                x_split = cx
                print(f"  📌 找到「{self.start_text}」: "
                      f"({cx:.0f}, {cy:.0f}) → 区域起点 / 左右分界")
            if self.end_text in text_str:
                y_end = cy
                print(f"  📌 找到「{self.end_text}」: "
                      f"({cx:.0f}, {cy:.0f}) → 区域终点")

        if y_start is None or y_end is None or x_split is None:
            print("  ❌ 区域起止文本不完整，无法推算坐标")
            return []
        if y_end <= y_start:
            print(f"  ❌ 终点 Y({y_end:.0f}) 不大于起点 Y({y_start:.0f})，区间无效")
            return []

        all_xs = [self.finder._box_center(box)[0] for box, _, _ in page_data]
        if not all_xs:
            print("  ❌ 页面无任何 OCR 文本，无法确定左右边界")
            return []

        x_left = min(all_xs)
        x_right = max(all_xs)

        y_mid = (y_start + y_end) / 2.0
        y_span = y_end - y_start
        y_top_center = y_start + y_span / 4.0
        y_bot_center = y_mid + (y_end - y_mid) / 4.0

        x_left_center = (x_left + x_split) / 2.0
        x_right_center = (x_split + x_right) / 2.0

        coords = [
            self._apply_offset((x_left_center, y_top_center), 0, 0),
            self._apply_offset((x_right_center, y_top_center), 0, 0),
            self._apply_offset((x_left_center, y_bot_center), 0, 0),
            self._apply_offset((x_right_center, y_bot_center), 0, 0),
        ]

        print(f"  📍 成功推算 {len(coords)} 个坐标（2×2 区域中心）:")
        for idx, c in enumerate(coords):
            print(f"     坐标 {idx + 1}: ({c[0]:.0f}, {c[1]:.0f})")

        return coords

    # ---------- 内部工具 ----------
    def _check_expect(self, page_data) -> bool:
        if not page_data:
            return False
        full_text = "\n".join(text for _, text, _ in page_data if text)
        return check_keywords_match(full_text, self.expect_text)

    def _find_click_text(self, page_data) -> Optional[Tuple[float, float]]:
        candidates: List[Tuple[float, float]] = []
        for box, text, _ in page_data:
            text_str = str(text).strip()
            if text_str == self.click_text:
                cx, cy = self.finder._box_center(box)
                candidates.append((cx, cy))
        if not candidates:
            return None
        candidates.sort(key=lambda c: c[1])
        return candidates[0]

    def _close_popup(self):
        print("  🚪 兜底：发送返回键关闭当前页面...")
        self.dm.adb_shell(["input", "keyevent", "4"])
        time.sleep(1.0)

    def _wait_popup(self, max_attempts: int = 3,
                    interval: float = 0.5) -> Optional[list]:
        for attempt in range(max_attempts):
            page_data = self.finder.get_page_ocr_data(self.dm)
            if page_data and self._check_expect(page_data):
                return page_data
            if attempt < max_attempts - 1:
                time.sleep(interval)
        return None

    def _process_one(self, coord: Tuple[float, float],
                     wait_open: float = 1.5) -> str:
        print(f"\n  🎯 点击坐标: ({coord[0]:.0f}, {coord[1]:.0f})")
        self.dm.touch(coord)
        time.sleep(wait_open)

        page_data = self._wait_popup(max_attempts=3, interval=0.5)
        if page_data is None:
            print(f"  ℹ️ 未识别到期望文本「{self.expect_text}」"
                  f"（已点满 / 未解锁，无法打开页面）")
            return RESULT_FINISHED

        print(f"  ✅ 页面校验通过: 匹配到「{self.expect_text}」")

        click_coord = self._find_click_text(page_data)
        if not click_coord:
            print(f"  ❌ 无法定位点击文本「{self.click_text}」，兜底关闭页面")
            self._close_popup()
            return RESULT_ERROR

        print(f"  👆 点击「{self.click_text}」: "
              f"({click_coord[0]:.0f}, {click_coord[1]:.0f})")
        self.dm.touch(click_coord)

        print("  ⏳ 等待游戏自动关闭页面...")
        time.sleep(1.0)

        verify_data = self.finder.get_page_ocr_data(self.dm)
        if verify_data and self._check_expect(verify_data):
            print("  ⚠️ 页面似乎仍未关闭，点击可能无效")

        return RESULT_OK

    # ---------- 对外入口 ----------
    def run(self) -> bool:
        print("🚀 开始轮询点击")

        if self.coords_list:
            coords = self.coords_list
        elif self.click_coords:
            coords = [self.click_coords]
        else:
            coords = self.locate_coords()

        if not coords:
            print("  ❌ 无可用坐标")
            return False

        for idx, coord in enumerate(coords, 1):
            coord = tuple(coord)
            print(f"\n===== 处理第 {idx}/{len(coords)} 个坐标 =====")
            self.stats["processed"] += 1

            round_no = 0
            finished = False
            while round_no < self.max_times:
                round_no += 1
                print(f"  🔁 第 {round_no} 次点击该坐标")

                result = self._process_one(coord)

                if result == RESULT_OK:
                    self.stats["clicks"] += 1
                    time.sleep(self.interval)
                    continue
                if result == RESULT_FINISHED:
                    print(f"  🛑 该坐标已点满（第 {round_no} 次点不出页面），换下一个")
                    self.stats["finished"] += 1
                    finished = True
                    break

                print("  ⚠️ 处理出错，停止该坐标的轮询，换下一个")
                self.stats["errors"] += 1
                break

            if not finished and round_no >= self.max_times:
                print(f"  ⚠️ 该坐标已达最大重试次数 {self.max_times}，强制换下一个")

        print(f"\n🎉 轮询处理完毕")
        print(f"   处理坐标数 : {self.stats['processed']}")
        print(f"   完成坐标数 : {self.stats['finished']}")
        print(f"   成功点击数 : {self.stats['clicks']}")
        print(f"   错误次数   : {self.stats['errors']}")
        return True