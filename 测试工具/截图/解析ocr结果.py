import re
import json


def parse_by_coords(ocr_data):
    boxes = ocr_data["texts_with_boxes"]

    # 1. 建筑名称和等级：找最上面那行包含 (LV.x) 的
    title_item = None
    for item in boxes:
        text = item[0]
        if re.search(r"\(LV\.\d+\)", text):
            if title_item is None or item[1][1] < title_item[1][1]:
                title_item = item
                break
    title = title_item[0]
    match = re.match(r"(.+)\(LV\.(\d+)\)", title)
    building_name = match.group(1).strip()
    next_level = int(match.group(2)) + 1
    level_str = f"LV{next_level}"

    # 2. 升级时间：y 在 600~800 之间、x < 300
    upgrade_time = None
    for item in boxes:
        text, center, *rest = item
        x, y = center
        if 600 < y < 800 and x < 300:
            upgrade_time = text
            break

    def convert_time(t):
        days = re.search(r'(\d+)d', t)
        hours = re.search(r'(\d+)h', t)
        minutes = re.search(r'(\d+)m', t)
        seconds = re.search(r'(\d+)s', t)
        total_hours = 0
        if days: total_hours += int(days.group(1)) * 24
        if hours: total_hours += int(hours.group(1))
        res = ""
        if total_hours > 0: res += f"{total_hours}h"
        if minutes: res += f"{minutes.group(1)}m"
        if seconds: res += f"{seconds.group(1)}s"
        if not res and days: res = f"{int(days.group(1)) * 24}h"
        return res

    upgrade_time = convert_time(upgrade_time)

    # 3. 资源：以"类别"的 y 坐标为表头基线
    header_y = None
    for item in boxes:
        if item[0] == "类别":
            header_y = item[1][1]
            break

    rows = {}
    for item in boxes:
        text, center, *rest = item
        x, y = center
        if header_y and y > header_y + 50:
            row_key = round((y - header_y) / 127)
            rows.setdefault(row_key, []).append((x, text))

    resources = {}
    resource_names = ["铁矿", "石油", "铅矿"]
    for row_key in sorted(rows.keys()):
        row = sorted(rows[row_key])
        name = None
        amount = None
        for x, text in row:
            if 250 < x < 400:
                name = text
            elif 500 < x < 650:
                amount = text
        if name in resource_names and amount:
            resources[name] = amount

    # 4. 组装成新格式
    result = {
        "建筑": building_name,
        "等级": level_str,
        **resources,  # 把铁矿/石油/铅矿平铺进来
        "用时": upgrade_time
    }
    return result


# ===== 使用 =====
with open("ocr_result.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

first_key = list(raw.keys())[0]
result = parse_by_coords(raw[first_key])

print(json.dumps(result, ensure_ascii=False, indent=2))