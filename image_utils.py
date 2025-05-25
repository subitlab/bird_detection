import cv2
import numpy as np
from torchvision import models, transforms
import torch
from PIL import Image
import os
import random
import string

# 确定计算设备
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 加载分割模型
def load_segmentation_model():
    model = models.segmentation.deeplabv3_resnet101(pretrained=True)
    model.to(DEVICE)
    model.eval()
    return model

segmentation_model = load_segmentation_model()

# 生成随机文件名的函数
def generate_random_filename(extension):
    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    return f"{random_str}.{extension}"

def compress_image(image_path, output_folder="uploads"):
    image = Image.open(image_path).convert("RGB")
    orig_w, orig_h = image.size
    scale = min(1024 / orig_w, 1024 / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    image_resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

    background = Image.new("RGB", (1024, 1024), (255, 255, 255))
    x_offset = (1024 - new_w) // 2
    y_offset = (1024 - new_h) // 2
    background.paste(image_resized, (x_offset, y_offset))

    os.makedirs(output_folder, exist_ok=True)
    output_filename = generate_random_filename("jpg")
    output_path = os.path.join(output_folder, output_filename)
    background.save(output_path, quality=85)
    return output_path

# 图片预处理
def preprocess(image):
    preprocess_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225])
    ])
    return preprocess_transform(image).unsqueeze(0).to(DEVICE)

# 分割背景
def remove_background(image_path):
    image = Image.open(image_path).convert("RGB")
    input_tensor = preprocess(image)
    
    with torch.no_grad():
        output = segmentation_model(input_tensor)["out"][0]
    # 将输出上采样到输入图像大小
    output = torch.nn.functional.interpolate(
        output.unsqueeze(0),
        size=image.size[::-1],
        mode='bilinear',
        align_corners=False
    )[0]
    mask = output.argmax(0).byte().cpu().numpy()
    
    image_np = np.array(image)
    return image_np, mask

# 创建最终图像
def create_final_image(image_np, mask, output_folder="uploads"):
    # 识别主体部分
    subject_mask = (mask > 0).astype(np.uint8)
    
    # 形态学操作清理掩膜
    # 1. 开运算：去除小噪声
    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    subject_mask = cv2.morphologyEx(subject_mask, cv2.MORPH_OPEN, kernel_small)
    
    # 2. 闭运算：连接断开的区域
    kernel_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    subject_mask = cv2.morphologyEx(subject_mask, cv2.MORPH_CLOSE, kernel_large)
    
    # 查找连接的组件（主体）
    num_labels, labels_im = cv2.connectedComponents(subject_mask)
    num_subjects = num_labels - 1  # 减去背景
    
    if num_subjects == 0:
        raise Exception(f"未检测到任何主体")
    elif num_subjects == 1:
        # 只有一个主体，使用原有逻辑
        coords = cv2.findNonZero(subject_mask)
        x, y, w, h = cv2.boundingRect(coords)
    else:
        # 多个主体时，选择最佳的主体
        print(f"🔍 检测到 {num_subjects} 个主体，智能选择最佳主体")
        
        best_score = 0
        best_component = 0
        image_center_x, image_center_y = image_np.shape[1] // 2, image_np.shape[0] // 2
        
        # 遍历所有连通组件，计算综合评分
        for label in range(1, num_labels):  # 跳过背景（label=0）
            component_mask = (labels_im == label).astype(np.uint8)
            area = cv2.countNonZero(component_mask)
            
            # 跳过过小的组件
            if area < 100:  # 过滤掉噪声点
                continue
            
            # 获取组件的边界框和中心点
            coords = cv2.findNonZero(component_mask)
            if coords is None:
                continue
                
            x, y, w, h = cv2.boundingRect(coords)
            component_center_x = x + w // 2
            component_center_y = y + h // 2
            
            # 计算综合评分
            # 1. 面积评分 (40%)
            area_score = area / (image_np.shape[0] * image_np.shape[1])  # 归一化面积
            
            # 2. 位置评分 (30%) - 越靠近图像中心越好
            distance_to_center = np.sqrt((component_center_x - image_center_x)**2 + 
                                       (component_center_y - image_center_y)**2)
            max_distance = np.sqrt(image_center_x**2 + image_center_y**2)
            position_score = 1 - (distance_to_center / max_distance)
            
            # 3. 形状评分 (20%) - 长宽比接近1:1到2:1之间较好（鸟类特征）
            aspect_ratio = max(w, h) / min(w, h)
            if aspect_ratio <= 2.0:
                shape_score = 1.0
            elif aspect_ratio <= 3.0:
                shape_score = 0.7
            else:
                shape_score = 0.3
            
            # 4. 尺寸评分 (10%) - 不能太小也不能太大
            size_ratio = min(w, h) / max(image_np.shape[0], image_np.shape[1])
            if 0.1 <= size_ratio <= 0.8:
                size_score = 1.0
            else:
                size_score = 0.5
            
            # 综合评分
            total_score = (area_score * 0.6 + position_score * 0.1 + 
                          shape_score * 0.1 + size_score * 0.1)
            
            print(f"  组件 {label}: 面积={area}, 位置=({component_center_x},{component_center_y}), "
                  f"尺寸={w}x{h}, 评分={total_score:.3f}")
            
            if total_score > best_score:
                best_score = total_score
                best_component = label
        
        if best_component == 0:
            raise Exception(f"未找到合适的主体组件")
        
        # 创建只包含最佳主体的掩膜
        subject_mask = (labels_im == best_component).astype(np.uint8)
        coords = cv2.findNonZero(subject_mask)
        
        if coords is None:
            raise Exception(f"无法找到最佳主体的坐标")
            
        x, y, w, h = cv2.boundingRect(coords)
        print(f"✅ 选择了评分最高的主体 (评分: {best_score:.3f}, 尺寸: {w}x{h})")
    
    # 检查主体尺寸
    if w < 64 or h < 64:
        raise Exception(f"主体尺寸过小（{w}x{h}）")
    
    # 提取主体和掩膜
    subject = image_np[y:y+h, x:x+w]
    subject_mask = subject_mask[y:y+h, x:x+w]
    
    # 保持长宽比调整主体尺寸到适合 224x224
    subject_h, subject_w = subject.shape[:2]
    scale = min(224 / subject_w, 224 / subject_h)
    new_w = int(subject_w * scale)
    new_h = int(subject_h * scale)
    subject_resized = cv2.resize(subject, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    mask_resized = cv2.resize(subject_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
    mask_resized = mask_resized.astype(bool)
    
    # 创建随机噪声背景
    final_image = np.random.randint(0, 256, (224, 224, 3), dtype=np.uint8)
    
    # 计算主体在背景中的位置，使其居中
    x_offset = (224 - new_w) // 2
    y_offset = (224 - new_h) // 2
    
    # 合成最终图像
    roi = final_image[y_offset:y_offset+new_h, x_offset:x_offset+new_w]
    roi[mask_resized] = subject_resized[mask_resized]
    final_image[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = roi
    
    # 将图像从BGR转换为RGB
    final_image_rgb = cv2.cvtColor(final_image, cv2.COLOR_BGR2RGB)
    final_image_pil = Image.fromarray(final_image_rgb)

    os.makedirs(output_folder, exist_ok=True)
    output_filename = generate_random_filename("jpg")
    output_path = os.path.join(output_folder, output_filename)
    final_image_pil.save(output_path)
    return output_path