import json
import csv
import re


def calculate_gold(time_str):
    """1分钟=1金币，有秒则加1"""
    hours = int(re.search(r'(\d+)h', time_str).group(1)) if re.search(r'(\d+)h', time_str) else 0
    m_match = re.search(r'(\d+)m(?!s)', time_str)
    minutes = int(m_match.group(1)) if m_match else 0
    s_match = re.search(r'(\d+)s', time_str)
    seconds = int(s_match.group(1)) if s_match else 0

    total = hours * 60 + minutes
    if seconds > 0:
        total += 1
    return total


def json_to_csv(json_file, csv_file='output.csv'):
    # 只读原文件
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 金币为空则计算
    for item in data:
        if not item.get('金币'):
            item['金币'] = calculate_gold(item.get('用时', ''))

    # 收集所有出现过的字段（并集），保持出现顺序
    fieldnames = []
    for item in data:
        for key in item.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    # 写新 CSV
    with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"已生成 {csv_file}，共 {len(data)} 条数据")
    print(f"字段：{fieldnames}")


if __name__ == '__main__':
    json_to_csv(
        '/Users/mac/Documents/learn/pythonProject/mini_tk/迷你坦克自动化/data/upgrade_building_info.json',
        'output.csv'
    )