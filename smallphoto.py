from PIL import Image
import os

def generate_thumbnail(original_path, thumbnail_path, size=(150, 150)):
    """
    生成缩略图
    Args:
        original_path (str): 原始图片路径
        thumbnail_path (str): 缩略图保存路径
        size (tuple): 缩略图尺寸，默认为 (150, 150)
    """
    # 确保缩略图目录存在
    os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)

    # 如果缩略图已存在，则直接返回
    if os.path.exists(thumbnail_path):
        return thumbnail_path

    try:
        # 打开原始图片
        with Image.open(original_path) as img:
            # 保持长宽比生成缩略图
            img.thumbnail(size)
            # 保存缩略图
            img.save(thumbnail_path, "JPEG")
            print(f"Generated thumbnail: {thumbnail_path}")
            return thumbnail_path
    except Exception as e:
        print(f"Error generating thumbnail for {original_path}: {e}")
        return None