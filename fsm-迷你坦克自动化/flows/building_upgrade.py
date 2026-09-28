# -*- coding: utf-8 -*-
"""
建筑升级 - 小流程 (重构版)

流程：
  1. 升级页面 (upgrade_page)
     - before: OCR 识别当前建筑等级 + 升级按钮坐标
     - condition: 包含 "120" → finished
     - after: 连续点击升级按钮 4 次
  2. 确认页面 (confirm_page)
     - before: OCR 识别确认按钮坐标，记录标识
     - condition: 始终返回 True
     - after: 根据标识决定是否点击确认按钮（点 1 次）
     - 返回升级页面循环
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor

from flows.base_flow import YAMLStateMachineFlow, FlowFactory
from ocr_utils import load_pages_config, _run_ocr, find_text_items


@FlowFactory.register("building_upgrade")
class BuildingUpgradeFlow(YAMLStateMachineFlow):
    """建筑升级流程"""

    # 连续点击升级按钮的次数
    UPGRADE_CLICK_TIMES = 4

    def __init__(self, cfg: dict, device):
        super().__init__(
            cfg, device,
            default_fsm_path="flows_config/building_upgrade_fsm.yaml",
        )

        # 1. 时序
        self.t_click_upgrade = self.timings.get("click_upgrade_button", 0.5)
        self.t_click_confirm = self.timings.get("click_confirm_button", 0.5)
        self.t_before_shot   = self.timings.get("before_snapshot", 0.3)
        self.t_loop          = self.timings.get("loop_interval", 0.1)
        self.t_between_click = self.timings.get("between_upgrade_click", 0.3)

        # 2. 页面配置
        pages_yaml = self.cfg.get("pages_yaml", "pages.yaml")
        all_pages = load_pages_config(pages_yaml)
        flow_pages = all_pages.get("building_upgrade", all_pages)

        self.p_upgrade = flow_pages["upgrade_page"]
        self.p_confirm = flow_pages["confirm_page"]

        self.upgrade_text       = self.p_upgrade.get("upgrade_text", "升级")
        self.upgrade_match_mode = self.p_upgrade.get("upgrade_match_mode", "exact")

        self.confirm_text       = self.p_confirm.get("confirm_text", "确定")
        self.confirm_match_mode = self.p_confirm.get("confirm_match_mode", "exact")

        self.finish_keyword     = self.p_upgrade.get("finish_keyword", "120")
        self.level_pattern      = re.compile(
            self.p_upgrade.get("level_pattern", r"[Ll][Vv]\.?\s*(\d+)")
        )

        # 3. 运行期数据（每次循环重新填充）
        self._upgrade_coord = None
        self._confirm_coord = None
        self._has_confirm   = False
        self._current_level = None

        # 4. 线程池
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="BuildingPool")

    # ============================================================
    # 通用 OCR 工具
    # ============================================================
    def _capture_and_ocr(self):
        """截图并返回 (img, items)"""
        img = self.device.capture(settle=self.t_before_shot)
        if img is None:
            return None, []
        return img, _run_ocr(img)

    @staticmethod
    def _pick_nearest_center(items_hits, img_height: int):
        """
        在多个候选里取 cy 最接近图像垂直中心的那个。
        items_hits 为空时返回 (None, None)。
        """
        if not items_hits:
            return None, None
        center_y = img_height / 2.0 if img_height else 0.0
        hits = sorted(items_hits, key=lambda e: abs(e["cy"] - center_y))
        it = hits[0]
        return it["text"], (it["cx"], it["cy"])

    # ============================================================
    # 升级页面：before / condition / after
    # ============================================================
    def prepare_upgrade_page(self):
        """
        [before] 前置 OCR：识别当前建筑等级 + 升级按钮坐标
        """
        img, items = self._capture_and_ocr()
        if not items:
            print("⚠️ [upgrade_page] OCR 未识别到任何文字")
            self._upgrade_coord = None
            self._current_level = None
            return

        texts = [it["text"] for it in items]

        # 提取当前建筑等级（可选，仅用于日志）
        level = None
        for t in texts:
            m = self.level_pattern.search(t)
            if m:
                level = int(m.group(1))
                break
        self._current_level = level

        # 提取升级按钮坐标：按配置的 match_mode 找候选，再取离屏幕中心最近的
        hits = find_text_items(items, self.upgrade_text, self.upgrade_match_mode)
        from ocr_utils import _get_image_height
        H = _get_image_height(img, items) if img is not None else 0
        btn_text, coord = self._pick_nearest_center(hits, H)
        self._upgrade_coord = coord

        print(f"🔍 [upgrade_page] OCR 文本: {texts}")
        print(f"🔍 [upgrade_page] 当前等级: {self._current_level}, "
              f"升级按钮: {btn_text} -> {coord} "
              f"(mode={self.upgrade_match_mode}, 候选数={len(hits)})")

    def check_finish_keyword(self) -> bool:
        """
        [condition] 检查是否包含结束关键词（120）
        """
        _, items = self._capture_and_ocr()
        if not items:
            return False

        for it in items:
            if self.finish_keyword in it["text"]:
                print(f"✅ [upgrade_page] 命中结束关键词: {it['text']!r}")
                return True
        return False

    def click_upgrade_four_times(self):
        """
        [after] 连续点击升级按钮 4 次
        """
        if self._upgrade_coord is None:
            print(f"❌ [upgrade_page] 未找到「{self.upgrade_text}」按钮，跳过点击")
            return

        print(f"👆 [upgrade_page] 连续点击「{self.upgrade_text}」"
              f"{self.UPGRADE_CLICK_TIMES} 次，坐标: {self._upgrade_coord}")

        for i in range(1, self.UPGRADE_CLICK_TIMES + 1):
            self.device.touch(self._upgrade_coord, duration=self.t_click_upgrade)
            print(f"   👆 第 {i}/{self.UPGRADE_CLICK_TIMES} 次点击完成")
            if i < self.UPGRADE_CLICK_TIMES:
                time.sleep(self.t_between_click)

    # ============================================================
    # 确认页面：before / condition / after
    # ============================================================
    def prepare_confirm_page(self):
        """
        [before] 前置 OCR：识别确认按钮坐标，记录标识
        """
        img, items = self._capture_and_ocr()
        if not items:
            print("⚠️ [confirm_page] OCR 未识别到任何文字")
            self._confirm_coord = None
            self._has_confirm = False
            return

        texts = [it["text"] for it in items]
        hits = find_text_items(items, self.confirm_text, self.confirm_match_mode)
        from ocr_utils import _get_image_height
        H = _get_image_height(img, items) if img is not None else 0
        btn_text, coord = self._pick_nearest_center(hits, H)

        self._confirm_coord = coord
        self._has_confirm = coord is not None

        print(f"🔍 [confirm_page] OCR 文本: {texts}")
        print(f"🔍 [confirm_page] 确认按钮标识: {self._has_confirm}, "
              f"按钮: {btn_text} -> {coord} "
              f"(mode={self.confirm_match_mode}, 候选数={len(hits)})")

    def check_confirm_page(self) -> bool:
        """
        [condition] 始终返回 True（无论有没有确认按钮，都允许转换）
        """
        return True

    def click_confirm_if_needed(self):
        """
        [after] 根据标识决定是否点击确认按钮（点击一次）
        """
        if not self._has_confirm or self._confirm_coord is None:
            print("ℹ️ [confirm_page] 无确认按钮，跳过点击")
            return

        print(f"👆 [confirm_page] 点击「{self.confirm_text}」: {self._confirm_coord}")
        self.device.touch(self._confirm_coord, duration=self.t_click_confirm)
        time.sleep(self.t_click_confirm)

    # ============================================================
    # 结束 / 清理
    # ============================================================
    def on_finished(self):
        print("🎉 [building_upgrade] 流程结束")

    def teardown(self):
        self.executor.shutdown(wait=True)
        print("🎉 [building_upgrade] 资源回收完毕")

    # ============================================================
    # 主循环
    # ============================================================
    def run(self):
        print("🚀 开始执行：建筑升级流程")
        while self.state != "finished":
            if self.state == "upgrade_page":
                self.prepare_upgrade_page()

                if self.check_finish_keyword():
                    self.tri_finish()
                else:
                    self.click_upgrade_four_times()
                    self.tri_check_upgrade()

            elif self.state == "confirm_page":
                self.prepare_confirm_page()
                self.check_confirm_page()
                self.click_confirm_if_needed()
                self.tri_back_to_upgrade()

            else:
                break

            time.sleep(self.t_loop)