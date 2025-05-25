import os
import cv2
import numpy as np
import pandas as pd
from image_utils import remove_background
from tqdm import tqdm  # 导入tqdm进度条库

# 数据文件夹路径和CSV文件路径
DATA_FOLDER = 'static/'
CSV_PATH = 'all_data.csv'

# 检查图片墙中所有图片是否含有多个主体，若有则删除，同时删除CSV中的相关记录
def delete_images_with_multiple_subjects():
    # 读取CSV文件
    df = pd.read_csv(CSV_PATH)
    
    # 筛选出data set为'test'的记录
    test_df = df[df['data set'] == 'test']
    
    # 获取所有图片文件路径
    image_files = test_df['filepaths'].tolist()
    
    # 使用 tqdm 进度条来显示处理过程
    for image_file in tqdm(image_files, desc="Processing images", unit="image"):
        image_path = os.path.join(DATA_FOLDER, image_file)
        
        try:
            # 使用remove_background函数检测图片中主体
            image_np, mask = remove_background(image_path)
            
            # 识别主体部分
            subject_mask = (mask > 0).astype(np.uint8)
            
            # 查找连接的组件（主体）
            num_labels, labels_im = cv2.connectedComponents(subject_mask)
            num_subjects = num_labels - 1  # 减去背景
            
            if num_subjects > 1:
                # 如果有多个主体，则删除该图片
                os.remove(image_path)
                print(f"删除图片: {image_file}")
                
                # 从CSV中删除该图片对应的行
                image_row = test_df[test_df['filepaths'] == image_file]
                if not image_row.empty:
                    test_df = test_df.drop(image_row.index)
                    print(f"删除CSV中的记录: {image_file}")
        
        except Exception as e:
            print(f"处理图片 {image_file} 时发生错误: {e}")

    # 将更新后的DataFrame保存回CSV文件
    test_df.to_csv(CSV_PATH, index=False)
    print("CSV文件更新完成！")

if __name__ == '__main__':
    try:
        delete_images_with_multiple_subjects()
        print("所有包含多个主体的图片及其CSV记录已删除！")
    except Exception as e:
        print(f"删除失败：{e}")