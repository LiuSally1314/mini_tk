import pandas as pd
import numpy as np
import os


def process_game_data(input_file, output_file):
    # 1. 检查文件是否存在
    if not os.path.exists(input_file):
        print(f"❌ 错误：找不到文件 '{input_file}'，请检查路径是否正确。")
        return

    # 2. 读取CSV文件 (尝试不同编码)
    df = None
    for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'gb18030']:
        try:
            df = pd.read_csv(input_file, encoding=encoding)
            break
        except Exception:
            continue

    if df is None:
        print("❌ 错误：无法读取 CSV 文件，请检查文件编码。")
        return

    # 去除列名中的空格
    df.columns = df.columns.str.strip()

    # 3. 容错处理：查找“等级”列
    if '等级' not in df.columns:
        possible_cols = [col for col in df.columns if '等级' in col or '级' in col or 'level' in col.lower()]
        if possible_cols:
            df = df.rename(columns={possible_cols[0]: '等级'})
        else:
            print("❌ 错误：找不到 '等级' 列，请检查 CSV 表头。")
            return

    # 确保“等级”列是数字
    df['等级'] = pd.to_numeric(df['等级'], errors='coerce').fillna(0)

    # 4. 解析资源数值 (K, M, G 转换为纯数字用于计算)
    resource_cols = ['铁矿', '石油', '铅矿']

    def parse_value(val):
        if pd.isna(val): return 0
        if isinstance(val, (int, float)): return val
        val = str(val).strip().upper()
        try:
            if 'G' in val:
                return float(val.replace('G', '')) * 1_000_000_000
            elif 'M' in val:
                return float(val.replace('M', '')) * 1_000_000
            elif 'K' in val:
                return float(val.replace('K', '')) * 1_000
            else:
                return float(val)
        except ValueError:
            return 0

    for col in resource_cols:
        if col in df.columns:
            df[col] = df[col].apply(parse_value)
        else:
            df[col] = 0

    # 5. 划分数据：正常建筑 vs 其他（等级为0）
    df_normal = df[df['等级'] > 0].copy()
    df_other = df[df['等级'] == 0].copy()

    # 6. 正常建筑统计
    # 6.1 0-120 总计
    df_normal['等级区间'] = '0-120'
    total_grouped = df_normal.groupby(['建筑', '等级区间'], observed=False).agg({
        '铁矿': 'sum', '石油': 'sum', '铅矿': 'sum'
    }).reset_index()

    # 6.2 分段统计
    bins = [0, 80, 100, 110, 120]
    labels = ['0-80', '81-100', '100-110', '110-120']
    df_normal['等级区间'] = pd.cut(df_normal['等级'], bins=bins, labels=labels, right=True)

    seg_grouped = df_normal.groupby(['建筑', '等级区间'], observed=False).agg({
        '铁矿': 'sum', '石油': 'sum', '铅矿': 'sum'
    }).reset_index()

    # 合并正常建筑数据
    grouped = pd.concat([total_grouped, seg_grouped], ignore_index=True)

    # 7. 处理“其他”建筑（等级为0）
    if not df_other.empty:
        df_other['等级区间'] = '其他'
        other_grouped = df_other.groupby(['建筑', '等级区间'], observed=False).agg({
            '铁矿': 'sum', '石油': 'sum', '铅矿': 'sum'
        }).reset_index()
        grouped = pd.concat([grouped, other_grouped], ignore_index=True)

    # 8. 排序：0-120 第一，分段第二，其他最后
    sort_order = {'0-120': 0, '0-80': 1, '81-100': 2, '100-110': 3, '110-120': 4, '其他': 5}
    grouped['排序号'] = grouped['等级区间'].map(sort_order)
    grouped = grouped.sort_values(by=['建筑', '排序号']).drop(columns=['排序号'])

    # 9. 格式化输出 (转回 K/M/G)
    def format_value(val):
        if val >= 1_000_000_000:
            return f"{val / 1_000_000_000:.2f}G"
        elif val >= 1_000_000:
            return f"{val / 1_000_000:.2f}M"
        elif val >= 1_000:
            return f"{val / 1_000:.2f}K"
        else:
            return f"{val:.0f}"

    for col in resource_cols:
        grouped[col] = grouped[col].apply(format_value)

    # 10. 只保留需要的列（删除了金币和用时）
    final_cols = ['建筑', '等级区间', '铁矿', '石油', '铅矿']
    grouped = grouped[final_cols]

    # 11. 保存结果
    grouped.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ 处理完成！结果已保存至 {output_file}")
    print("\n数据预览：")
    print(grouped.head(10))


# ================= 配置区域 =================
INPUT_CSV = '/Users/mac/Documents/learn/pythonProject/mini_tk/迷你坦克自动化/utils/output.csv'
OUTPUT_CSV = 'statistics_result.csv'

if __name__ == '__main__':
    process_game_data(INPUT_CSV, OUTPUT_CSV)