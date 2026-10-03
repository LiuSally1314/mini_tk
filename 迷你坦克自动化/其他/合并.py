import pandas as pd

# 读取文件
items_df = pd.read_csv('output.csv', encoding='utf-8-sig')
email_df = pd.read_csv('/Users/mac/Documents/learn/pythonProject/mini_tk/迷你坦克自动化/data/save_email_info.csv', encoding='utf-8-sig')

# 清理列名（去 BOM、空格）
items_df.columns = items_df.columns.str.strip().str.replace('\ufeff', '', regex=False)
email_df.columns = email_df.columns.str.strip().str.replace('\ufeff', '', regex=False)

# email 去重，保留第一条
email_df = email_df.drop_duplicates(subset=['name'], keep='first')

# 以 output.csv 为主表，左连接拿 desc
merged_df = items_df.merge(
    email_df[['name', 'desc']],
    on='name',
    how='left'
)

# id 转整数
merged_df['id'] = pd.to_numeric(merged_df['id'], errors='coerce').astype('Int64')

# 按 id 排序
merged_df = merged_df.sort_values(by='id', ascending=True).reset_index(drop=True)

# 找出所有重复的 name
dup_names = merged_df['name'][merged_df['name'].duplicated(keep=False)].unique()

# 给每个重复的 name 分配一个组号
name_to_group = {name: i + 1 for i, name in enumerate(dup_names)}

# remark：重复的词填对应组号，不重复留空
merged_df['remark'] = merged_df['name'].map(name_to_group).fillna('')

# 构造结果：不要编号列
result_df = pd.DataFrame({
    'id': merged_df['id'],
    'name': merged_df['name'],
    'desc': merged_df['desc'].fillna(''),
    'remark': merged_df['remark']
})

# 输出
result_df.to_csv('合并结果.csv', index=False, encoding='utf-8-sig')

print(f"合并完成，共 {len(result_df)} 条记录")