import json
import csv


def json_to_csv(json_file, csv_file='output.csv'):
    """
    读取 JSON 文件，转换为 CSV
    不修改原 JSON 文件
    """
    # 读取原文件（只读，不写入）
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not data:
        print("数据为空")
        return

    # 收集所有字段名（以第一条为准，也可用并集）
    fieldnames = list(data[0].keys())

    # 写入 CSV（新文件，不影响原 JSON）
    with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"已生成 {csv_file}，共 {len(data)} 条数据")
    print(f"字段：{fieldnames}")


if __name__ == '__main__':
    json_to_csv('data.json', 'output.csv')