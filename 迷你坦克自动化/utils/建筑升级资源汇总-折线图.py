import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# ================= 解决 matplotlib 中文显示问题 =================
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang HK', 'SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

def process_game_data(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"❌ 错误：找不到文件 '{input_file}'")
        return

    df = None
    for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'gb18030']:
        try:
            df = pd.read_csv(input_file, encoding=encoding)
            break
        except Exception:
            continue

    if df is None:
        print("❌ 错误：无法读取 CSV 文件。")
        return

    df.columns = df.columns.str.strip()

    if '等级' not in df.columns:
        possible_cols = [col for col in df.columns if '等级' in col or '级' in col or 'level' in col.lower()]
        if possible_cols:
            df = df.rename(columns={possible_cols[0]: '等级'})
        else:
            print("❌ 错误：找不到 '等级' 列。")
            return

    df['等级'] = pd.to_numeric(df['等级'], errors='coerce').fillna(1).astype(int)
    df.loc[df['等级'] <= 0, '等级'] = 1

    resource_cols = ['铁矿', '石油', '铅矿']

    def parse_value(val):
        if pd.isna(val): return 0
        if isinstance(val, (int, float)): return val
        val = str(val).strip().upper()
        try:
            if 'G' in val: return float(val.replace('G', '')) * 1_000_000_000
            elif 'M' in val: return float(val.replace('M', '')) * 1_000_000
            elif 'K' in val: return float(val.replace('K', '')) * 1_000
            else: return float(val)
        except ValueError: return 0

    for col in resource_cols:
        if col in df.columns:
            df[col] = df[col].apply(parse_value)
        else:
            df[col] = 0

    grouped = df.groupby(['建筑', '等级'], as_index=False).agg({
        '铁矿': 'sum', '石油': 'sum', '铅矿': 'sum'
    })

    def format_value(val):
        if val >= 1_000_000_000: return f"{val/1_000_000_000:.2f}G"
        elif val >= 1_000_000: return f"{val/1_000_000:.2f}M"
        elif val >= 1_000: return f"{val/1_000:.2f}K"
        else: return f"{val:.0f}"

    df_output = grouped.copy()
    for col in resource_cols:
        df_output[col] = df_output[col].apply(format_value)

    df_output.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"✅ 统计结果已保存至 {output_file}")

    # ================= 生成 1×9 长条图 =================
    print("\n📊 开始生成 1×9 长条图...")

    building_order = ['指挥中心', '科研中心', '仓库', '坦克工厂', '改装车间', '水晶工厂', '钛矿场', '铁矿场', '铅矿场']

    available_buildings = grouped['建筑'].unique()
    ordered_buildings = [b for b in building_order if b in available_buildings]
    for b in available_buildings:
        if b not in ordered_buildings:
            ordered_buildings.append(b)

    print(f"📋 图表顺序：{ordered_buildings}")

    def y_formatter(x, pos):
        if x >= 1_000_000_000:
            return f'{x/1_000_000_000:.1f}G'
        elif x >= 1_000_000:
            return f'{x/1_000_000:.1f}M'
        elif x >= 1_000:
            return f'{x/1_000:.1f}K'
        else:
            return f'{x:.0f}'

    def compress_x(levels):
        mapped = []
        for lv in levels:
            if lv <= 50:
                mapped.append(lv / 50 * 10)
            else:
                mapped.append(10 + (lv - 50) / 70 * 90)
        return mapped

    def get_display_ticks(levels):
        ticks = []
        for lv in [0, 30, 50, 60, 80, 100, 120]:
            if lv in levels:
                ticks.append(lv)
        return ticks

    # ★ 放大参数：整体等比例放大
    SCALE = 1.8  # 放大倍数，可自行调整（如 1.5、2.0）

    n = len(ordered_buildings)
    # 图幅尺寸同比放大
    fig, axes = plt.subplots(n, 1, figsize=(8 * SCALE, n * 4 * SCALE))

    if n == 1:
        axes = [axes]

    # 字号同比放大
    TITLE_SIZE = 16 * SCALE
    LABEL_SIZE = 13 * SCALE
    TICK_SIZE = 11 * SCALE
    LEGEND_SIZE = 12 * SCALE
    # 标记点和线宽同比放大
    MARKER_SIZE = 5 * SCALE
    LINE_WIDTH = 2 * SCALE

    for idx, building in enumerate(ordered_buildings):
        ax = axes[idx]
        b_data = grouped[grouped['建筑'] == building].copy()
        b_data = b_data.sort_values('等级')

        x_levels_raw = b_data['等级'].tolist()
        y_iron = b_data['铁矿'].tolist()
        y_oil = b_data['石油'].tolist()
        y_lead = b_data['铅矿'].tolist()

        x_compressed = compress_x(x_levels_raw)

        ax.plot(x_compressed, y_iron, marker='o', label='铁矿', color='#1f77b4',
                linewidth=LINE_WIDTH, markersize=MARKER_SIZE)
        ax.plot(x_compressed, y_oil, marker='s', label='石油', color='#ff7f0e',
                linewidth=LINE_WIDTH, markersize=MARKER_SIZE)
        ax.plot(x_compressed, y_lead, marker='^', label='铅矿', color='#2ca02c',
                linewidth=LINE_WIDTH, markersize=MARKER_SIZE)

        ax.set_title(f'{building} - 各等级资源需求', fontsize=TITLE_SIZE, fontweight='bold')
        ax.set_xlabel('等级', fontsize=LABEL_SIZE)
        ax.set_ylabel('资源数量', fontsize=LABEL_SIZE)
        ax.legend(fontsize=LEGEND_SIZE, loc='upper left')
        ax.grid(True, linestyle='--', alpha=0.6)

        display_ticks = get_display_ticks(x_levels_raw)
        tick_positions = compress_x(display_ticks)
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(display_ticks, fontsize=TICK_SIZE)

        ax.tick_params(axis='y', labelsize=TICK_SIZE, left=True, labelleft=True, right=True, labelright=True)

        y_max = max(max(y_iron), max(y_oil), max(y_lead))
        ax.set_ylim(0, y_max * 1.1)
        ax.yaxis.set_major_formatter(FuncFormatter(y_formatter))

    plt.tight_layout()

    img_path = 'charts_output/所有建筑_资源折线图_1x9.png'
    os.makedirs('charts_output', exist_ok=True)
    # dpi 也提高，进一步保证清晰度
    plt.savefig(img_path, dpi=200, bbox_inches='tight')
    plt.close()

    print(f"\n🎉 长条图已保存至 '{img_path}'")


# ================= 配置区域 =================
INPUT_CSV = 'output.csv'
OUTPUT_CSV = 'result_no_interval.csv'

if __name__ == '__main__':
    process_game_data(INPUT_CSV, OUTPUT_CSV)