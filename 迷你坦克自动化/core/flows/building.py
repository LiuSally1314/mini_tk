# ============================================
# 建筑升级流程专用方法
#
# 业务解析全部在本文件内完成，不依赖 core/ocr_parser 之外的业务模块。
# ============================================

import json
import os
import re
from typing import Dict, Optional

from .base import FlowMethods
from core.ocr_parser import (
    parse_page_data, filter_by_region, group_by_row,
)


class BuildingFlow(FlowMethods):
    """建筑升级：保存建筑升级信息（累积多条，按 建筑+等级 去重）"""

    def save_upgrade_building_info(
        self,
        file: str = "upgrade_building_info.json",
        debug: bool = False,
    ) -> Optional[dict]:
        # ---------- 1. 原始 OCR ----------
        page_data = self.finder.get_page_ocr_data(self.dm)
        if not page_data:
            print("  ❌ save_upgrade_building_info: OCR 失败")
            return None

        # ---------- 2. 通用初次处理：清洗 + 归一化 + 中心点 + 排序 ----------
        items = parse_page_data(page_data, strip_space=True, normalize_unicode=True)

        if debug:
            print(f"  📋 OCR 共 {len(items)} 条：")
            for it in items:
                print(f"     ({it.cx:.0f},{it.cy:.0f}) 「{it.text}」")

        # ---------- 3. 业务解析 ----------
        # 3.1 建筑标题：最上方含 (LV.x) 的那行
        title_item = None
        for it in items:
            if re.search(r"\(LV\.\d+\)", it.text):
                if title_item is None or it.cy < title_item.cy:
                    title_item = it

        if title_item is None:
            print("  ⚠️ 未找到 (LV.x) 标题，无法识别建筑信息")
            return None

        m = re.match(r"(.+)\(LV\.(\d+)\)", title_item.text)
        if not m:
            print(f"  ⚠️ 标题格式异常: {title_item.text}")
            return None
        building_name = m.group(1).strip()
        next_level = int(m.group(2)) + 1

        # 3.2 升级时间：y∈(600,800) 且 x<300 里第一个含时间单位的那条
        time_region = (0, 600, 300, 800)
        time_text = ""
        for it in filter_by_region(items, time_region):
            if re.search(r"\d+\s*(d|h|m|s)", it.text, re.IGNORECASE):
                time_text = it.text
                break

        def _convert_time(t: str) -> str:
            if not t:
                return ""
            days = re.search(r"(\d+)d", t, re.IGNORECASE)
            hours = re.search(r"(\d+)h", t, re.IGNORECASE)
            minutes = re.search(r"(\d+)m", t, re.IGNORECASE)
            seconds = re.search(r"(\d+)s", t, re.IGNORECASE)
            total_hours = 0
            if days:
                total_hours += int(days.group(1)) * 24
            if hours:
                total_hours += int(hours.group(1))
            res = ""
            if total_hours > 0:
                res += f"{total_hours}h"
            if minutes:
                res += f"{minutes.group(1)}m"
            if seconds:
                res += f"{seconds.group(1)}s"
            if not res and days:
                res = f"{int(days.group(1)) * 24}h"
            return res

        upgrade_time = _convert_time(time_text)

        # 3.3 资源表：以「类别」的 y 为基线，按行分组
        header_y = None
        for it in items:
            if it.text == "类别":
                header_y = it.cy
                break

        resources: Dict[str, str] = {}
        if header_y is not None:
            rows = group_by_row(items, base_y=header_y,
                                row_height=127.0, offset=50.0)
            resource_names = ["铁矿", "石油", "铅矿"]
            for _, row in sorted(rows.items()):
                name = None
                amount = None
                for it in row:
                    if 250 < it.cx < 400:
                        name = it.text
                    elif 500 < it.cx < 650:
                        amount = it.text
                if name in resource_names and amount:
                    resources[name] = amount

        # ---------- 4. 组装记录 ----------
        result = {
            "建筑": building_name,
            "等级": f"LV{next_level}",
            **resources,
            "用时": upgrade_time,
        }

        # ---------- 5. 读取旧数据（兼容 dict / list / 空文件） ----------
        os.makedirs(os.path.dirname(file) or ".", exist_ok=True)

        history = []
        if os.path.exists(file):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    old = json.load(f)
                if isinstance(old, list):
                    history = old
                elif isinstance(old, dict) and old:
                    # 旧版单条 dict → 迁移成 list
                    history = [old]
                # 其他情况（空 dict / None / 非法）→ 保持 []
            except Exception as e:
                print(f"  ⚠️ 读取旧数据失败，按空历史处理: {e}")
                history = []

        # ---------- 6. 按「建筑 + 等级」去重 ----------
        key_new = (result["建筑"], result["等级"])
        is_dup = any(
            (h.get("建筑"), h.get("等级")) == key_new
            for h in history
        )

        if is_dup:
            print(f"  ⏭ 已存在「{result['建筑']} {result['等级']}」，跳过写入"
                  f"（累计 {len(history)} 条）")
            return result

        # ---------- 7. 追加 & 写回 ----------
        history.append(result)

        with open(file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

        print(f"  💾 已保存 → {file}（累计 {len(history)} 条）")
        print(f"     {json.dumps(result, ensure_ascii=False)}")
        return result

    def save_upgrade_building_time_info(
            self,
            file: str = "data/upgrade_building_info.json",
            debug: bool = False,
    ) -> Optional[dict]:
        """
        识别当前页面「花费 xxx 个金币」，写入对应建筑记录的「金币」字段。
          - 若记录已存在（按 建筑+等级 匹配）→ 只更新「金币」，其余字段不动
          - 若记录不存在 → 插入一条新记录（建筑 / 等级 / 金币）
        """
        # ---------- 1. OCR ----------
        page_data = self.finder.get_page_ocr_data(self.dm)
        if not page_data:
            print("  ❌ save_upgrade_building_time_info: OCR 失败")
            return None

        items = parse_page_data(page_data, strip_space=True, normalize_unicode=True)

        if debug:
            print(f"  📋 OCR 共 {len(items)} 条：")
            for it in items:
                print(f"     ({it.cx:.0f},{it.cy:.0f}) 「{it.text}」")

        # ---------- 2. 识别建筑标题（与 save_upgrade_building_info 一致） ----------
        title_item = None
        for it in items:
            if re.search(r"\(LV\.\d+\)", it.text):
                if title_item is None or it.cy < title_item.cy:
                    title_item = it

        if title_item is None:
            print("  ⚠️ 未找到 (LV.x) 标题，无法定位建筑记录")
            return None

        m = re.match(r"(.+)\(LV\.(\d+)\)", title_item.text)
        if not m:
            print(f"  ⚠️ 标题格式异常: {title_item.text}")
            return None

        building_name = m.group(1).strip()
        next_level = int(m.group(2)) + 1
        level_str = f"LV{next_level}"

        # ---------- 3. 提取金币 ----------
        gold_pattern = re.compile(r"花费\s*(\d+)\s*个?金币")
        gold_amount = None
        for it in items:
            gm = gold_pattern.search(it.text)
            if gm:
                gold_amount = int(gm.group(1))
                if debug:
                    print(f"  💰 识别到金币: {gold_amount}（原文「{it.text}」）")
                break

        if gold_amount is None:
            print("  ⚠️ 未识别到「花费 xxx 个金币」")
            return None

        # ---------- 4. 读取旧数据 ----------
        os.makedirs(os.path.dirname(file) or ".", exist_ok=True)

        history = []
        if os.path.exists(file):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    old = json.load(f)
                if isinstance(old, list):
                    history = old
                elif isinstance(old, dict) and old:
                    history = [old]
            except Exception as e:
                print(f"  ⚠️ 读取旧数据失败，按空历史处理: {e}")
                history = []

        # ---------- 5. 查找 / 插入 ----------
        key_new = (building_name, level_str)
        target = None
        for h in history:
            if (h.get("建筑"), h.get("等级")) == key_new:
                target = h
                break

        if target is not None:
            # 已存在：只更新金币，其余字段保留
            old_gold = target.get("金币")
            target["金币"] = gold_amount
            if old_gold == gold_amount:
                print(f"  ⏭ 已存在「{building_name} {level_str}」，"
                      f"金币={gold_amount}（未变化）")
            else:
                print(f"  ♻️ 已更新「{building_name} {level_str}」"
                      f"金币: {old_gold} → {gold_amount}")
        else:
            # 不存在：插入新记录
            target = {
                "建筑": building_name,
                "等级": level_str,
                "金币": gold_amount,
            }
            history.append(target)
            print(f"  ➕ 未找到「{building_name} {level_str}」，已插入新记录："
                  f"金币={gold_amount}")

        # ---------- 6. 写回 ----------
        with open(file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

        print(f"  💾 已保存 → {file}（累计 {len(history)} 条）")
        print(f"     {json.dumps(target, ensure_ascii=False)}")
        return target