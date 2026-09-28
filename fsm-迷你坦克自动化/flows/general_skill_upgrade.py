import time
import queue
from concurrent.futures import ThreadPoolExecutor

from flows.base_flow import YAMLStateMachineFlow, FlowFactory
from ocr_utils import (
    load_pages_config,
    check_page,
    load_skills_from_ocr,
    find_upgrade_button,
)


@FlowFactory.register("general_skill_upgrade")
class GeneralSkillUpgradeFlow(YAMLStateMachineFlow):
    """将领技能升级流程 (配合方案一的分组 pages.yaml 读取)"""

    def __init__(self, cfg: dict, device):
        super().__init__(cfg, device, default_fsm_path="flows_config/general_skill_upgrade_fsm.yaml")

        # 1. 时序配置
        self.t_click_skill = self.timings.get('click_skill_icon', 0.1)
        self.t_after_icon = self.timings.get('after_click_icon', 1.2)
        self.t_click_upgrade = self.timings.get('click_upgrade_button', 0.1)
        self.t_after_upgrade = self.timings.get('after_upgrade', 0.5)
        self.t_before_shot = self.timings.get('before_snapshot', 0.3)
        self.t_loop = self.timings.get('loop_interval', 0.1)

        # 2. 页面与 OCR 配置 (方案一改造：按流程模块名提取)
        pages_yaml = self.cfg.get('pages_yaml', 'pages.yaml')
        all_pages = load_pages_config(pages_yaml)

        # 优先读取 "general_skill_upgrade" 节点下的配置，若不存在则降级读取全局根配置
        flow_pages = all_pages.get("general_skill_upgrade", all_pages)

        self.p1 = flow_pages['general_management']
        self.p2 = flow_pages['skill_upgrade']
        self.skill_ocr = self.p1.get('ocr', {})
        self.popup_ocr = self.p2.get('ocr', {})

        # 3. 运行缓存及线程池
        self.current_index = 0
        self.coord_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ActionPool")

        self._coords_calculated = False

        # 升级按钮坐标：按技能维度缓存 + 每个技能前 N 次强制重算
        self._upgrade_btn_coord = None          # 当前缓存的升级按钮坐标
        self._upgrade_btn_skill_id = None       # 该坐标属于哪个技能
        self._upgrade_btn_click_count = 0       # 当前技能已进入升级页的次数
        # 每个技能前几次进入升级页需要重算坐标（默认 2 次）
        self.upgrade_recalc_times = self.popup_ocr.get('recalc_times', 2)

        # 4. 执行首次截图及识别
        self._init_skills_data()

    def _init_skills_data(self):
        main_img = self.device.capture(settle=self.t_before_shot)
        if main_img is None:
            raise RuntimeError("首次截图失败，无法继续流程")

        if self.debug:
            print("=== 页面校验 ===")
            check_page(main_img, self.p1, debug=True)

        self.skills_data, self.max_level = load_skills_from_ocr(
            image=main_img,
            lv_pattern=self.skill_ocr.get('lv_pattern'),
            icon_offset=self.skill_ocr.get('icon_offset', 0),
            row_tol_mode=self.skill_ocr.get('row_tol_mode', 'auto'),
            row_tol_manual=self.skill_ocr.get('row_tol_manual', 0),
            debug=self.debug,
        )
        self.total_skills = len(self.skills_data)

    # ---------------- YAML 状态机绑定的回调函数 ----------------

    def check_and_seek_next_need_upgrade_skill(self) -> bool:
        while self.current_index < self.total_skills:
            skill = self.skills_data[self.current_index]
            if not self._is_skill_finished(skill):
                return True
            print(f"ℹ️ 技能 {skill['id']} 初始进度 {skill['current_clicks']}/{skill['target_clicks']} 无需升级，跳过。")
            self.current_index += 1
        return False

    def calculate_skill_coords(self):
        calc_once_flag = self.p1.get('calc_once', True)
        if calc_once_flag and self._coords_calculated:
            print("⚡ [坐标] 已计算过，跳过")
            return
        with self.coord_queue.mutex:
            self.coord_queue.queue.clear()
        for s in self.skills_data:
            self.coord_queue.put(s["center"])
        self._coords_calculated = True
        print(f"📐 [坐标] 填充 {len(self.skills_data)} 个技能坐标")

    def calculate_upgrade_button_coord(self, retries: int = 3):
        """
        计算升级按钮坐标。

        规则：每个技能进入升级页的前 `upgrade_recalc_times` 次强制重新 OCR，
        之后复用缓存；切换到新技能时计数与缓存重置。
        """
        skill = self.skills_data[self.current_index]
        skill_id = skill['id']

        # 换技能了 -> 重置计数与缓存
        if self._upgrade_btn_skill_id != skill_id:
            self._upgrade_btn_skill_id = skill_id
            self._upgrade_btn_click_count = 0
            self._upgrade_btn_coord = None
            print(f"🔄 [升级按钮] 切换到技能 {skill_id}，重置坐标缓存与计数")

        # 判断是否需要重新计算
        need_recalc = (
            self._upgrade_btn_coord is None
            or self._upgrade_btn_click_count < self.upgrade_recalc_times
        )

        if not need_recalc:
            print(f"⚡ [升级按钮] 技能 {skill_id} 第 {self._upgrade_btn_click_count + 1} 次进入，"
                  f"复用缓存坐标: {self._upgrade_btn_coord}")
            return

        button_text = self.popup_ocr.get('button_text', '升级')
        y_band_cfg = self.popup_ocr.get('button_y_band')
        y_band = tuple(y_band_cfg) if y_band_cfg else None

        print(f"🔍 [升级按钮] 技能 {skill_id} 第 {self._upgrade_btn_click_count + 1} 次进入，"
              f"重新 OCR 计算坐标 ...")

        for attempt in range(1, retries + 1):
            popup_img = self.device.capture(settle=self.t_before_shot)
            if popup_img is None:
                time.sleep(0.3)
                continue

            if not check_page(popup_img, self.p2, debug=self.debug):
                print(f"⚠️ [升级按钮] 第 {attempt} 次截图非技能升级弹窗，重试...")
                time.sleep(0.3)
                continue

            coord = find_upgrade_button(
                image=popup_img,
                button_text=button_text,
                y_band=y_band,
                debug=self.debug,
            )

            if coord is not None:
                self._upgrade_btn_coord = coord
                print(f"📐 [升级按钮] 技能 {skill_id} 坐标已更新: {coord}")
                return
            time.sleep(0.3)

        print(f"❌ [升级按钮] {retries} 次尝试均未找到「{button_text}」")

    def execute_touch_action(self, target_name: str, coord: tuple, duration: float):
        print(f"  👇 [线程池] 点击【{target_name}】，坐标: {coord}，按压 {duration}s")
        self.device.touch(coord, duration=duration)

    def click_skill_icon_from_pool(self):
        coords_list = list(self.coord_queue.queue)
        if not coords_list or self.current_index >= len(coords_list):
            print("❌ 坐标队列为空或索引超出范围")
            return

        target_coord = coords_list[self.current_index]
        skill = self.skills_data[self.current_index]
        print(f"\n[主界面] 📍 准备处理第 {self.current_index + 1} 个技能图标")

        future = self.executor.submit(
            self.execute_touch_action,
            f"技能-{skill['id']}图标",
            target_coord,
            self.t_click_skill,
        )
        future.result()
        time.sleep(self.t_after_icon)

    def click_upgrade_button_from_pool(self):
        skill = self.skills_data[self.current_index]

        if self._is_skill_finished(skill):
            print(f"✅ 技能 {skill['id']} 已达到升级目标，无需继续点击")
            self.current_index += 1
            return

        if self._upgrade_btn_coord is None:
            self.calculate_upgrade_button_coord()
            if self._upgrade_btn_coord is None:
                print("❌ [升级按钮] 无法获得坐标，跳过本次点击")
                return

        upgrade_btn_coord = self._upgrade_btn_coord
        print(f"[升级页] 🎯 技能 {skill['id']} 使用升级按钮坐标: {upgrade_btn_coord}")

        future = self.executor.submit(
            self.execute_touch_action,
            f"技能-{skill['id']}升级按钮",
            upgrade_btn_coord,
            self.t_click_upgrade,
        )
        future.result()

        time.sleep(self.t_after_upgrade)
        skill['current_clicks'] += 1

        # 本次进入升级页已完成，累加进入次数（用于判断下次是否重算）
        self._upgrade_btn_click_count += 1

        print(f"[升级页] 🎉 技能 {skill['id']} 升级成功！"
              f"进度: {skill['current_clicks']}/{skill['target_clicks']}，"
              f"进入次数: {self._upgrade_btn_click_count}")

        if self._is_skill_finished(skill):
            print(f"✅ 技能 {skill['id']} 已升满，切到下一个技能")
            self.current_index += 1

        print("[升级页] 🚪 返回主界面")

    def _is_skill_finished(self, skill: dict) -> bool:
        return (
                skill['current_clicks'] >= skill['target_clicks']
                or skill['current_clicks'] >= self.max_level
        )

    def on_finished(self):
        print("\n🎉 [总结] 将领技能升级流程全部结束！")

    def teardown(self):
        self.executor.shutdown(wait=True)
        print("🎉 [技能升级流程] 线程池与流程资源已回收。")

    # ---------------- 主循环逻辑 ----------------

    def run(self):
        print("🚀 开始执行：ADB 实时截图 → 直接喂 OCR，坐标来自 OCR...")

        while self.state != 'finished':
            if self.state == 'general_management':
                if self.check_and_seek_next_need_upgrade_skill():
                    self.tri_enter_upgrade()
                else:
                    self.tri_finish()
            elif self.state == 'skill_upgrade':
                self.tri_back_to_management()

            time.sleep(self.t_loop)