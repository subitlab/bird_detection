FROM --platform=linux/amd64 python:3.10-slim

WORKDIR /app

COPY requirements.txt .

# 安装 OpenCV 所需的系统库 + Python 库
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 curl && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
        torch torchvision \
        --index-url https://download.pytorch.org/whl/cpu

# 先复制模型相关文件
COPY image_utils.py .
COPY model_utils.py .
COPY epoch40_model.pth .

# 创建预下载模型的脚本并运行
RUN echo "import torch\nfrom torchvision import models\nprint('预下载DeepLabV3模型...')\nmodel = models.segmentation.deeplabv3_resnet101(pretrained=True)\nprint('模型下载完成！')" > preload_model.py && \
    python preload_model.py && \
    rm preload_model.py

# 复制其余文件
COPY . .

ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=80

EXPOSE 80

CMD ["flask", "run"]