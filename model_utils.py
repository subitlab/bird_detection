import torch
from torchvision import transforms, models
from PIL import Image
import pandas as pd
from config import MODEL_PATH, CSV_PATH
import os

# 确定计算设备
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 加载类别映射
class_mapping = pd.read_csv(CSV_PATH)
class_to_label = class_mapping.set_index('class')['original_label'].to_dict()

# 加载分类模型
def load_classification_model():
    model = models.resnet50(weights=None)
    num_classes = 167
    model.fc = torch.nn.Linear(model.fc.in_features, num_classes)
    model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    model.to(DEVICE)
    model.eval()
    return model

classification_model = load_classification_model()

# 数据转换
data_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

def predict_image(image_path):
    """模型预测"""
    image = Image.open(image_path).convert("RGB")
    input_tensor = data_transforms(image).unsqueeze(0).to(DEVICE)

    # 模型预测
    with torch.no_grad():
        outputs = classification_model(input_tensor)
        _, preds = torch.max(outputs, 1)
        predicted_class = preds.item()
        return class_to_label.get(predicted_class, "未知类别")