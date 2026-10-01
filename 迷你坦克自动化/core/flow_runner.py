# ============================================
# 流程执行模块 - 通用执行器，解释配置里的步骤
# ============================================

import time
from datetime import datetime, timedelta
from typing import Optional          # ✅ 新增

from core.device import DeviceManager
from core.ocr_finder import OcrFinder
from core.actions import ActionRunner


def _fmt_duration(seconds: float) -> str:
    """把秒数格式化为 1h 02m 03.4s 形式"""
    td = timedelta(seconds=seconds)
    total = int(td.total_seconds())
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    ms = seconds - total
    if h:
        return f"{h}h {m:02d}m {s:02d}.{int(ms * 10):01d}s"
    if m:
        return f"{m}m {s:02d}.{int(ms * 10):01d}s"
    return f"{s}.{int(ms * 10):01d}s"


class TimeLimitReached(Exception):
    """到达 end_time，强制停止流程"""
    pass


class FlowRunner:
    """按配置执行任意流程"""

    def __init__(self, device_manager: DeviceManager, config: dict):
        self.dm = device_manager
        self.config = config
        self.defaults = config.get("defaults", {})
        self.finder = OcrFinder(base_dir=config["output"]["base_dir"])
        self.runner = ActionRunner(self.dm, self.finder, self.defaults)

        self.runner._flows = config.get("flows", {})

        # 结束时间（datetime 或 None）
        # ✅ 3.9 兼容写法
        self.end_time: Optional[datetime] = None

    # ---------- end_time 解析 ----------
    @staticmethod
    def _parse_end_time(value) -> Optional[datetime]:        # ✅ 3.9 兼容写法
        """解析 end_time 配置，返回 datetime；无效或未配置返回 None"""
        if value is None or value == "":
            return None

        if isinstance(value, datetime):
            return value

        text = str(value).strip()

        # 1) 绝对时间：YYYY-MM-DD HH:MM(:SS)
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                pass

        # 2) 当天时刻：HH:MM(:SS)
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                t = datetime.strptime(text, fmt).time()
                now = datetime.now()
                return now.replace(hour=t.hour, minute=t.minute,
                                   second=t.second, microsecond=0)
            except ValueError:
                pass

        print(f"  ⚠️ end_time 格式无法识别: {value!r}（应为 "
              f"'YYYY-MM-DD HH:MM:SS' 或 'HH:MM:SS'），按无限制处理")
        return None

    def _check_time_limit(self):
        """到达结束时间则抛出 TimeLimitReached"""
        if self.end_time is None:
            return
        if datetime.now() >= self.end_time:
            raise TimeLimitReached(
                f"已到达结束时间 {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

    # ---------- 主流程 ----------
    def run(self):
        flow_name = self.config["active_flow"]
        flow = self.config["flows"].get(flow_name)
        if not flow:
            print(f"❌ 未找到流程配置: {flow_name}")
            print(f"   可用流程: {list(self.config['flows'].keys())}")
            return

        loop = flow.get("loop_count", 1)
        steps = flow.get("steps", [])

        # ---------- 解析 end_time ----------
        self.end_time = self._parse_end_time(flow.get("end_time"))

        # ---------- 整流程计时 ----------
        flow_start = time.time()
        flow_start_dt = datetime.now()

        print(f"🕐 流程开始时间: {flow_start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        if self.end_time:
            remaining = (self.end_time - flow_start_dt).total_seconds()
            if remaining <= 0:
                print(f"⛔ 结束时间 {self.end_time.strftime('%Y-%m-%d %H:%M:%S')} "
                      f"已过，直接退出")
                return
            print(f"⏰ 结束时间    : "
                  f"{self.end_time.strftime('%Y-%m-%d %H:%M:%S')}"
                  f"（剩余 {_fmt_duration(remaining)}）")
        else:
            print("⏰ 结束时间    : 无限制")

        print(f"🚀 开始执行流程「{flow_name}」，共 {loop} 次循环")

        loop_durations = []
        success_loops = 0
        failed_loops = 0
        finished_loops = 0          # 实际完成的循环数
        stopped_by_time = False

        try:
            for n in range(1, loop + 1):
                # 循环开始前先查一次
                self._check_time_limit()

                loop_start = time.time()
                loop_start_dt = datetime.now()
                print(f"\n===== 「{flow_name}」第 {n}/{loop} 次循环 =====")
                print(f"  🕐 本轮开始: {loop_start_dt.strftime('%H:%M:%S')}")

                loop_ok = True
                for idx, step in enumerate(steps, 1):
                    # 每个步骤前检查时间
                    self._check_time_limit()

                    print(f"  ▶ 步骤 {idx}: {step['action']}")
                    ok = self.runner.run_step(step)
                    if not ok:
                        print(f"  ⏭ 步骤 {idx} 未成功，跳过本循环剩余步骤")
                        loop_ok = False
                        break

                loop_end = time.time()
                loop_cost = loop_end - loop_start
                loop_durations.append(loop_cost)
                finished_loops += 1

                if loop_ok:
                    success_loops += 1
                    status = "✅ 完成"
                else:
                    failed_loops += 1
                    status = "⚠️ 中断"

                print(f"  🕐 本轮结束: {datetime.now().strftime('%H:%M:%S')}"
                      f"  |  耗时: {_fmt_duration(loop_cost)}  |  {status}")

        except TimeLimitReached as e:
            stopped_by_time = True
            print(f"\n⛔ {e}，强制停止流程")

        # ---------- 汇总 ----------
        flow_end = time.time()
        flow_end_dt = datetime.now()
        total_cost = flow_end - flow_start

        print(f"\n{'=' * 55}")
        title = "⛔ 流程被时间限制强制停止" if stopped_by_time else "🎉 流程执行完毕"
        print(f"{title}：「{flow_name}」")
        print(f"{'=' * 55}")
        print(f"  🕐 开始时间 : {flow_start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  🕐 结束时间 : {flow_end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  ⏱  总耗时   : {_fmt_duration(total_cost)}")
        print(f"  🔁 计划循环 : {loop}")
        print(f"  🔁 实际完成 : {finished_loops}")
        print(f"  ✅ 成功轮次 : {success_loops}")
        print(f"  ⚠️ 中断轮次 : {failed_loops}")
        if stopped_by_time:
            print(f"  ⛔ 停止原因 : 到达 end_time")
            print(f"  ⏰ 结束时间 : "
                  f"{self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        if loop_durations:
            avg = sum(loop_durations) / len(loop_durations)
            fast = min(loop_durations)
            slow = max(loop_durations)
            print(f"  📊 单轮平均 : {_fmt_duration(avg)}")
            print(f"  📊 单轮最快 : {_fmt_duration(fast)}")
            print(f"  📊 单轮最慢 : {_fmt_duration(slow)}")

        print(f"{'=' * 55}")