import os
from opencc import OpenCC

def convert_traditional_to_simplified(root_dir):
    """
    将目录下所有子目录文件中的繁体中文转换为简体中文
    :param root_dir: 需要处理的根目录路径
    """
    cc = OpenCC('t2s')  # 初始化转换器（繁体 -> 简体）
    encodings_to_try = ['utf-8', 'gbk', 'big5', 'gb18030']  # 常见中文编码列表

    # 遍历根目录下的所有子目录
    for dir_name in os.listdir(root_dir):
        subdir_path = os.path.join(root_dir, dir_name)
        
        if not os.path.isdir(subdir_path):
            continue  # 跳过非目录项

        # 遍历所有子目录及其文件
        for root, dirs, files in os.walk(subdir_path):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                
                # 跳过二进制文件等非文本文件
                if not is_text_file(file_path):
                    continue

                # 尝试用不同编码读取文件
                content, file_encoding = read_file_with_encodings(file_path, encodings_to_try)
                if content is None:
                    print(f"无法解码文件: {file_path}")
                    continue

                # 转换内容并写回文件
                try:
                    simplified_content = cc.convert(content)
                    write_file(file_path, simplified_content, file_encoding)
                    print(f"已处理: {file_path}")
                except Exception as e:
                    print(f"处理文件失败: {file_path}，错误: {str(e)}")

def is_text_file(file_path):
    """简单判断是否为文本文件"""
    try:
        with open(file_path, 'tr') as check_file:
            check_file.read(1024)
            return True
    except UnicodeDecodeError:
        return False
    except:
        return False

def read_file_with_encodings(file_path, encodings):
    """尝试用多种编码读取文件"""
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read(), encoding
        except UnicodeDecodeError:
            continue
        except Exception as e:
            continue
    return None, None

def write_file(file_path, content, encoding):
    """写入文件"""
    with open(file_path, 'w', encoding=encoding) as f:
        f.write(content)

if __name__ == "__main__":
    target_directory = input("请输入要处理的根目录路径: ").strip()
    if os.path.isdir(target_directory):
        convert_traditional_to_simplified(target_directory)
        print("转换完成！")
    else:
        print("输入的路径无效或不是目录")