# ============================================
# 终止检查模块 - 独立处理 abort_check 动作
#
# 功能：
#   - 同步 / 异步监听
#   - on_match / on_miss 走向控制
#   - consume_at 延迟消费（step / loop_end / outer_end）
#   - not 规则的连续确认（not_confirm_count）
#   - 同配置复用监听线程（避免 repeat 内每轮重启导致计数被重置）
#
# 走向值（通用控制流语义）：
#   on_match / on_miss 取值：
#     break_outer  → 抛出 SkillAbort，跳到最外层 for_each_coord 的下一个坐标
#     break_inner  → 抛出 LoopBreak，跳出最近一层 repeat / for_each_coord 内循环
#     next         → 继续下一步
#
# consume_at 取值：
#     step         → 立即消费命中
#     loop_end     → 等到最近一层循环结束时消费
#     outer_end    → 等到外层 for_each_coord 的当前项结束时消费
# ============================================

import time
import threading
from typing import Optional

from core.keyword_matcher import check_keywords_match, only_not_rules_matched


class SkillAbort(Exception):
    """外层中止：for_each_coord 捕获后跳到下一个坐标项"""
    def __init__(self, reason: str = ""):
        super().__init__(reason)
        self.reason = reason


class LoopBreak(Exception):
    """内层中止：repeat / for_each_coord 内循环捕获后跳出当前循环"""
    def __init__(self, reason: str = ""):
        super().__init__(reason)
        self.reason = reason


class AbortChecker:
    """终止检查器（同步 / 异步）"""

    def __init__(self, dm, finder, defaults: dict):
        self.dm = dm
        self.finder = finder
        self.defaults = defaults

        self._async_thread: Optional[threading.Thread] = None
        self._async_stop = threading.Event()
        self._async_hit = threading.Event()
        self._async_on_match: str = "break_outer"
        self._async_consume_at: str = "step"

        self._async_signature: Optional[tuple] = None

    def _get(self, step: dict, key: str):
        return step.get(key, self.defaults.get(key))

    def _get_region(self, step: dict):
        region = step.get("region")
        if region:
            try:
                x1, y1, x2, y2 = region
                return (float(x1), float(y1), float(x2), float(y2))
            except Exception:
                print(f"  ⚠️ region 格式错误: {region}")
                return None

        coords = step.get("coords")
        if not coords:
            return None

        size = step.get("region_size")
        w = step.get("region_w", size)
        h = step.get("region_h", size)
        if not w or not h:
            w = w or 200
            h = h or 200

        try:
            cx, cy = float(coords[0]), float(coords[1])
        except Exception:
            print(f"  ⚠️ coords 格式错误: {coords}")
            return None

        half_w = float(w) / 2.0
        half_h = float(h) / 2.0
        return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)

    @staticmethod
    def _apply_decision(decision: str, reason: str) -> bool:
        if decision == "break_outer":
            raise SkillAbort(reason)
        if decision == "break_inner":
            raise LoopBreak(reason)
        print(f"  ➡️ {reason}（next，继续下一步）")
        return True

    @staticmethod
    def _match(page_text: str, abort_text, exact: bool) -> bool:
        if not page_text:
            return False

        if isinstance(abort_text, dict):
            return check_keywords_match(page_text, abort_text)

        keywords = abort_text if isinstance(abort_text, list) else [abort_text]

        if exact:
            lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
            return any(kw in lines for kw in keywords)

        return any(kw in page_text for kw in keywords)

    def _make_signature(self, step: dict, abort_text, exact, interval,
                        region, on_match, consume_at, not_confirm_count) -> tuple:
        return (
            repr(abort_text),
            bool(exact),
            float(interval),
            tuple(region) if region else None,
            str(on_match),
            str(consume_at),
            int(not_confirm_count),
        )

    def _start_async(self, step: dict):
        abort_text = step.get("abort_text")
        if not abort_text:
            print("  ⚠️ async abort_check 未配置 abort_text，跳过")
            return

        exact = self._get(step, "exact")
        interval = self._get(step, "retry_interval")
        region = self._get_region(step)
        on_match = step.get("on_match", "break_outer")
        consume_at = step.get("consume_at", "step")
        not_confirm_count = step.get("not_confirm_count", 3)

        signature = self._make_signature(
            step, abort_text, exact, interval,
            region, on_match, consume_at, not_confirm_count
        )

        if (self._async_thread is not None
                and self._async_thread.is_alive()
                and self._async_signature == signature):
            return

        self.stop_async()

        self._async_hit.clear()
        self._async_stop.clear()
        self._async_on_match = on_match
        self._async_consume_at = consume_at
        self._async_signature = signature

        def _worker():
            consecutive_not_hits = 0

            while not self._async_stop.is_set():
                try:
                    page_text = self.finder.find_page_text(self.dm, region=region)
                except Exception as e:
                    print(f"  ⚠️ 异步 abort_check OCR 异常: {e}")
                    page_text = None

                matched = self._match(page_text, abort_text, exact)

                if matched:
                    is_not_only = only_not_rules_matched(page_text or "", abort_text)

                    if is_not_only and not_confirm_count > 1:
                        consecutive_not_hits += 1
                        if consecutive_not_hits < not_confirm_count:
                            print(f"  ⏳ 异步 abort_check：not 规则命中 "
                                  f"({consecutive_not_hits}/{not_confirm_count})，等待确认")
                            if self._async_stop.wait(interval):
                                return
                            continue
                        print(f"  🛑 异步 abort_check：not 规则连续 "
                              f"{not_confirm_count} 次命中（on_match={on_match}）")
                    else:
                        print(f"  🛑 异步 abort_check 命中（on_match={on_match}）")

                    self._async_hit.set()
                    return
                else:
                    consecutive_not_hits = 0

                if self._async_stop.wait(interval):
                    return

        self._async_thread = threading.Thread(target=_worker, daemon=True)
        self._async_thread.start()
        print(f"  🛡 已启动异步 abort_check 监听 "
              f"(on_match={on_match}, consume_at={consume_at}, "
              f"not_confirm_count={not_confirm_count})")

    def stop_async(self):
        self._async_stop.set()
        if self._async_thread and self._async_thread.is_alive():
            self._async_thread.join(timeout=2.0)
        self._async_thread = None
        self._async_hit.clear()
        self._async_on_match = "break_outer"
        self._async_consume_at = "step"
        self._async_signature = None

    def check_async_hit(self, phase: str = "step"):
        if not self._async_hit.is_set():
            return

        if self._async_consume_at == "loop_end" and phase != "loop_end":
            return
        if self._async_consume_at == "outer_end" and phase != "outer_end":
            return

        on_match = self._async_on_match
        self._async_hit.clear()
        reason = (f"异步 abort_check 命中"
                  f"（on_match={on_match}, consume_at={self._async_consume_at}）")
        self._apply_decision(on_match, reason)

    def check_sync(self, step: dict) -> bool:
        abort_text = step.get("abort_text")
        if not abort_text:
            print("  ⚠️ abort_check 未配置 abort_text，跳过")
            return True

        on_match = step.get("on_match", "break_outer")
        on_miss = step.get("on_miss", "next")

        exact = self._get(step, "exact")
        retry = self._get(step, "retry")
        interval = self._get(step, "retry_interval")
        region = self._get_region(step)

        for i in range(retry):
            page_text = self.finder.find_page_text(self.dm, region=region)
            if self._match(page_text, abort_text, exact):
                reason = f"检测到终止关键词（on_match={on_match}）"
                print(f"  🛑 {reason}")
                return self._apply_decision(on_match, reason)

            if i < retry - 1:
                time.sleep(interval)

        print(f"  ✅ 未命中终止关键词（on_miss={on_miss}）")
        if on_miss == "next":
            return True
        return self._apply_decision(on_miss, "abort_check 未命中")

    def run(self, step: dict) -> bool:
        if step.get("async", False):
            self._start_async(step)
            return True
        return self.check_sync(step)