#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pandas as pd
from image_utils import compress_image, remove_background, create_final_image
import cv2
import numpy as np
from PIL import Image
import json
from datetime import datetime

class ImageValidator:
    def __init__(self, data_folder='static/', csv_file='all_data.csv'):
        self.data_folder = data_folder
        self.csv_file = csv_file
        self.results = {
            'valid_images': [],
            'invalid_images': [],
            'error_details': {}
        }
    
    def validate_single_image(self, image_path, filepath):
        """验证单个图片是否可以正常处理"""
        try:
            print(f"正在验证: {filepath}")
            
            # 步骤1: 压缩图片
            compressed_path = compress_image(image_path)
            
            # 步骤2: 移除背景
            image_np, mask = remove_background(compressed_path)
            
            # 步骤3: 检查主体数量（这里是关键检查点）
            subject_mask = (mask > 0).astype(np.uint8)
            num_labels, labels_im = cv2.connectedComponents(subject_mask)
            num_subjects = num_labels - 1  # 减去背景
            
            if num_subjects != 1:
                error_msg = f"未检测到主体或检测到多个主体（{num_subjects} 个主体）"
                print(f"  ❌ {error_msg}")
                self.results['invalid_images'].append(filepath)
                self.results['error_details'][filepath] = {
                    'error': error_msg,
                    'subject_count': num_subjects,
                    'step': 'subject_detection'
                }
                return False
            
            # 步骤4: 检查主体尺寸
            coords = cv2.findNonZero(subject_mask)
            if coords is None:
                error_msg = "未找到主体坐标"
                print(f"  ❌ {error_msg}")
                self.results['invalid_images'].append(filepath)
                self.results['error_details'][filepath] = {
                    'error': error_msg,
                    'subject_count': num_subjects,
                    'step': 'coordinate_detection'
                }
                return False
                
            x, y, w, h = cv2.boundingRect(coords)
            if w < 64 or h < 64:
                error_msg = f"主体尺寸过小（{w}x{h}）"
                print(f"  ❌ {error_msg}")
                self.results['invalid_images'].append(filepath)
                self.results['error_details'][filepath] = {
                    'error': error_msg,
                    'subject_count': num_subjects,
                    'dimensions': f"{w}x{h}",
                    'step': 'size_check'
                }
                return False
            
            # 如果到这里，说明图片可以正常处理
            print(f"  ✅ 验证通过")
            self.results['valid_images'].append(filepath)
            
            # 清理临时文件
            if os.path.exists(compressed_path):
                os.remove(compressed_path)
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ 处理异常: {error_msg}")
            self.results['invalid_images'].append(filepath)
            self.results['error_details'][filepath] = {
                'error': error_msg,
                'step': 'exception'
            }
            return False
    
    def validate_all_images(self, dataset_filter='test'):
        """验证所有图片"""
        print(f"🔍 开始验证图片，数据集筛选: {dataset_filter}")
        
        # 读取数据文件
        try:
            df = pd.read_csv(self.csv_file)
            print(f"📊 从 {self.csv_file} 读取到 {len(df)} 条记录")
        except Exception as e:
            print(f"❌ 无法读取CSV文件: {e}")
            return
        
        # 筛选测试集数据
        if dataset_filter:
            test_images = df[df['data set'] == dataset_filter][['filepaths', 'class']].values.tolist()
            print(f"📋 筛选出 {len(test_images)} 张 {dataset_filter} 集图片")
        else:
            test_images = df[['filepaths', 'class']].values.tolist()
            print(f"📋 处理所有 {len(test_images)} 张图片")
        
        # 验证每张图片
        total_count = len(test_images)
        valid_count = 0
        invalid_count = 0
        
        for i, (filepath, bird_class) in enumerate(test_images):
            print(f"\n[{i+1}/{total_count}] ", end="")
            
            full_path = os.path.join(self.data_folder, filepath)
            if not os.path.exists(full_path):
                print(f"文件不存在: {filepath}")
                self.results['invalid_images'].append(filepath)
                self.results['error_details'][filepath] = {
                    'error': '文件不存在',
                    'step': 'file_check'
                }
                invalid_count += 1
                continue
            
            if self.validate_single_image(full_path, filepath):
                valid_count += 1
            else:
                invalid_count += 1
        
        # 输出统计结果
        print(f"\n" + "="*50)
        print(f"📊 验证完成！")
        print(f"✅ 有效图片: {valid_count} 张")
        print(f"❌ 无效图片: {invalid_count} 张")
        print(f"📈 有效率: {valid_count/total_count*100:.1f}%")
        
        return self.results
    
    def save_results(self, output_file='image_validation_results.json'):
        """保存验证结果到文件"""
        result_data = {
            'timestamp': datetime.now().isoformat(),
            'total_images': len(self.results['valid_images']) + len(self.results['invalid_images']),
            'valid_count': len(self.results['valid_images']),
            'invalid_count': len(self.results['invalid_images']),
            'valid_images': self.results['valid_images'],
            'invalid_images': self.results['invalid_images'],
            'error_details': self.results['error_details']
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 结果已保存到: {output_file}")
        
        # 同时保存无效图片列表（用于后续筛选）
        invalid_list_file = 'invalid_images_list.txt'
        with open(invalid_list_file, 'w', encoding='utf-8') as f:
            for filepath in self.results['invalid_images']:
                f.write(f"{filepath}\n")
        
        print(f"📝 无效图片列表已保存到: {invalid_list_file}")
    
    def generate_report(self):
        """生成详细报告"""
        print(f"\n" + "="*60)
        print(f"📋 详细错误报告")
        print(f"="*60)
        
        # 按错误类型统计
        error_types = {}
        for filepath, details in self.results['error_details'].items():
            error = details['error']
            if error not in error_types:
                error_types[error] = []
            error_types[error].append(filepath)
        
        for error_type, files in error_types.items():
            print(f"\n🔸 {error_type}: {len(files)} 张图片")
            for filepath in files[:5]:  # 只显示前5个例子
                print(f"   - {filepath}")
            if len(files) > 5:
                print(f"   ... 还有 {len(files) - 5} 张图片")

def main():
    print("🎯 开始图片验证任务")
    
    validator = ImageValidator()
    
    # 验证所有图片
    results = validator.validate_all_images(dataset_filter='test')
    
    # 保存结果
    validator.save_results()
    
    # 生成报告
    validator.generate_report()
    
    print(f"\n✅ 验证任务完成！")
    print(f"💡 提示：您可以使用生成的 'invalid_images_list.txt' 文件来过滤照片墙中的问题图片")

if __name__ == "__main__":
    main() 