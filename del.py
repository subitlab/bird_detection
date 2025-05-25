import os
import pandas as pd

def clean_non_test_images(csv_path, data_folder, new_data_folder):
    """
    清除表格中 'data set' 列不是 'test' 的所有图片，同时删除 new_data 文件夹中的对应文件。
    
    Args:
    - csv_path: str，表格文件路径 (e.g., "all_data.csv")
    - data_folder: str，原始图片所在的文件夹 (e.g., "data")
    - new_data_folder: str，去除背景后的图片所在的文件夹 (e.g., "new_data")
    """
    # 加载 CSV 表格
    df = pd.read_csv(csv_path, header=None, names=["filepaths", "labels", "class", "data set"])

    # 筛选 'data set' 列为 'test' 的文件路径
    test_images = set(df[df['data set'] == 'test']['filepaths'])

    # 遍历表格中的所有文件路径
    all_images = set(df['filepaths'])
    non_test_images = all_images - test_images  # 计算非 'test' 的文件路径

    # 删除非 'test' 的文件
    for filepath in non_test_images:
        # 转换为系统兼容路径格式
        normalized_filepath = filepath.replace("\\", "/")  # 如果表格中有 `\`，替换为 `/`
        normalized_filepath = os.path.normpath(normalized_filepath)
        print(normalized_filepath)

        # 删除原始图片
        data_path = os.path.join(data_folder, normalized_filepath)
        if os.path.exists(data_path):
            os.remove(data_path)
            print(f"Deleted: {data_path}")

        # # 删除 new_data 中的对应文件
        # new_data_path = os.path.join(new_data_folder, normalized_filepath)
        # if os.path.exists(new_data_path):
        #     os.remove(new_data_path)
        #     print(f"Deleted: {new_data_path}")

    print("清理完成：所有非 'test' 图片已删除。")

# 示例调用
csv_path = "all_data.csv"  # 替换为实际 CSV 路径
data_folder = ""  # 替换为原始图片文件夹路径
new_data_folder = "new_"  # 替换为去除背景后的图片文件夹路径

clean_non_test_images(csv_path, data_folder, new_data_folder)