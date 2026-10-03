import os
import re
import codecs

def unicode_escape_to_chinese(text):
    # 把 \uXXXX 转成对应字符
    return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)

def convert_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = unicode_escape_to_chinese(content)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)

def convert_dir(root_dir):
    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            if name.endswith('.smali'):
                full = os.path.join(dirpath, name)
                try:
                    convert_file(full)
                    print('转换成功:', full)
                except Exception as e:
                    print('失败:', full, e)

if __name__ == '__main__':
    # 改成你的 smali 文件夹路径
    convert_dir(r'/Users/mac/Documents/learn/pythonProject/mini_tk/base2')