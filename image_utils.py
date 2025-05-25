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
    
    # 查找连接的组件（主体）
    num_labels, labels_im = cv2.connectedComponents(subject_mask)
    num_subjects = num_labels - 1  # 减去背景
    
    if num_subjects != 1:
        raise Exception(f"未检测到主体或检测到多个主体（{num_subjects} 个主体）")
    
    # 获取主体的边界框
    coords = cv2.findNonZero(subject_mask)
    x, y, w, h = cv2.boundingRect(coords)
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