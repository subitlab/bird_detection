# 🐦 智能鸟类识别系统

一个基于深度学习的智能鸟类识别Web应用，支持图片上传识别、照片墙浏览和详细的鸟类信息查看功能。

## 📸 主要功能

### 🎯 鸟类识别
- **上传识别**：支持上传 PNG、JPG、JPEG、GIF 格式的图片进行鸟类识别
- **照片墙选择**：从精选的鸟类图片库中选择图片进行识别
- **实时处理**：自动进行图像压缩、背景移除、图像增强等预处理
- **准确识别**：基于深度学习模型进行鸟类种类预测

### 🖼️ 照片墙展示
- **动态轮播**：精美的无缝循环轮播展示
- **智能过滤**：自动过滤无效图片，确保展示质量
- **随机采样**：每次访问随机展示50张精选鸟类图片
- **交互体验**：支持鼠标悬停暂停、点击选择等交互

### 📖 鸟类详情页
- **详细信息**：展示鸟类的描述、分布等详细信息
- **本地数据**：支持本地鸟类数据存储和展示
- **图片展示**：高质量的鸟类图片展示
- **版权声明**：完整的版权保护和免责声明

## 🛠️ 技术栈

### 后端技术
- **Flask** - Python Web框架
- **OpenCV** - 图像处理
- **PIL/Pillow** - 图像操作
- **pandas** - 数据处理
- **NumPy** - 数值计算
- **深度学习模型** - 鸟类识别核心算法

### 前端技术
- **HTML5/CSS3** - 现代化UI设计
- **JavaScript ES6** - 动态交互效果
- **响应式设计** - 适配各种设备
- **CSS动画** - 流畅的视觉效果

### 数据处理
- **requests** - HTTP请求处理
- **PyQuery** - HTML解析
- **JSON** - 数据存储格式
- **CSV** - 数据映射文件

## 📁 项目结构

```
├── app.py                    # Flask主应用文件
├── image_utils.py           # 图像处理工具
├── model_utils.py           # 模型预测工具
├── filter_problematic_images.py  # 图片验证脚本
├── class_mapping.csv        # 鸟类ID和名称映射
├── all_data.csv            # 完整数据集信息
├── invalid_images_list.txt  # 无效图片黑名单
├── templates/              # HTML模板目录
│   ├── index.html          # 主页模板
│   ├── processing.html     # 处理页面模板
│   ├── result.html         # 结果展示模板
│   └── bird_detail.html    # 鸟类详情模板
├── static/                 # 静态文件目录
│   └── [鸟类图片数据集]
├── uploads/                # 用户上传文件目录
├── bird_data_local/        # 本地鸟类数据目录
│   └── [鸟类ID]/
│       ├── info.json       # 鸟类基本信息
│       ├── description.html # 鸟类描述
│       ├── distribution.html # 鸟类分布
│       └── images/         # 鸟类图片
└── README.md               # 项目说明文件
```

## 🚀 安装指南

### 环境要求
- Python 3.7+
- pip包管理器

### 安装步骤

1. **克隆项目**
```bash
git clone <your-repository-url>
cd bird-recognition-system
```

2. **安装依赖**
```bash
pip install flask opencv-python pillow pandas numpy requests pyquery
```

3. **准备数据文件**
   - 确保 `class_mapping.csv` 存在（鸟类ID映射文件）
   - 确保 `all_data.csv` 存在（数据集信息文件）
   - 将鸟类图片数据放入 `static/` 目录

4. **创建必要目录**
```bash
mkdir -p uploads bird_data_local
```

5. **（可选）生成无效图片列表**
```bash
python filter_problematic_images.py
```

## 🎮 使用方法

### 启动应用
```bash
python app.py
```
应用将在 `http://localhost` (端口80) 启动

### 功能使用

#### 1. 鸟类识别
- 访问主页，选择"上传图片"或从照片墙中选择图片
- 系统会自动处理图片并进行识别
- 查看识别结果和置信度

#### 2. 浏览照片墙
- 主页展示精选鸟类图片的动态轮播
- 鼠标悬停可暂停轮播
- 点击图片名称可查看详细信息

#### 3. 查看鸟类详情
- 在识别结果页或照片墙点击鸟类名称
- 查看详细的鸟类描述和分布信息
- 浏览高质量的鸟类图片

## 📊 数据说明

### 数据集格式
- `all_data.csv`：包含图片路径、鸟类类别、数据集划分等信息
- `class_mapping.csv`：鸟类数字ID与中文名称的映射关系
- `invalid_images_list.txt`：经过验证的无效图片列表

### 本地鸟类数据结构
```
bird_data_local/
└── [鸟类ID]/
    ├── info.json           # 基本信息
    ├── description.html    # 描述内容
    ├── distribution.html   # 分布信息
    └── images/            # 相关图片
        └── *.jpg
```

## 🔧 配置选项

### 应用配置
- `UPLOAD_FOLDER`：上传文件存储目录
- `ALLOWED_EXTENSIONS`：允许的文件扩展名
- `DATA_FOLDER`：数据集根目录

### 性能优化
- 图片自动压缩处理
- 无效图片过滤机制
- 后台异步处理
- 智能缓存策略

## 🛡️ 安全特性

- 文件类型验证
- 随机文件名生成
- 输入参数校验
- 错误处理机制
- 版权保护声明

## 📈 性能数据

基于测试数据集的性能统计：
- **总测试图片**：2,696张
- **有效图片**：1,550张 (57.5%)
- **过滤图片**：1,146张 (42.5%)
- **支持格式**：PNG、JPG、JPEG、GIF

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📝 版权声明

本项目仅用于学习和研究目的。鸟类详情页面中的内容来源于鸟网(birdnet.cn)，版权归原作者所有。如有版权问题，请联系 yangzixiao2027@i.pkuschool.edu.cn。

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🔗 相关链接

- [鸟网官网](https://www.birdnet.cn)
- [Flask文档](https://flask.palletsprojects.com/)
- [OpenCV文档](https://opencv.org/)

## 📞 联系方式

如有问题或建议，请联系：yangzixiao2027@i.pkuschool.edu.cn

---
⭐ 如果这个项目对您有帮助，请给个星标支持！ 