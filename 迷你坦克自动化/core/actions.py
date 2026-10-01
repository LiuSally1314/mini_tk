# ============================================
# 动作执行模块（通用）
#
# 通用 action 列表：
#   click              点击坐标
#   find               OCR 查找文本并记录坐标
#   find_click         查找并点击（支持 name + cache_ttl 坐标缓存）
#   wait               纯等待
#   wait_text          等待文本出现
#   dump_ocr           打印当前页面 OCR 内容（调试）
#   repeat             次数循环
#   for_each_coord     遍历坐标列表
#   poll_click         反复点击同一坐标
#   abort_check        条件检查 / 终止
#   call_flow          调用子流程
#   run_method         调用方法（优先查 core/flows/ 注册表，再回退自身方法）
# ============================================

import json
import math
import os
import re
import time
from typing import Optional, Tuple, Dict, List, Any

from core.device import DeviceManager
from core.ocr_finder import OcrFinder
from core.keyword_matcher import check_keywords_match
from core.abort_checker import AbortChecker, SkillAbort, LoopBreak
from core.flows import (
    register_all, bind_all, get_method, get_owner, list_methods,
)


class UserExit(Exception):
    """用户选择退出"""
    pass


# 坐标缓存文件路径（运行期配置，启动时清空）
COORD_CACHE_FILE = "data/coord_cache.json"


class ActionRunner:
    """执行单个动作"""

    def __init__(self, dm: DeviceManager, finder: OcrFinder, defaults: dict):
        self.dm = dm
        self.finder = finder
        self.defaults = defaults
        self.last_coord: Optional[Tuple[float, float]] = None

        self.global_abort_keywords: List[str] = []
        self.global_abort_exact: bool = False

        self.abort_checker = AbortChecker(dm, finder, defaults)

        self._flows: Dict = {}
        self._include_stack: List[str] = []

        # 跨 action 数据存储（run_method 写，后续 action 读）
        self._action_data: Dict[str, Any] = {}

        # 坐标缓存：name -> {"x": float, "y": float, "ts": float}
        self._coord_cache: Dict[str, Dict[str, float]] = {}
        self._coord_cache_file = COORD_CACHE_FILE
        self._load_coord_cache()

        # ---------- 注册流程专用方法 ----------
        register_all()
        bind_all(self)

    # ---------- 坐标缓存（文件） ----------
    def _load_coord_cache(self):
        """启动时从文件加载坐标缓存"""
        if not os.path.exists(self._coord_cache_file):
            self._coord_cache = {}
            return
        try:
            with open(self._coord_cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._coord_cache = data
                print(f"  💾 已加载坐标缓存: {len(self._coord_cache)} 条")
            else:
                print(f"  ⚠️ 坐标缓存文件格式异常，忽略: {type(data)}")
                self._coord_cache = {}
        except Exception as e:
            print(f"  ⚠️ 坐标缓存加载失败: {e}")
            self._coord_cache = {}

    def _save_coord_cache(self):
        """写回坐标缓存文件"""
        try:
            os.makedirs(os.path.dirname(self._coord_cache_file) or ".", exist_ok=True)
            with open(self._coord_cache_file, "w", encoding="utf-8") as f:
                json.dump(self._coord_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ⚠️ 坐标缓存写入失败: {e}")

    def _get_cache_ttl(self, step: dict) -> float:
        """取 cache_ttl，step 覆盖 defaults，单位秒"""
        value = step.get("cache_ttl", self.defaults.get("cache_ttl", 300))
        try:
            return float(value)
        except (TypeError, ValueError):
            print(f"  ⚠️ cache_ttl 非法: {value!r}，回退默认 300s")
            return 300.0

    def _get_cached_coord(self, name: str, ttl: float
                          ) -> Optional[Tuple[float, float]]:
        """命中且未过期则返回坐标，否则返回 None 并清理过期项"""
        entry = self._coord_cache.get(name)
        if not entry:
            return None

        try:
            x = float(entry["x"])
            y = float(entry["y"])
            ts = float(entry["ts"])
        except (KeyError, TypeError, ValueError):
            print(f"  ⚠️ 坐标缓存条目损坏「{name}」，删除并重新 OCR")
            del self._coord_cache[name]
            self._save_coord_cache()
            return None

        age = time.time() - ts
        if age >= ttl:
            print(f"  ⏰ 坐标缓存过期「{name}」"
                  f"（已 {age:.1f}s / TTL {ttl:.0f}s），重新 OCR")
            del self._coord_cache[name]
            self._save_coord_cache()
            return None

        print(f"  💾 坐标缓存命中「{name}」→ ({x:.0f}, {y:.0f})"
              f"（{age:.1f}s / TTL {ttl:.0f}s）")
        return x, y

    def _store_cached_coord(self, name: str, coord: Tuple[float, float]):
        self._coord_cache[name] = {
            "x": float(coord[0]),
            "y": float(coord[1]),
            "ts": time.time(),
        }
        self._save_coord_cache()
        print(f"  💾 已缓存「{name}」→ ({coord[0]:.0f}, {coord[1]:.0f})")

    # ---------- 全局终止监听 ----------
    def set_global_abort(self, keywords, exact: bool = False):
        if not keywords:
            self.global_abort_keywords = []
            return
        self.global_abort_keywords = keywords if isinstance(keywords, list) else [keywords]
        self.global_abort_exact = exact
        print(f"  🛡 全局终止监听: {self.global_abort_keywords}")

    def _check_global_abort(self):
        if not self.global_abort_keywords:
            return
        page_text = self.finder.find_page_text(self.dm)
        if not page_text:
            return
        for kw in self.global_abort_keywords:
            matched = (kw == page_text) if self.global_abort_exact else (kw in page_text)
            if matched:
                reason = f"全局终止词命中「{kw}」，中止当前坐标项"
                print(f"  🛑 {reason}")
                raise SkillAbort(reason)

    # ---------- 异步 abort_check ----------
    def _check_async_abort_hit(self, phase: str = "step"):
        self.abort_checker.check_async_hit(phase=phase)

    # ---------- 工具 ----------
    def _get(self, step: dict, key: str):
        return step.get(key, self.defaults.get(key))

    def _get_confirm_config(self, step: dict):
        """兼容旧的 page_keyword / confirm_keyword，统一走 expect_text"""
        if "expect_text" in step:
            return step["expect_text"]
        if "confirm_keyword" in step:
            return step["confirm_keyword"]
        if "page_keyword" in step:
            return step["page_keyword"]
        return None

    def _get_sleep(self, step: dict) -> float:
        value = step.get("sleep", self.defaults.get("sleep", 0))
        return value if value else 0

    def _do_sleep(self, step: dict):
        seconds = self._get_sleep(step)
        if seconds and seconds > 0:
            print(f"  💤 休眠 {seconds}s")
            time.sleep(seconds)

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

    def _find_with_retry_multi(self, step, targets, exact, region=None):
        retry = self._get(step, "retry")
        interval = self._get(step, "retry_interval")

        has_page = "page" in targets
        has_query = "query" in targets

        def _fmt_target(t):
            if isinstance(t, (list, tuple)):
                return " / ".join(str(x) for x in t)
            return str(t)

        for i in range(retry):
            self._check_global_abort()
            self._check_async_abort_hit(phase="step")

            found = self.finder.find_texts(self.dm, targets, exact=exact, region=region)

            page_ok = found.get("page") is not None if has_page else True
            query_ok = found.get("query") is not None if has_query else True

            if page_ok and query_ok:
                return found["query"] if has_query else found["page"]

            if not page_ok:
                print(f"  🔁 期望文本「{_fmt_target(targets['page'])}」未出现，{interval}s 后重试...")
            elif not query_ok:
                print(f"  🔁 目标「{_fmt_target(targets['query'])}」未找到，{interval}s 后重试...")

            if i < retry - 1:
                time.sleep(interval)

        return None

    def _warn(self, reason: str, context: Optional[dict] = None):
        print(f"  ⚠️ {reason}")
        if context:
            for k, v in context.items():
                print(f"     - {k}: {v}")

    def _check_page(self, step: dict) -> bool:
        confirm_config = self._get_confirm_config(step)
        if not confirm_config:
            return True

        retry = self._get(step, "retry")
        interval = self._get(step, "retry_interval")

        for i in range(retry):
            page_text = self.finder.find_page_text(self.dm)
            if page_text is not None:
                matched = check_keywords_match(page_text, confirm_config)
                if matched:
                    print(f"  ✅ 页面确认通过: {confirm_config}")
                    return True
                else:
                    print(f"  ⚠️ 页面确认未通过，重试 {i + 1}/{retry}")
            else:
                print(f"  ⚠️ 截图/OCR 失败，重试 {i + 1}/{retry}")

            if i < retry - 1:
                time.sleep(interval)

        reason = f"页面确认失败: {confirm_config}"
        print(f"  ❌ {reason}")
        self._warn(reason, {"确认规则": str(confirm_config)})
        return False

    # ---------- 动作 ----------
    def do_find(self, step: dict) -> bool:
        text = step.get("text")
        confirm_config = self._get_confirm_config(step)
        exact = self._get(step, "exact")

        region = self._get_region(step)
        if region:
            print(f"  🎯 限定查找区域: "
                  f"x[{region[0]:.0f},{region[2]:.0f}] "
                  f"y[{region[1]:.0f},{region[3]:.0f}]")

        targets: Dict[str, str] = {}
        if text:
            targets["query"] = text

        if isinstance(confirm_config, str):
            targets["page"] = confirm_config
            coord = self._find_with_retry_multi(step, targets, exact, region=region)
        else:
            if confirm_config is not None:
                if not self._check_page(step):
                    return False
            if text:
                coord = self._find_with_retry_multi(step, targets, exact, region=region)
            else:
                return True

        if coord is None:
            missing = []
            if text:
                missing.append(f"目标「{text}」")
            if isinstance(confirm_config, str):
                missing.append(f"期望文本「{confirm_config}」")
            reason = "未找到 " + " / ".join(missing) if missing else "未找到目标"

            if step.get("optional"):
                print(f"  ⚠️ {reason}（optional=true，继续下一步）")
                return True

            print(f"  ❌ {reason}")
            self._warn(reason, {
                "期望文本": str(confirm_config) if confirm_config else "-",
                "目标": text or "-",
                "查找区域": str(region) if region else "全图",
            })
            return False

        self.last_coord = coord
        return True

    def do_click(self, step: dict) -> bool:
        if self._get_confirm_config(step) is not None:
            if not self._check_page(step):
                return False

        target = step.get("target", "last")
        if target in ("last", "skill"):
            if not self.last_coord:
                if step.get("optional"):
                    print("  ⚠️ click 无可用坐标，但配置了 optional=true，跳过点击继续下一步")
                    return True
                print("  ❌ click 无可用坐标（未先 find）")
                return False
            coord = self.last_coord
        else:
            coord = tuple(step["coords"])

        times = step.get("times", 1)
        interval = step.get("interval", self.defaults.get("interval", 0.5))

        for i in range(times):
            self._check_async_abort_hit(phase="step")
            self.dm.touch(coord)
            if i < times - 1:
                time.sleep(interval)
        print(f"  ✅ 点击 ({coord[0]:.0f},{coord[1]:.0f}) ×{times}")

        self._do_sleep(step)
        return True

    def do_click(self, step: dict) -> bool:
        if self._get_confirm_config(step) is not None:
            if not self._check_page(step):
                return False

        target = step.get("target", "last")
        if target in ("last", "skill"):
            if not self.last_coord:
                if step.get("optional"):
                    print("  ⚠️ click 无可用坐标，但配置了 optional=true，跳过点击继续下一步")
                    return True
                print("  ❌ click 无可用坐标（未先 find）")
                return False
            coord = self.last_coord
        else:
            coord = tuple(step["coords"])

        # ---------- 坐标偏移（offset_x / offset_y）处理 ----------
        offset_x = float(step.get("offset_x", 0))
        offset_y = float(step.get("offset_y", 0))
        if offset_x != 0 or offset_y != 0:
            coord = (coord[0] + offset_x, coord[1] + offset_y)
            print(f"  🎯 应用坐标偏移 (offset_x={offset_x}, offset_y={offset_y}) → 最终坐标: ({coord[0]:.0f}, {coord[1]:.0f})")

        times = step.get("times", 1)
        interval = step.get("interval", self.defaults.get("interval", 0.5))

        for i in range(times):
            self._check_async_abort_hit(phase="step")
            self.dm.touch(coord)
            if i < times - 1:
                time.sleep(interval)
        print(f"  ✅ 点击 ({coord[0]:.0f},{coord[1]:.0f}) ×{times}")

        self._do_sleep(step)
        return True

    def do_find_click(self, step: dict) -> bool:
        name = step.get("name")          # 可选，唯一标识
        use_cache = bool(name)

        # ---------- 缓存命中：跳过 find，直接点击 ----------
        if use_cache:
            ttl = self._get_cache_ttl(step)
            cached = self._get_cached_coord(name, ttl)
            if cached is not None:
                self.last_coord = cached
                click_step = dict(step)
                click_step["target"] = "last"
                click_step["optional"] = step.get("optional", False)
                return self.do_click(click_step)

        # ---------- 原有逻辑：OCR 查找 ----------
        if not self.do_find(step):
            return False

        # ---------- 查找成功：写缓存 ----------
        if use_cache and self.last_coord:
            self._store_cached_coord(name, self.last_coord)

        if step.get("target") == "coords":
            return self.do_click(step)

        click_step = dict(step)
        click_step["target"] = "last"
        click_step["optional"] = step.get("optional", False)
        return self.do_click(click_step)

    def do_wait(self, step: dict) -> bool:
        seconds = step["seconds"]
        print(f"  ⏳ 等待 {seconds}s")
        elapsed = 0.0
        slice_sec = 0.2
        while elapsed < seconds:
            self._check_async_abort_hit(phase="step")
            step_sleep = min(slice_sec, seconds - elapsed)
            time.sleep(step_sleep)
            elapsed += step_sleep
        return True

    def do_wait_text(self, step: dict) -> bool:
        text = step.get("text")
        if not text:
            print("  ❌ wait_text 缺少 text")
            return False

        exact = self._get(step, "exact")
        retry = self._get(step, "retry")
        interval = self._get(step, "retry_interval")

        region = self._get_region(step)
        if region:
            print(f"  🎯 限定等待区域: "
                  f"x[{region[0]:.0f},{region[2]:.0f}] "
                  f"y[{region[1]:.0f},{region[3]:.0f}]")

        for i in range(retry):
            self._check_global_abort()
            self._check_async_abort_hit(phase="step")

            coord = self.finder.find_text(self.dm, text, exact=exact, region=region)
            if coord is not None:
                self.last_coord = coord
                print(f"  ✅ wait_text 命中「{text}」，继续下一步")
                return True

            print(f"  🔁 wait_text 未出现「{text}」，"
                  f"{interval}s 后重试 ({i + 1}/{retry})")
            if i < retry - 1:
                time.sleep(interval)

        reason = f"wait_text 超时：未出现「{text}」"

        if step.get("optional"):
            print(f"  ⚠️ {reason}（optional=true，继续下一步）")
            return True

        print(f"  ❌ {reason}")
        self._warn(reason, {
            "等待关键词": text,
            "重试次数": retry,
            "每次间隔": interval,
            "总等待": f"{retry * interval}s",
            "查找区域": str(region) if region else "全图",
        })
        return False

    def do_abort_check(self, step: dict) -> bool:
        return self.abort_checker.run(step)

    def do_dump_ocr(self, step: dict) -> bool:
        page_data = self.finder.get_page_ocr_data(self.dm)
        if not page_data:
            print("  ❌ OCR 失败")
            return False
        print("  📋 当前页面 OCR 内容：")
        for box, text, score in page_data:
            cx, cy = self.finder._box_center(box)
            print(f"     ({cx:.0f}, {cy:.0f})  「{text}」  conf={score:.2f}")
        return True

    def do_repeat(self, step: dict) -> bool:
        times = step.get("times", 1)
        inner = step.get("steps", [])

        if not inner:
            print("  ⚠️ repeat 未配置 steps，跳过")
            return True

        for i in range(1, times + 1):
            print(f"  🔁 repeat 第 {i}/{times} 轮")
            self._check_async_abort_hit(phase="step")

            try:
                for sub_idx, sub in enumerate(inner, 1):
                    action_name = sub.get("action", "?")
                    print(f"  │  ├ repeat 子步骤 {sub_idx}/{len(inner)}: {action_name}")
                    ok = self.run_step(sub)
                    if not ok:
                        print(f"  │  └ ⚠️ repeat 第 {i} 轮子步骤 {sub_idx} 失败")
                        return False
            except LoopBreak as e:
                print(f"  │  ⏹ repeat 被 LoopBreak 打断: {e.reason}")
                return True

            self._check_async_abort_hit(phase="loop_end")

        return True

    def do_for_each_coord(self, step: dict) -> bool:
        coords_list = step.get("coords_list") or step.get("skill_coords") or []
        sub_steps = step.get("steps") or step.get("sub_steps") or []
        inner_times = step.get("times") or step.get("loop_times") or 1
        click_wait = step.get("click_wait", self.defaults.get("interval", 0.5))
        loop_interval = step.get("interval", self.defaults.get("interval", 0.5))
        close_between = step.get("close_popup_before_next", False)

        if not coords_list:
            print("  ❌ for_each_coord 缺少 coords_list")
            return False
        if not sub_steps:
            print("  ❌ for_each_coord 缺少 steps")
            return False

        abort_cfg = step.get("global_abort")
        if abort_cfg:
            keywords = abort_cfg.get("keywords", [])
            exact = abort_cfg.get("exact", False)
            self.set_global_abort(keywords, exact)
        else:
            self.set_global_abort([])

        all_ok = True

        try:
            for idx, coord in enumerate(coords_list, 1):
                if isinstance(coord, dict):
                    item_coord = tuple(coord.get("coord", []))
                    item_times = coord.get("times", inner_times)
                else:
                    item_coord = tuple(coord)
                    item_times = inner_times

                if not item_coord or len(item_coord) != 2:
                    print(f"  ❌ 坐标项 {idx} 无效: {coord}")
                    all_ok = False
                    continue

                print(f"\n  ┌── 坐标项 {idx}/{len(coords_list)}: "
                      f"{item_coord}（内部循环 {item_times} 次） ──")

                self.abort_checker.stop_async()
                self.last_coord = item_coord

                print(f"  👆 点击坐标: ({item_coord[0]:.0f}, {item_coord[1]:.0f})")
                self.dm.touch(item_coord)
                time.sleep(click_wait)

                abort_text = step.get("abort_text")
                if abort_text:
                    async_step = {
                        "action": "abort_check",
                        "async": True,
                        "abort_text": abort_text,
                        "on_match": step.get("on_match", "break_outer"),
                        "retry_interval": step.get(
                            "retry_interval",
                            self.defaults.get("retry_interval", 0.3)
                        ),
                        "not_confirm_count": step.get("not_confirm_count", 3),
                        "exact": step.get("exact", self.defaults.get("exact", True)),
                        "consume_at": "step",
                    }
                    self.abort_checker.run(async_step)

                item_ok = True
                try:
                    for loop_idx in range(1, item_times + 1):
                        print(f"  🔁 坐标项 {idx} 第 {loop_idx}/{item_times} 轮")
                        self.last_coord = item_coord
                        self._check_async_abort_hit(phase="step")

                        for sub_idx, sub in enumerate(sub_steps, 1):
                            action_name = sub.get("action", "?")
                            print(f"  │  ├ 子步骤 {sub_idx}/{len(sub_steps)}: {action_name}")
                            ok = self.run_step(sub)
                            if not ok:
                                print(f"  │  └ ⚠️ 坐标项 {idx} 第 {loop_idx} 轮"
                                      f"子步骤 {sub_idx} 失败")
                                item_ok = False
                                all_ok = False
                                break

                        if not item_ok:
                            break

                        if loop_idx < item_times and loop_interval > 0:
                            time.sleep(loop_interval)

                except SkillAbort as e:
                    print(f"  │  🛑 坐标项 {idx} 提前中止: {e.reason}")
                    item_ok = False
                    self.abort_checker.stop_async()
                except LoopBreak as e:
                    print(f"  │  ⏹ 坐标项 {idx} 内循环被打断: {e.reason}")
                    self.abort_checker.stop_async()

                try:
                    self._check_async_abort_hit(phase="outer_end")
                except SkillAbort as e:
                    print(f"  │  🛑 坐标项 {idx} 结束阶段被中止: {e.reason}")
                    item_ok = False
                    self.abort_checker.stop_async()

                self.abort_checker.stop_async()

                if item_ok:
                    print(f"  └── ✅ 坐标项 {idx} 完成 {item_times} 轮")

                if close_between and idx < len(coords_list):
                    print("  🚪 发送返回键关闭当前弹窗...")
                    self.dm.adb_shell(["input", "keyevent", "4"])
                    time.sleep(0.5)

        finally:
            self.set_global_abort([])
            self.abort_checker.stop_async()

        return all_ok

    def do_poll_click(self, step: dict) -> bool:
        from core.poll_clicker import PollClicker

        clicker = PollClicker(
            dm=self.dm,
            finder=self.finder,
            click_coords=step.get("coords"),
            start_text=step.get("start_text"),
            end_text=step.get("end_text"),
            expect_text=step.get("expect_text"),
            click_text=step.get("click_text", "升级"),
            coords_list=step.get("coords_list"),
            max_times=step.get("times", 20),
            interval=step.get("interval", self.defaults.get("interval", 1.0)),
        )

        ok = clicker.run()

        stats = getattr(clicker, "stats", None)
        if stats:
            print(
                f"  📊 轮询统计: 处理坐标={stats.get('processed', 0)}, "
                f"完成={stats.get('finished', 0)}, "
                f"成功点击={stats.get('clicks', 0)}, "
                f"错误={stats.get('errors', 0)}"
            )

        self._do_sleep(step)
        return ok

    # ---------- run_method 通用分发 ----------
    def do_run_method(self, step: dict) -> bool:
        """
        调用方法：
          1) 优先查 core/flows/ 注册表（流程专用方法）
          2) 回退到 ActionRunner 自身方法

        重要：LoopBreak / SkillAbort 直接向上抛，交给 repeat / for_each_coord 处理。
        """
        method_name = step.get("method")
        if not method_name:
            print("  ❌ run_method 缺少 method")
            return False

        # 1) 优先查流程方法注册表
        method = get_method(method_name)
        source = f"flows::{get_owner(method_name)}" if method else None

        # 2) 回退到 ActionRunner 自身方法
        if method is None:
            method = getattr(self, method_name, None)
            source = "ActionRunner"

        if not callable(method):
            print(f"  ❌ run_method 未找到可调用方法: {method_name}")
            print(f"     已注册流程方法: {sorted(list_methods().keys())}")
            return False

        store = step.get("store")
        params = step.get("params") or {}
        if not isinstance(params, dict):
            print(f"  ❌ run_method params 必须是 dict，实际: {type(params)}")
            return False

        print(f"  🔧 调用 {source}.{method_name}")
        try:
            result = method(**params)
        except (LoopBreak, SkillAbort):
            # 放行：让上层 repeat / for_each_coord 捕获处理
            raise
        except Exception as e:
            import traceback
            print(f"  ❌ run_method 执行 {method_name} 异常: {e}")
            traceback.print_exc()
            return False

        if store:
            self._action_data[store] = result
            try:
                size = len(result)
            except TypeError:
                size = "?"
            print(f"  💾 结果已存到「{store}」（{size} 项）")
        else:
            # save_/write_/update_ 类方法靠副作用，返回值常被忽略，不提示
            if not method_name.startswith(("save_", "write_", "update_")):
                print("  ℹ️ run_method 未配置 store，返回值未保留")
        return True

    # ---------- 将领技能：扫描并写文件 ----------
    def scan_general_skills(self,
                            anchor_coords: List,
                            pattern: str,
                            region_w: float = 300,
                            region_h: float = 300,
                            default_times: int = 0,
                            value_per_unit: int = 1,
                            debug: bool = False,
                            file: str = "data/general_plan.json",
                            general_coord: Optional[List] = None,
                            general_region_w: float = 300,
                            general_region_h: float = 120) -> List[dict]:
        try:
            rx = re.compile(pattern)
        except re.error as e:
            print(f"  ❌ scan_general_skills pattern 非法: {e}")
            return []

        page_data = self.finder.get_page_ocr_data(self.dm)
        if not page_data:
            print("  ❌ scan_general_skills: OCR 失败")
            return []

        current_general = "unknown"
        if general_coord:
            try:
                gx, gy = float(general_coord[0]), float(general_coord[1])
                ghw = float(general_region_w) / 2.0
                ghh = float(general_region_h) / 2.0
                best_d = float("inf")
                for box, text, _score in page_data:
                    text_str = str(text).strip()
                    if not text_str:
                        continue
                    cx, cy = self.finder._box_center(box)
                    if gx - ghw <= cx <= gx + ghw and gy - ghh <= cy <= gy + ghh:
                        d = (cx - gx) ** 2 + (cy - gy) ** 2
                        if d < best_d:
                            best_d = d
                            current_general = text_str
                if debug:
                    print(f"  👤 识别到将领: {current_general} "
                          f"（搜索中心 ({gx:.0f},{gy:.0f})）")
            except Exception as e:
                print(f"  ⚠️ 将领名称识别失败: {e}")

        hits: List[Tuple[float, float, int, int, str]] = []
        for box, text, _score in page_data:
            text_str = str(text).strip()
            m = rx.search(text_str)
            if not m:
                continue
            try:
                cur = int(m.group(1))
                tgt = int(m.group(2))
            except (IndexError, ValueError):
                continue
            cx, cy = self.finder._box_center(box)
            hits.append((cx, cy, cur, tgt, text_str))
            if debug:
                print(f"     LV.{cur}/{tgt} @ ({cx:.0f},{cy:.0f})  「{text_str}」")

        if debug:
            print(f"  📖 OCR 识别到 {len(hits)} 个 LV 匹配项")

        hw = float(region_w) / 2.0
        hh = float(region_h) / 2.0

        skills: List[dict] = []
        for anchor in anchor_coords:
            try:
                ax, ay = float(anchor[0]), float(anchor[1])
            except Exception:
                print(f"  ⚠️ 锚点格式错误，跳过: {anchor}")
                continue

            best = None
            best_d = float("inf")
            for cx, cy, cur, tgt, _txt in hits:
                if ax - hw <= cx <= ax + hw and ay - hh <= cy <= ay + hh:
                    d = (cx - ax) ** 2 + (cy - ay) ** 2
                    if d < best_d:
                        best_d = d
                        best = (cur, tgt)

            if best is None:
                cur = tgt = None
                need = int(default_times)
                matched = False
            else:
                cur, tgt = best
                diff = max(0, tgt - cur)
                if value_per_unit and value_per_unit > 0:
                    need = math.ceil(diff / value_per_unit)
                else:
                    need = 0
                matched = True

            skills.append({
                "coord": [int(ax), int(ay)],
                "cur": cur,
                "tgt": tgt,
                "need": need,
                "done": 0,
                "matched": matched,
            })

            if matched:
                print(f"  📊 锚点@({ax:.0f},{ay:.0f}) LV.{cur}/{tgt} "
                      f"→ 差 {tgt - cur} → 需点 {need} 次")
            else:
                print(f"  📊 锚点@({ax:.0f},{ay:.0f}) 未匹配 → 兜底 {need} 次")

        data = {
            "current_general": current_general,
            "skills": skills,
            "cursor": 0,
        }

        os.makedirs(os.path.dirname(file) or ".", exist_ok=True)
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"  💾 已写入 {file}")
        print(f"     当前将领: {current_general}")
        print(f"     技能项数: {len(skills)}")
        return skills

    # ---------- 将领技能：读取并判断 / 点击 ----------
    def get_click_target(self,
                         file: str = "data/general_plan.json",
                         anchor_wait: float = 0.5) -> Optional[Tuple[float, float]]:
        if not os.path.exists(file):
            print(f"  ❌ get_click_target: 数据文件不存在 {file}")
            return None

        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)

        skills = data.get("skills", [])
        cursor = int(data.get("cursor", 0))

        target = None
        new_cursor = cursor
        for i in range(cursor, len(skills)):
            s = skills[i]
            if s.get("done", 0) < s.get("need", 0):
                target = s
                new_cursor = i
                break

        if target is None:
            for i in range(0, cursor):
                s = skills[i]
                if s.get("done", 0) < s.get("need", 0):
                    target = s
                    new_cursor = i
                    break

        if target is None:
            print("  ⏭ 所有技能已点满，跳出 repeat")
            raise LoopBreak("所有技能已点满")

        if new_cursor != cursor:
            data["cursor"] = new_cursor
            with open(file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        coord = tuple(target["coord"])
        print(f"  🎯 当前技能 @ {coord} "
              f"(cur={target.get('cur')}, tgt={target.get('tgt')}, "
              f"done={target.get('done')}/{target.get('need')})")

        self.dm.touch(coord)
        if anchor_wait > 0:
            time.sleep(anchor_wait)

        self.last_coord = coord
        return coord

    # ---------- 将领技能：更新已点次数 ----------
    def update_click_count(self,
                           file: str = "data/general_plan.json") -> bool:
        if not os.path.exists(file):
            print(f"  ❌ update_click_count: 数据文件不存在 {file}")
            return False

        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)

        skills = data.get("skills", [])
        cursor = int(data.get("cursor", 0))

        if not skills or cursor >= len(skills):
            print("  ⚠️ update_click_count: cursor 越界，忽略")
            return False

        skills[cursor]["done"] = skills[cursor].get("done", 0) + 1
        data["skills"] = skills

        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        s = skills[cursor]
        print(f"  📝 更新技能 @ {s['coord']} done={s['done']}/{s['need']}")
        return True

    # ---------- 流程引用 ----------
    def _run_steps(self, steps: List[dict], tag: str = "") -> bool:
        for idx, sub in enumerate(steps, 1):
            action_name = sub.get("action", "?")
            prefix = f"{tag} " if tag else ""
            print(f"  │  ├ {prefix}子步骤 {idx}/{len(steps)}: {action_name}")
            ok = self.run_step(sub)
            if not ok:
                print(f"  │  └ ⚠️ {prefix}子步骤 {idx} 失败")
                return False
        return True

    def do_call_flow(self, step: dict) -> bool:
        flow_name = step.get("flow")
        if not flow_name:
            print("  ❌ call_flow 缺少 flow 参数")
            return False

        flows = self._flows or {}
        flow = flows.get(flow_name)
        if not flow:
            print(f"  ❌ call_flow 未找到流程: {flow_name}")
            return False

        if flow_name in self._include_stack:
            chain = " → ".join(self._include_stack + [flow_name])
            print(f"  ❌ call_flow 检测到循环引用: {chain}")
            return False

        before_steps = step.get("before") or []
        after_steps = step.get("after") or []
        times = step.get("times", flow.get("loop_count", 1))
        steps = flow.get("steps", [])

        self._include_stack.append(flow_name)
        try:
            if before_steps:
                print(f"  🔗 子流程「{flow_name}」前置动作 ×{len(before_steps)}")
                if not self._run_steps(before_steps, tag="[before]"):
                    print(f"  ❌ 子流程「{flow_name}」前置动作失败")
                    return False

            if not steps:
                print(f"  ⚠️ call_flow 流程「{flow_name}」没有 steps，跳过主体")
            else:
                print(f"  🔗 进入子流程「{flow_name}」，共 {times} 次循环")
                for n in range(1, times + 1):
                    if times > 1:
                        print(f"  ┌─ 子流程「{flow_name}」第 {n}/{times} 次循环")
                    if not self._run_steps(steps, tag=f"[{flow_name}]"):
                        print(f"  │  └ ⚠️ 子流程「{flow_name}」第 {n} 次循环失败")
                        return False
                print(f"  🔗 子流程「{flow_name}」执行完毕")

            if after_steps:
                print(f"  🔗 子流程「{flow_name}」后置动作 ×{len(after_steps)}")
                if not self._run_steps(after_steps, tag="[after]"):
                    print(f"  ❌ 子流程「{flow_name}」后置动作失败")
                    return False

            return True
        finally:
            self._include_stack.pop()

    # ---------- 分发 ----------
    def run_step(self, step: dict, _depth: int = 0) -> bool:
        MAX_DEPTH = 10
        if _depth > MAX_DEPTH:
            print(f"  ❌ before/after 嵌套过深（>{MAX_DEPTH}），疑似循环引用")
            return False

        enabled = step.get("enabled", self.defaults.get("enabled", True))
        if not enabled:
            print(f"  ⏭ 步骤已禁用，跳过: {step.get('action')}")
            return True

        self._check_async_abort_hit(phase="step")

        action = step["action"]

        remark = step.get("remark")
        text = step.get("text")
        name = step.get("name")

        if remark:
            print(f"  📝 {remark}")
        elif text:
            print(f"  📝 [text] {text}")
        elif name:
            print(f"  📝 [name] {name}")

        # ---------- before ----------
        before_steps = step.get("before") or []
        if before_steps and action != "call_flow":
            print(f"  ⏩ [before] 前置动作 ×{len(before_steps)}")
            for idx, sub in enumerate(before_steps, 1):
                print(f"  │  ├ [before] 子步骤 {idx}/{len(before_steps)}: "
                      f"{sub.get('action', '?')}")
                if not self.run_step(sub, _depth=_depth + 1):
                    print(f"  │  └ ⚠️ [before] 子步骤 {idx} 失败，跳过主步骤")
                    return False

        # ---------- 主 action ----------
        handler = {
            "find": self.do_find,
            "click": self.do_click,
            "find_click": self.do_find_click,
            "wait": self.do_wait,
            "wait_text": self.do_wait_text,
            "abort_check": self.do_abort_check,
            "dump_ocr": self.do_dump_ocr,
            "repeat": self.do_repeat,
            "for_each_coord": self.do_for_each_coord,
            "poll_click": self.do_poll_click,
            "call_flow": self.do_call_flow,
            "run_method": self.do_run_method,
        }.get(action)

        if not handler:
            print(f"  ❌ 未知动作: {action}")
            return False

        ok = handler(step)

        # ---------- after ----------
        after_steps = step.get("after") or []
        if after_steps and action != "call_flow":
            print(f"  ⏩ [after] 后置动作 ×{len(after_steps)}")
            for idx, sub in enumerate(after_steps, 1):
                print(f"  │  ├ [after] 子步骤 {idx}/{len(after_steps)}: "
                      f"{sub.get('action', '?')}")
                if not self.run_step(sub, _depth=_depth + 1):
                    print(f"  │  └ ⚠️ [after] 子步骤 {idx} 失败")
                    return False

        return ok