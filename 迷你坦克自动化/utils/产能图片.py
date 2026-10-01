import matplotlib.pyplot as plt

# ===== 字体设置 =====
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# ===== 数据 =====
columns = ["水晶", "铁矿", "石油", "铅矿", "钛矿"]
production = ["0.715", "4.55", "0.343", "2.28", "1.14"]   # M/H
capacity   = ["125", "159", "120", "7.95", "199"]          # M

# ===== 画布 =====
fig, ax = plt.subplots(figsize=(12, 8), dpi=200)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis('off')

# ===== 标题 =====
ax.text(0.5, 0.95, "单个满级120资源工厂提供的产量及容量统计",
        ha='center', va='center', fontsize=21, fontweight='bold', color='#1a1a1a')

# ===== 表格区域 =====
left, right = 0.06, 0.94
top, bottom = 0.82, 0.46
n_rows = 3
n_cols = len(columns) + 1

col_width = (right - left) / n_cols
row_height = (top - bottom) / n_rows

# ===== 画横线 =====
for i in range(n_rows + 1):
    y = top - i * row_height
    ax.plot([left, right], [y, y], color='black', linewidth=1.6)

# ===== 画竖线 =====
for j in range(n_cols + 1):
    x = left + j * col_width
    ax.plot([x, x], [bottom, top], color='black', linewidth=1.6)

# ===== 左上角单元格：左对角线 =====
x0, x1 = left, left + col_width
y0, y1 = top, top - row_height
ax.plot([x0, x1], [y0, y1], color='black', linewidth=1.6)

# ===== 对角线两侧文字 =====
ax.text(x0 + col_width * 0.72, y0 - row_height * 0.22, "资源工厂",
        ha='center', va='center', fontsize=17, fontweight='bold', color='#1a1a1a')
ax.text(x0 + col_width * 0.28, y1 + row_height * 0.22, "项目",
        ha='center', va='center', fontsize=17, fontweight='bold', color='#1a1a1a')

# ===== 表头：资源名称 =====
for j, col in enumerate(columns):
    x = left + (j + 1) * col_width + col_width / 2
    y = top - row_height / 2
    ax.text(x, y, col, ha='center', va='center',
            fontsize=18, fontweight='bold', color='#1a1a1a')

# ===== 第一列：项目名称 =====
row_labels = ["产量(M/H)", "容量(M)"]
for i, label in enumerate(row_labels):
    x = left + col_width / 2
    y = top - (i + 1) * row_height - row_height / 2
    ax.text(x, y, label, ha='center', va='center',
            fontsize=16, fontweight='bold', color='#1a1a1a')

# ===== 数据：产量 =====
for j, val in enumerate(production):
    x = left + (j + 1) * col_width + col_width / 2
    y = top - row_height - row_height / 2
    ax.text(x, y, val, ha='center', va='center',
            fontsize=16, color='#333333')

# ===== 数据：容量 =====
for j, val in enumerate(capacity):
    x = left + (j + 1) * col_width + col_width / 2
    y = top - 2 * row_height - row_height / 2
    ax.text(x, y, val, ha='center', va='center',
            fontsize=16, color='#333333')

# ===== 说明文字 =====
notes = [
    "说明：",
    "1. 以上统计的是单个满级120资源工厂产量及其容量",
    "2. 不包含指挥中心提供的产量，不包含指挥中心仓库提供的容量",
    "3. 不叠加其他资源及容量加成，如VIP特权"
]

note_x = left
note_y = bottom - 0.06
line_gap = 0.06

for i, note in enumerate(notes):
    if i == 0:
        ax.text(note_x, note_y - i * line_gap, note,
                ha='left', va='top', fontsize=15,
                fontweight='bold', color='#1a1a1a')
    else:
        ax.text(note_x, note_y - i * line_gap, note,
                ha='left', va='top', fontsize=14, color='#444444')

# ===== 保存 =====
plt.savefig("resource_table.png", bbox_inches='tight', facecolor='white')
plt.show()