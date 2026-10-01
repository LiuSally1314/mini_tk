import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

# ============ 数据 ============
data = [
    ["仓库", "0-120", "12.11G", "12.11G", "12.11G"],
    ["坦克工厂", "0-120", "48.52G", "36.40G", "24.25G"],
    ["指挥中心", "0-120", "24.17G", "24.17G", "24.17G"],
    ["改装车间", "0-120", "30.33G", "18.19G", "12.11G"],
    ["水晶工厂", "0-120", "48.55G", "72.87G", "48.55G"],
    ["油井", "0-120", "24.24G", "12.11G", "48.51G"],
    ["科研中心", "0-120", "84.95G", "84.95G", "84.95G"],
    ["钛矿场", "0-120", "84.95G", "84.95G", "84.95G"],
    ["铁矿场", "0-120", "12.11G", "48.52G", "24.24G"],
    ["仓库", "0-80", "1.58G", "1.58G", "1.58G"],
    ["仓库", "81-100", "3.22G", "3.22G", "3.22G"],
    ["仓库", "100-110", "2.93G", "2.93G", "2.93G"],
    ["仓库", "110-120", "4.39G", "4.39G", "4.39G"],
    ["坦克工厂", "0-120", "48.52G", "36.40G", "24.25G"],
    ["坦克工厂", "0-80", "6.34G", "4.75G", "3.17G"],
    ["坦克工厂", "81-100", "12.87G", "9.65G", "6.43G"],
    ["坦克工厂", "100-110", "11.74G", "8.79G", "5.86G"],
    ["坦克工厂", "110-120", "17.58G", "13.20G", "8.78G"],
    ["指挥中心", "0-80", "3.10G", "3.10G", "3.10G"],
    ["指挥中心", "81-100", "6.43G", "6.43G", "6.43G"],
    ["指挥中心", "100-110", "5.86G", "5.86G", "5.86G"],
    ["指挥中心", "110-120", "8.78G", "8.78G", "8.78G"],
    ["改装车间", "0-80", "3.96G", "2.38G", "1.58G"],
    ["改装车间", "81-100", "8.05G", "4.83G", "3.22G"],
    ["改装车间", "100-110", "7.32G", "4.39G", "2.93G"],
    ["改装车间", "110-120", "11.00G", "6.58G", "4.39G"],
    ["水晶工厂", "0-80", "6.34G", "9.50G", "6.34G"],
    ["水晶工厂", "81-100", "12.87G", "19.36G", "12.87G"],
    ["水晶工厂", "100-110", "11.74G", "17.62G", "11.74G"],
    ["水晶工厂", "110-120", "17.60G", "26.39G", "17.60G"],
    ["油井", "0-80", "3.17G", "1.58G", "6.34G"],
    ["油井", "81-100", "6.43G", "3.22G", "12.87G"],
    ["油井", "100-110", "5.86G", "2.93G", "11.73G"],
    ["油井", "110-120", "8.77G", "4.39G", "17.58G"],
    ["科研中心", "0-80", "11.09G", "11.09G", "11.09G"],
    ["科研中心", "81-100", "22.57G", "22.57G", "22.57G"],
    ["科研中心", "100-110", "20.55G", "20.55G", "20.55G"],
    ["科研中心", "110-120", "30.75G", "30.75G", "30.75G"],
    ["钛矿场", "0-80", "11.09G", "11.09G", "11.09G"],
    ["钛矿场", "81-100", "22.57G", "22.57G", "22.57G"],
    ["钛矿场", "100-110", "20.55G", "20.55G", "20.55G"],
    ["钛矿场", "110-120", "30.75G", "30.75G", "30.75G"],
    ["铁矿场", "0-80", "1.58G", "6.34G", "3.17G"],
    ["铁矿场", "81-100", "3.22G", "12.87G", "6.43G"],
    ["铁矿场", "100-110", "2.93G", "11.73G", "5.86G"],
    ["铁矿场", "110-120", "4.39G", "17.58G", "8.77G"],
    ["铅矿场", "0-120", "48.45G", "24.21G", "12.10G"],
    ["铅矿场", "0-80", "6.28G", "3.14G", "1.57G"],
    ["铅矿场", "81-100", "12.87G", "6.43G", "3.22G"],
    ["铅矿场", "100-110", "11.73G", "5.86G", "2.93G"],
    ["铅矿场", "110-120", "17.58G", "8.78G", "4.39G"],
]

headers = ["建筑", "等级区间", "铁矿", "石油", "铅矿"]

# ============ 字体设置 ============
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'PingFang SC',
                                    'WenQuanYi Micro Hei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# ============ 画布 ============
n_rows = len(data)
fig, ax = plt.subplots(figsize=(15, 24), dpi=130)
ax.axis('off')
fig.patch.set_facecolor('#F5F7FA')

# ============ 尺寸参数 ============
col_widths = [2.6, 2.2, 2.4, 2.4, 2.4]
row_h = 1.0
head_h = 1.3
table_w = sum(col_widths)
table_h = head_h + n_rows * row_h

# ============ 表头 ============
head_colors = ['#34495E', '#34495E', '#C0392B', '#27AE60', '#8E44AD']
head_y = table_h - head_h
x = 0
for h, w, c in zip(headers, col_widths, head_colors):
    rect = FancyBboxPatch((x, head_y), w, head_h,
                          boxstyle="round,pad=0,rounding_size=0",
                          facecolor=c, edgecolor='white', linewidth=2)
    ax.add_patch(rect)
    ax.text(x + w/2, head_y + head_h/2, h,
            ha='center', va='center', fontsize=20, fontweight='bold',
            color='white')
    x += w

# ============ 数据行 ============
building_colors = {
    '仓库': '#3498DB',
    '坦克工厂': '#E74C3C',
    '指挥中心': '#9B59B6',
    '改装车间': '#E67E22',
    '水晶工厂': '#1ABC9C',
    '油井': '#F1C40F',
    '科研中心': '#2980B9',
    '钛矿场': '#16A085',
    '铁矿场': '#7F8C8D',
    '铅矿场': '#8E44AD',
}

prev_building = None
group_index = 0
group_colors = ['#FFFFFF', '#F4F8FB']

for i, row in enumerate(data):
    y = table_h - head_h - (i + 1) * row_h
    building = row[0]
    if building != prev_building:
        group_index += 1
    bg = group_colors[group_index % 2]

    x = 0
    for j, (cell, w) in enumerate(zip(row, col_widths)):
        rect = mpatches.Rectangle((x, y), w, row_h,
                                   facecolor=bg, edgecolor='#D5DBDB', linewidth=1)
        ax.add_patch(rect)

        if j == 0:
            bar = mpatches.Rectangle((x, y), 0.12, row_h,
                                      facecolor=building_colors.get(cell, '#95A5A6'),
                                      edgecolor='none')
            ax.add_patch(bar)
            ax.text(x + w/2 + 0.05, y + row_h/2, cell,
                    ha='center', va='center', fontsize=16,
                    fontweight='bold', color='#2C3E50')
        elif j == 1:
            ax.text(x + w/2, y + row_h/2, cell,
                    ha='center', va='center', fontsize=15,
                    color='#566573', fontweight='medium')
        else:
            ax.text(x + w/2, y + row_h/2, cell,
                    ha='center', va='center', fontsize=15,
                    fontweight='bold', color='#2C3E50')
        x += w
    prev_building = building

# ============ 分组大框 ============
groups = []
start = 0
for i in range(1, len(data) + 1):
    if i == len(data) or data[i][0] != data[start][0]:
        groups.append((data[start][0], start, i - 1))
        start = i

for name, s, e in groups:
    if e > s:
        y_top = table_h - head_h - s * row_h
        y_bot = table_h - head_h - (e + 1) * row_h
        box = mpatches.Rectangle((-0.15, y_bot - 0.05),
                                  table_w + 0.3, (y_top - y_bot) + 0.1,
                                  facecolor='none',
                                  edgecolor=building_colors.get(name, '#95A5A6'),
                                  linewidth=3, zorder=5)
        ax.add_patch(box)

# ============ 表格外框 ============
outer = mpatches.Rectangle((0, table_h - head_h - n_rows * row_h),
                            table_w, n_rows * row_h,
                            facecolor='none', edgecolor='#34495E', linewidth=2)
ax.add_patch(outer)

# ============ 标题 ============
ax.text(table_w/2, table_h + 1.2, '建筑升级资源消耗总览',
        ha='center', va='bottom', fontsize=32, fontweight='bold',
        color='#1A252F')
ax.text(table_w/2, table_h + 0.4, 'Building Upgrade Resource Cost Overview',
        ha='center', va='bottom', fontsize=16, color='#7F8C8D', style='italic')

# ============ 坐标范围 ============
ax.set_xlim(-1, table_w + 1)
ax.set_ylim(table_h - head_h - n_rows * row_h - 0.3, table_h + 2.5)

plt.savefig('building_resources.png', dpi=130, bbox_inches='tight',
            facecolor='#F5F7FA', edgecolor='none', pad_inches=0.4)
plt.show()
print("图片已保存为 building_resources.png")