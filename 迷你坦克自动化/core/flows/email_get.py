# ============================================
# 邮箱信息保存流程
#
# 识别当前邮件详情页，提取「数量 / 物品名称 / 物品描述」，
# 以「数量」为 id 去重后追加写入 CSV（id,name,desc）。
#
# 注意：extract_mail_info 依赖「数量：」的全角冒号，
#       因此这里用原始 OCR 文本构造 texts_with_boxes，
#       不做 NFKC 归一化（与 building.py 的归一化策略不同）。
# ============================================

import csv
import os
from typing import Any, Dict, Optional

from .base import FlowMethods


# ------------------------------------------------------------
# 邮件信息解析（业务解析全部在本文件内完成）
# ------------------------------------------------------------
def extract_mail_info(data: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "数量": None,
        "物品名称": None,
        "物品描述": None,
    }

    items = data.get("texts_with_boxes", [])

    # 1. 找数量
    count_item = None
    for item in items:
        if item and len(item) >= 2 and item[0].startswith("数量："):
            count_item = item
            break

    if not count_item:
        return result

    count_text = count_item[0]
    count_center = count_item[1]
    count_box = count_item[2:]
    count_y = count_center[1]

    result["数量"] = {
        "text": count_text,
        "value": count_text.replace("数量：", "").strip(),
        "center": count_center,
        "box": count_box,
    }

    # 2. 找「点击屏幕继续」
    continue_y = None
    for item in items:
        if item and len(item) >= 2 and "点击屏幕继续" in item[0]:
            continue_y = item[1][1]
            break

    if continue_y is None:
        return result

    # 3. 物品名称：数量 y 上方最近的一条文本
    above = []
    for item in items:
        if not item or len(item) < 2:
            continue
        text = item[0]
        center = item[1]
        box = item[2:]
        cy = center[1]

        if cy < count_y:
            above.append({
                "text": text,
                "center": center,
                "box": box,
                "cy": cy,
            })

    if above:
        above.sort(key=lambda x: x["cy"], reverse=True)  # 离数量最近的
        name_item = above[0]
        result["物品名称"] = {
            "text": name_item["text"],
            "center": name_item["center"],
            "box": name_item["box"],
        }

    # 4. 物品描述：数量 y 到 点击屏幕继续 y 之间（可能多行，按 y 排序后无空格拼接）
    desc_items = []
    for item in items:
        if not item or len(item) < 2:
            continue
        text = item[0]
        center = item[1]
        box = item[2:]
        cy = center[1]

        if count_y < cy < continue_y and not text.startswith("数量："):
            desc_items.append({
                "text": text,
                "center": center,
                "box": box,
                "cy": cy,
            })

    if desc_items:
        desc_items.sort(key=lambda x: x["cy"])
        # 多行无空格拼接为一行
        desc_text = "".join(d["text"] for d in desc_items)
        result["物品描述"] = {
            "text": desc_text,
            "center": desc_items[0]["center"],
            "box": desc_items[0]["box"],
        }

    return result


class EmailGetFlow(FlowMethods):
    """邮箱信息：保存邮件物品信息到 CSV（按 id 去重）"""

    def save_email_info(
        self,
        file: str = "data/save_email_info.csv",
        debug: bool = False,
    ) -> Optional[dict]:
        # ---------- 1. 原始 OCR ----------
        page_data = self.finder.get_page_ocr_data(self.dm)
        if not page_data:
            print("  ❌ save_email_info: OCR 失败")
            return None

        # ---------- 2. 原始 OCR → texts_with_boxes ----------
        # 保持原始文本（不做 NFKC 归一化），确保「数量：」的全角冒号可被匹配。
        # 结构：[text, [cx, cy], [x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        texts_with_boxes = []
        for box, text, _score in page_data:
            text_str = str(text).strip()
            if not text_str:
                continue

            xs = [float(p[0]) for p in box]
            ys = [float(p[1]) for p in box]
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)

            texts_with_boxes.append([
                text_str,
                [cx, cy],
                [box[0][0], box[0][1]],
                [box[1][0], box[1][1]],
                [box[2][0], box[2][1]],
                [box[3][0], box[3][1]],
            ])

        if debug:
            print(f"  📋 OCR 共 {len(texts_with_boxes)} 条：")
            for t in texts_with_boxes:
                print(f"     ({t[1][0]:.0f},{t[1][1]:.0f}) 「{t[0]}」")

        # ---------- 3. 业务解析 ----------
        mail = extract_mail_info({"texts_with_boxes": texts_with_boxes})

        count = mail.get("数量")
        name = mail.get("物品名称")
        desc = mail.get("物品描述")

        if not count:
            print("  ⚠️ 未识别到「数量：」，无法作为 id，跳过")
            return None

        mail_id = str(count["value"]).strip()
        mail_name = name["text"].strip() if name else ""
        mail_desc = desc["text"].strip() if desc else ""

        if debug:
            print(f"  📧 解析结果: id={mail_id!r} "
                  f"name={mail_name!r} desc={mail_desc!r}")

        # ---------- 4. 读取旧数据（CSV，按 id 去重） ----------
        os.makedirs(os.path.dirname(file) or ".", exist_ok=True)

        existing_ids = set()
        file_exists = os.path.exists(file)

        if file_exists:
            try:
                with open(file, "r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        rid = (row.get("id") or "").strip()
                        if rid:
                            existing_ids.add(rid)
            except Exception as e:
                print(f"  ⚠️ 读取旧数据失败，按空历史处理: {e}")
                existing_ids = set()
                file_exists = False

        # ---------- 5. 按「id」去重 ----------
        if mail_id in existing_ids:
            print(f"  ⏭ 已存在 id={mail_id}，跳过写入"
                  f"（累计 {len(existing_ids)} 条）")
            return {"id": mail_id, "name": mail_name, "desc": mail_desc}

        # ---------- 6. 追加 & 写回 ----------
        try:
            with open(file, "a", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["id", "name", "desc"])
                if not file_exists:
                    writer.writeheader()
                writer.writerow({
                    "id": mail_id,
                    "name": mail_name,
                    "desc": mail_desc,
                })
        except Exception as e:
            print(f"  ❌ 写入 CSV 失败: {e}")
            return None

        print(f"  💾 已保存 → {file}（累计 {len(existing_ids) + 1} 条）")
        print(f"     id={mail_id} | name={mail_name} | desc={mail_desc}")
        return {"id": mail_id, "name": mail_name, "desc": mail_desc}