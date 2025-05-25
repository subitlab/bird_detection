from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify, session
import os
import random
import string
import uuid
import threading
from werkzeug.utils import secure_filename
import pandas as pd
from image_utils import compress_image, remove_background, create_final_image
from model_utils import predict_image

# Imports for web scraping
import requests
from pyquery import PyQuery as pq
import urllib.parse
import ssl
import warnings
import json

# Suppress SSL warnings and InsecureRequestWarning
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore") # General warnings

# Configure Flask application
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'your_secret_key'  # Replace with your actual secret key

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
DATA_FOLDER = 'static/'

# Initialize global task dictionary
tasks = {}

# Load class mapping (required for bird name lookup)
BIRD_CLASS_MAPPING_CSV = "class_mapping.csv"
INVALID_IMAGES_LIST = "invalid_images_list.txt"  # 无效图片列表文件

# 添加本地数据目录配置
LOCAL_BIRD_DATA_DIR = "bird_data_local"

try:
    class_mapping_df = pd.read_csv(BIRD_CLASS_MAPPING_CSV)
    # print("class_mapping.csv loaded successfully.")
except FileNotFoundError:
    print(f"错误: {BIRD_CLASS_MAPPING_CSV} 未找到。鸟类名称查找功能将无法工作。")
    class_mapping_df = pd.DataFrame(columns=['class', 'original_label'])

# 加载无效图片列表
def load_invalid_images_list():
    """加载无效图片列表"""
    invalid_images = set()
    if os.path.exists(INVALID_IMAGES_LIST):
        try:
            with open(INVALID_IMAGES_LIST, 'r', encoding='utf-8') as f:
                invalid_images = set(line.strip() for line in f if line.strip())
            print(f"📝 已加载 {len(invalid_images)} 张无效图片的黑名单")
        except Exception as e:
            print(f"⚠️ 加载无效图片列表失败: {e}")
    else:
        print(f"💡 提示: 未找到无效图片列表文件 {INVALID_IMAGES_LIST}")
        print(f"💡 您可以运行 'python filter_problematic_images.py' 来生成此文件")
    return invalid_images

# 在应用启动时加载无效图片列表
invalid_images_set = load_invalid_images_list()

def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_random_filename(extension):
    """Generate a random filename"""
    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    return f"{random_str}.{extension}"

def _get_photo_wall_images():
    """Generate photo wall data with filtering of invalid images"""
    csv_path = "all_data.csv"
    df = pd.read_csv(csv_path)
    class_to_label = {}
    if not class_mapping_df.empty:
        class_to_label = class_mapping_df.set_index('class')['original_label'].to_dict()

    test_images = df[df['data set'] == 'test'][['filepaths', 'class']].values.tolist()
    valid_images_with_labels = []
    filtered_count = 0
    
    for filepath, bird_class_numeric in test_images:
        # 检查图片是否在无效列表中
        if filepath in invalid_images_set:
            filtered_count += 1
            # print(f"🚫 过滤无效图片: {filepath}")
            continue
            
        full_path = os.path.join(DATA_FOLDER, filepath)
        if os.path.exists(full_path):
            bird_name = class_to_label.get(bird_class_numeric, "未知鸟类")
            image_url = url_for('data_file', filename=filepath)
            # 现在包含 bird_class_numeric 以便创建详情页链接
            valid_images_with_labels.append((image_url, bird_name, filepath, bird_class_numeric))

    if filtered_count > 0:
        print(f"✅ 已过滤掉 {filtered_count} 张无效图片，剩余 {len(valid_images_with_labels)} 张有效图片")
    
    displayed_images = random.sample(valid_images_with_labels, min(50, len(valid_images_with_labels)))
    return [displayed_images[i:i + 10] for i in range(0, len(displayed_images), 10)]

def load_local_bird_data(bird_class_id):
    """从本地加载鸟类数据"""
    bird_dir = os.path.join(LOCAL_BIRD_DATA_DIR, str(bird_class_id))
    
    if not os.path.exists(bird_dir):
        return None
    
    # 读取鸟类基本信息
    info_file = os.path.join(bird_dir, 'info.json')
    if not os.path.exists(info_file):
        return None
    
    try:
        with open(info_file, 'r', encoding='utf-8') as f:
            bird_info = json.load(f)
        
        # 读取描述HTML
        description_file = os.path.join(bird_dir, 'description.html')
        description_html = None
        if os.path.exists(description_file):
            with open(description_file, 'r', encoding='utf-8') as f:
                description_html = f.read()
        
        # 读取分布HTML
        distribution_file = os.path.join(bird_dir, 'distribution.html')
        distribution_html = None
        if os.path.exists(distribution_file):
            with open(distribution_file, 'r', encoding='utf-8') as f:
                distribution_html = f.read()
        
        return {
            'info': bird_info,
            'description': description_html,
            'distribution': distribution_html
        }
        
    except Exception as e:
        print(f"⚠️ 读取本地鸟类数据失败 (ID: {bird_class_id}): {e}")
        return None

def _update_local_image_urls(html_content, bird_class_id):
    """更新HTML中的图片URL为本地路径"""
    if not html_content:
        return html_content
    
    # 将相对路径的图片URL更新为Flask路由
    import re
    
    def replace_img_src(match):
        src = match.group(1)
        if src.startswith('images/'):
            # 将 images/xxx.jpg 替换为 /bird_data/{bird_class_id}/images/xxx.jpg
            filename = src.replace('images/', '')
            new_src = url_for('serve_local_bird_image', bird_class_id=bird_class_id, filename=filename)
            return f'src="{new_src}"'
        return match.group(0)
    
    # 使用正则表达式替换 src="images/..." 
    updated_html = re.sub(r'src="(images/[^"]+)"', replace_img_src, html_content)
    return updated_html

# 添加本地图片服务路由
@app.route('/bird_data/<bird_class_id>/images/<filename>')
def serve_local_bird_image(bird_class_id, filename):
    """提供本地鸟类图片文件"""
    bird_dir = os.path.join(LOCAL_BIRD_DATA_DIR, str(bird_class_id))
    images_dir = os.path.join(bird_dir, 'images')
    
    if not os.path.exists(images_dir):
        # 如果本地图片不存在，返回404
        return "Image not found", 404
    
    return send_from_directory(images_dir, filename)

@app.route('/data/<path:filename>')
def data_file(filename):
    """Serve static data files"""
    return send_from_directory(DATA_FOLDER, filename)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/task_status/<task_id>')
def task_status(task_id):
    """Query task status"""
    task = tasks.get(task_id)
    if task:
        return jsonify(task)
    else:
        return jsonify({'status': 'not found'})

def process_task(task_id, task_data):
    """Function to process the image in a background thread"""
    try:
        # Update task status in the global tasks dictionary
        if task_data['step'] == 'upload':
            upload_path = task_data['upload_path']
            tasks[task_id]['steps']['compress_image'] = False
            compressed_image_path = compress_image(upload_path)
            tasks[task_id]['steps']['compress_image'] = True

            tasks[task_id]['steps']['remove_background'] = False
            image_np, mask = remove_background(compressed_image_path)
            tasks[task_id]['steps']['remove_background'] = True

            tasks[task_id]['steps']['create_final_image'] = False
            final_image_path = create_final_image(image_np, mask)
            tasks[task_id]['steps']['create_final_image'] = True

            tasks[task_id]['steps']['prediction'] = False
            predicted_label = predict_image(final_image_path)
            tasks[task_id]['steps']['prediction'] = True

            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['result'] = predicted_label
        elif task_data['step'] == 'select':
            image_path = task_data['image_path']
            tasks[task_id]['steps']['compress_image'] = False
            compressed_image_path = compress_image(image_path)
            tasks[task_id]['steps']['compress_image'] = True

            tasks[task_id]['steps']['remove_background'] = False
            image_np, mask = remove_background(compressed_image_path)
            tasks[task_id]['steps']['remove_background'] = True

            tasks[task_id]['steps']['create_final_image'] = False
            final_image_path = create_final_image(image_np, mask)
            tasks[task_id]['steps']['create_final_image'] = True

            tasks[task_id]['steps']['prediction'] = False
            predicted_label = predict_image(final_image_path)
            tasks[task_id]['steps']['prediction'] = True

            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['result'] = predicted_label
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
        print(f"Error during processing and prediction: {e}")

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main page route"""
    if request.method == 'POST':
        step = request.form.get('step', None)
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        # Initialize task status
        tasks[task_id] = {
            'status': 'processing',
            'steps': {
                'compress_image': False,
                'remove_background': False,
                'create_final_image': False,
                'prediction': False
            },
            'result': None,
            'image_url': None,
            'error': None,
            'step': step  # Store the step for processing
        }

        if step == 'upload':  # Upload file processing
            file = request.files.get('file')
            if not file or not allowed_file(file.filename):
                flash("无效的文件或未选择文件")
                return redirect(request.url)

            extension = file.filename.rsplit('.', 1)[1].lower()
            filename = generate_random_filename(extension)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(upload_path)

            # Save original image URL for display on the result page
            original_image_url = url_for('uploaded_file', filename=filename)
            tasks[task_id]['image_url'] = original_image_url
            tasks[task_id]['upload_path'] = upload_path

            # Start background processing thread
            thread = threading.Thread(target=process_task, args=(task_id, tasks[task_id]))
            thread.start()

            # Redirect to the processing page
            return redirect(url_for('processing', task_id=task_id))

        elif step == 'select':  # Selected image processing
            selected_image = request.form.get('selected_image')
            if not selected_image:
                flash("未选择图片")
                return redirect(request.url)

            image_path = os.path.join(DATA_FOLDER, selected_image)
            if not os.path.exists(image_path):
                flash("所选图片不存在")
                return redirect(request.url)

            # Save original image URL for display on the result page
            original_image_url = url_for('data_file', filename=selected_image)
            tasks[task_id]['image_url'] = original_image_url
            tasks[task_id]['image_path'] = image_path

            # Start background processing thread
            thread = threading.Thread(target=process_task, args=(task_id, tasks[task_id]))
            thread.start()

            # Redirect to the processing page
            return redirect(url_for('processing', task_id=task_id))

    return render_template('index.html', image_rows=_get_photo_wall_images())

@app.route('/processing')
def processing():
    task_id = request.args.get('task_id')
    if not task_id:
        flash("未找到任务ID")
        return redirect(url_for('index'))
    return render_template('processing.html', task_id=task_id)

@app.route('/result')
def result():
    """Result page"""
    task_id = request.args.get('task_id')
    if not task_id:
        flash("未找到任务ID")
        return redirect(url_for('index'))
    task = tasks.get(task_id)
    if not task:
        flash("未找到任务信息")
        return redirect(url_for('index'))
    if task['status'] == 'completed':
        # 查找识别结果对应的鸟类ID
        bird_class_id = None
        if task['result'] and not class_mapping_df.empty:
            print(f"🔍 开始查找识别结果 '{task['result']}' 对应的ID")
            print(f"📊 class_mapping_df 包含 {len(class_mapping_df)} 条记录")
            
            # 在class_mapping中查找匹配的鸟类名称
            matching_birds = class_mapping_df[class_mapping_df['original_label'] == task['result']]
            
            if not matching_birds.empty:
                bird_class_id = matching_birds.iloc[0]['class']
                print(f"✅ 找到匹配！识别结果 '{task['result']}' 对应ID: {bird_class_id}")
            else:
                print(f"❌ 精确匹配失败，尝试部分匹配...")
                # 尝试部分匹配
                partial_matches = class_mapping_df[class_mapping_df['original_label'].str.contains(task['result'], na=False)]
                if not partial_matches.empty:
                    print(f"🔍 找到部分匹配的鸟类:")
                    for idx, row in partial_matches.iterrows():
                        print(f"   ID {row['class']}: '{row['original_label']}'")
                    # 使用第一个部分匹配的结果
                    bird_class_id = partial_matches.iloc[0]['class']
                    print(f"✅ 使用部分匹配结果，ID: {bird_class_id}")
                else:
                    print(f"❌ 未找到识别结果 '{task['result']}' 对应的ID（包括部分匹配）")
                    # 显示最相似的几个名称
                    print("🔍 数据库中相似的鸟类名称:")
                    for idx, row in class_mapping_df.iterrows():
                        if task['result'] in row['original_label'] or row['original_label'] in task['result']:
                            print(f"   ID {row['class']}: '{row['original_label']}'")
        else:
            if not task['result']:
                print("⚠️ 识别结果为空")
            if class_mapping_df.empty:
                print("⚠️ class_mapping_df 为空")
        
        return render_template('result.html', result=task['result'], image_url=task['image_url'], bird_class_id=bird_class_id)
    elif task['status'] == 'failed':
        flash(f"处理失败：{task.get('error', '未知错误')}")
        return redirect(url_for('index'))
    else:
        # Task not completed yet, redirect to processing page
        return redirect(url_for('processing', task_id=task_id))

# 新的/修改的鸟类详情页面路由 - 只使用本地数据
@app.route('/bird/<bird_class_id>')
def bird_detail(bird_class_id):
    bird_data = {
        'name': '未知鸟类',
        'class_id': bird_class_id,
        'description': None,
        'distribution': None,
        'data_source': 'local'  # 明确标识数据来源
    }
    
    try:
        numeric_class_id = int(bird_class_id)
        if not class_mapping_df.empty:
            bird_name_series = class_mapping_df[class_mapping_df['class'] == numeric_class_id]['original_label']
            if not bird_name_series.empty:
                bird_data['name'] = bird_name_series.iloc[0]
                print(f"🔍 加载鸟类 '{bird_data['name']}' (ID: {bird_class_id}) 的本地数据")
                
                # 只从本地加载数据
                local_data = load_local_bird_data(bird_class_id)
                
                if local_data:
                    bird_data['description'] = local_data['description']
                    bird_data['distribution'] = local_data['distribution']
                    
                    # 处理本地图片URL
                    if bird_data['description']:
                        bird_data['description'] = _update_local_image_urls(
                            bird_data['description'], bird_class_id)
                    if bird_data['distribution']:
                        bird_data['distribution'] = _update_local_image_urls(
                            bird_data['distribution'], bird_class_id)
                    
                    print(f"✅ 本地数据加载成功:")
                    print(f"   - 描述数据: {'有' if bird_data['description'] else '无'}")
                    print(f"   - 分布数据: {'有' if bird_data['distribution'] else '无'}")
                    
                else:
                    print(f"❌ 未找到ID {bird_class_id} 的本地数据")
                    flash(f"未找到鸟类 '{bird_data['name']}' 的详细信息。")
                
            else:
                flash(f"未在 class_mapping.csv 中找到ID为 {bird_class_id} 的鸟类名称。")
                print(f"❌ 未找到ID {bird_class_id} 对应的鸟类")
        else:
            flash(f"{BIRD_CLASS_MAPPING_CSV} 未加载，无法查找鸟类名称。")
            print(f"❌ {BIRD_CLASS_MAPPING_CSV} 文件未加载")
            
    except ValueError:
        flash("无效的鸟类ID格式。")
        print(f"❌ 无效的鸟类ID格式: {bird_class_id}")
    except Exception as e:
        print(f"❌ 处理鸟类详情页 /bird/{bird_class_id} 时出错: {e}")
        flash("获取鸟类详情时发生内部错误。")

    print(f"🎨 渲染模板，传递数据: {list(bird_data.keys())}")
    return render_template('bird_detail.html', bird_data=bird_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)