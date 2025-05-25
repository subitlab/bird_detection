#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
鸟类数据预下载脚本
从鸟网批量下载所有鸟类的描述和分布信息及图片到本地
"""

import os
import pandas as pd
import requests
from pyquery import PyQuery as pq
import urllib.parse
import ssl
import warnings
import time
import json
from datetime import datetime
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

# 禁用SSL警告
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

class BirdDataDownloader:
    def __init__(self, class_mapping_csv="class_mapping.csv", output_dir="bird_data_local"):
        self.class_mapping_csv = class_mapping_csv
        self.output_dir = output_dir
        self.base_url = "https://www.birdnet.cn"
        self.req_url = 'https://www.birdnet.cn/atlas.php'
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 设置请求头
        self.headers = self._get_headers()
        
        # 统计信息
        self.stats = {
            'total_birds': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_images': 0,
            'downloaded_images': 0,
            'failed_images': 0,
            'start_time': None,
            'end_time': None
        }
        
        # 加载已处理的鸟类（支持断点续传）
        self.processed_birds_file = os.path.join(self.output_dir, 'processed_birds.json')
        self.processed_birds = self._load_processed_birds()
        
    def _get_headers(self):
        """获取请求头"""
        headers_str = '''
        Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7
        Accept-Language: zh-CN,zh;q=0.9
        Cache-Control: no-cache
        Connection: keep-alive
        Content-Type: application/x-www-form-urlencoded
        Origin: https://www.birdnet.cn
        Pragma: no-cache
        Referer: https://www.birdnet.cn/atlas.php?mod=show&action=atlaslist
        Sec-Fetch-Dest: document
        Sec-Fetch-Mode: navigate
        Sec-Fetch-Site: same-origin
        Upgrade-Insecure-Requests: 1
        User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36
        sec-ch-ua: "Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"
        sec-ch-ua-mobile: ?0
        sec-ch-ua-platform: "Windows"
        '''
        return dict([[y.strip() for y in x.strip().split(':', 1)] for x in headers_str.strip().split('\n') if x.strip()])
    
    def _load_processed_birds(self):
        """加载已处理的鸟类列表（支持断点续传）"""
        if os.path.exists(self.processed_birds_file):
            try:
                with open(self.processed_birds_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"📝 加载已处理记录: {len(data)} 个鸟类")
                    return set(data)
            except Exception as e:
                print(f"⚠️ 加载已处理记录失败: {e}")
        return set()
    
    def _save_processed_bird(self, bird_class_id):
        """保存已处理的鸟类"""
        self.processed_birds.add(bird_class_id)
        try:
            with open(self.processed_birds_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.processed_birds), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存已处理记录失败: {e}")
    
    def _encode_bird_name(self, bird_name_chinese):
        """编码鸟类名称用于搜索"""
        name = ''
        for one in bird_name_chinese:
            try:
                name += urllib.parse.quote(one, encoding='gbk')
            except:
                name += f'&#{ord(one)};'
        return name
    
    def _download_image(self, img_url, save_path, session):
        """下载单个图片"""
        try:
            if os.path.exists(save_path):
                print(f"    📋 图片已存在，跳过: {os.path.basename(save_path)}")
                return True
                
            response = session.get(img_url, headers=self.headers, verify=False, timeout=30)
            response.raise_for_status()
            
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            print(f"    ✅ 图片下载成功: {os.path.basename(save_path)}")
            self.stats['downloaded_images'] += 1
            return True
            
        except Exception as e:
            print(f"    ❌ 图片下载失败 {img_url}: {e}")
            self.stats['failed_images'] += 1
            return False
    
    def _process_html_and_download_images(self, html_content, bird_dir, content_type, session):
        """处理HTML内容并下载其中的图片"""
        if not html_content:
            return None
            
        content_doc = pq(html_content)
        img_count = 0
        
        # 创建图片目录
        images_dir = os.path.join(bird_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        for img in content_doc('img').items():
            src = img.attr('src')
            if not src:
                continue
                
            # 确保图片URL是绝对路径
            if not src.startswith(('http://', 'https://')):
                src = urllib.parse.urljoin(self.base_url, src)
            
            # 生成本地文件名
            img_hash = hashlib.md5(src.encode()).hexdigest()[:8]
            img_ext = os.path.splitext(urllib.parse.urlparse(src).path)[1] or '.jpg'
            local_filename = f"{content_type}_{img_hash}{img_ext}"
            local_path = os.path.join(images_dir, local_filename)
            
            # 下载图片
            if self._download_image(src, local_path, session):
                # 更新HTML中的图片路径为本地路径
                img.attr('src', f"images/{local_filename}")
                img_count += 1
                self.stats['total_images'] += 1
        
        if img_count > 0:
            print(f"    📸 {content_type}: 处理了 {img_count} 张图片")
        
        return content_doc.html()
    
    def _fetch_bird_details(self, bird_name_chinese, bird_class_id):
        """获取单个鸟类的详细信息"""
        print(f"\n🔍 开始处理: {bird_name_chinese} (ID: {bird_class_id})")
        
        # 检查是否已处理
        if str(bird_class_id) in self.processed_birds:
            print(f"    ⏭️ 已处理过，跳过")
            return True
        
        # 创建鸟类目录
        bird_dir = os.path.join(self.output_dir, str(bird_class_id))
        os.makedirs(bird_dir, exist_ok=True)
        
        # 保存鸟类基本信息
        bird_info = {
            'class_id': bird_class_id,
            'name': bird_name_chinese,
            'processed_time': datetime.now().isoformat(),
            'description_file': 'description.html',
            'distribution_file': 'distribution.html'
        }
        
        session = requests.Session()
        
        try:
            # 编码搜索词
            encoded_name = self._encode_bird_name(bird_name_chinese)
            
            params = {"mod": "show", "action": "atlaslist"}
            data = f'mod=show&action=atlaslist&searchType=1&all_name={encoded_name}&page=1'
            
            print(f"    🌐 搜索鸟类信息...")
            
            # 双重POST请求
            session.post(self.req_url, headers=self.headers, params=params, data=data, verify=False)
            response = session.post(self.req_url, headers=self.headers, params=params, data=data, 
                                  verify=False, cookies=session.cookies.get_dict())
            response.raise_for_status()
            
            # 解析搜索结果
            doc = pq(response.text)
            search_items = doc('.picturel ul li')
            
            detail_page_link = None
            
            # 精确匹配
            for item in search_items.items():
                a = item('p a')
                title = a.text()
                img_a = item.children('a')
                href = img_a.attr('href') if img_a else None
                
                if title == bird_name_chinese and href and href != 'javascript:void(0);':
                    detail_page_link = urllib.parse.urljoin(self.base_url, href)
                    break
            
            # 部分匹配作为备选
            if not detail_page_link:
                for item in search_items.items():
                    a = item('p a')
                    title = a.text()
                    img_a = item.children('a')
                    href = img_a.attr('href') if img_a else None
                    
                    if title and bird_name_chinese in title and href and href != 'javascript:void(0);':
                        detail_page_link = urllib.parse.urljoin(self.base_url, href)
                        break
            
            if not detail_page_link:
                print(f"    ❌ 未找到详情页链接")
                bird_info['error'] = '未找到详情页链接'
                # 仍然保存基本信息
                with open(os.path.join(bird_dir, 'info.json'), 'w', encoding='utf-8') as f:
                    json.dump(bird_info, f, ensure_ascii=False, indent=2)
                self._save_processed_bird(str(bird_class_id))
                return False
            
            print(f"    📖 访问详情页...")
            detail_response = session.get(detail_page_link, headers=self.headers, verify=False, timeout=15)
            detail_response.raise_for_status()
            
            detail_doc = pq(detail_response.text)
            
            # 提取描述信息
            print(f"    📝 提取描述信息...")
            description_html = None
            description_container = detail_doc('div.z.atlas_miaoshu')
            
            if description_container:
                hr0 = description_container('.hr0')
                if hr0.length > 0:
                    next_elements = hr0.next_all()
                    if next_elements:
                        description_html = ''.join([pq(el).outer_html() for el in next_elements])
                    else:
                        p_elements = description_container('p')
                        if p_elements:
                            description_html = ''.join([pq(el).outer_html() for el in p_elements])
                else:
                    description_html = description_container.html()
            
            # 提取分布信息
            print(f"    🗺️ 提取分布信息...")
            distribution_html = None
            distribution_container = detail_doc('div.y.atlas_fenbu')
            
            if distribution_container:
                hr0 = distribution_container('.hr0')
                if hr0.length > 0:
                    next_elements = hr0.next_all()
                    if next_elements:
                        distribution_html = ''.join([pq(el).outer_html() for el in next_elements])
                    else:
                        p_elements = distribution_container('p')
                        if p_elements:
                            distribution_html = ''.join([pq(el).outer_html() for el in p_elements])
                else:
                    distribution_html = distribution_container.html()
            
            # 处理描述HTML并下载图片
            if description_html:
                print(f"    📸 处理描述图片...")
                description_html_local = self._process_html_and_download_images(
                    description_html, bird_dir, 'desc', session)
                
                with open(os.path.join(bird_dir, 'description.html'), 'w', encoding='utf-8') as f:
                    f.write(description_html_local or '')
                bird_info['has_description'] = True
            else:
                bird_info['has_description'] = False
            
            # 处理分布HTML并下载图片
            if distribution_html:
                print(f"    🗺️ 处理分布图片...")
                distribution_html_local = self._process_html_and_download_images(
                    distribution_html, bird_dir, 'dist', session)
                
                with open(os.path.join(bird_dir, 'distribution.html'), 'w', encoding='utf-8') as f:
                    f.write(distribution_html_local or '')
                bird_info['has_distribution'] = True
            else:
                bird_info['has_distribution'] = False
            
            # 保存鸟类信息
            with open(os.path.join(bird_dir, 'info.json'), 'w', encoding='utf-8') as f:
                json.dump(bird_info, f, ensure_ascii=False, indent=2)
            
            print(f"    ✅ 处理完成")
            self.stats['successful_downloads'] += 1
            self._save_processed_bird(str(bird_class_id))
            
            return True
            
        except Exception as e:
            print(f"    ❌ 处理失败: {e}")
            bird_info['error'] = str(e)
            with open(os.path.join(bird_dir, 'info.json'), 'w', encoding='utf-8') as f:
                json.dump(bird_info, f, ensure_ascii=False, indent=2)
            self.stats['failed_downloads'] += 1
            self._save_processed_bird(str(bird_class_id))
            return False
        
        finally:
            # 添加延迟，避免对服务器造成过大压力
            time.sleep(2)
    
    def download_all_birds(self, max_workers=3):
        """下载所有鸟类数据"""
        print(f"🚀 开始批量下载鸟类数据...")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"🧵 并发数: {max_workers}")
        
        self.stats['start_time'] = datetime.now()
        
        # 读取鸟类映射
        try:
            class_mapping_df = pd.read_csv(self.class_mapping_csv)
            print(f"📊 从 {self.class_mapping_csv} 读取到 {len(class_mapping_df)} 种鸟类")
        except Exception as e:
            print(f"❌ 无法读取 {self.class_mapping_csv}: {e}")
            return
        
        self.stats['total_birds'] = len(class_mapping_df)
        
        # 筛选出尚未处理的鸟类
        birds_to_process = []
        for _, row in class_mapping_df.iterrows():
            bird_class_id = row['class']
            bird_name = row['original_label']
            if str(bird_class_id) not in self.processed_birds:
                birds_to_process.append((bird_name, bird_class_id))
        
        print(f"📋 需要处理的鸟类: {len(birds_to_process)} 种")
        print(f"⏭️ 已跳过: {len(self.processed_birds)} 种")
        
        if not birds_to_process:
            print(f"🎉 所有鸟类都已处理完成！")
            return
        
        # 使用线程池进行并发下载
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_bird = {
                executor.submit(self._fetch_bird_details, bird_name, bird_class_id): (bird_name, bird_class_id)
                for bird_name, bird_class_id in birds_to_process
            }
            
            # 等待任务完成
            for future in as_completed(future_to_bird):
                bird_name, bird_class_id = future_to_bird[future]
                try:
                    result = future.result()
                    # 结果已在_fetch_bird_details中处理
                except Exception as e:
                    print(f"❌ 线程处理 {bird_name} (ID: {bird_class_id}) 时发生异常: {e}")
                    self.stats['failed_downloads'] += 1
        
        self.stats['end_time'] = datetime.now()
        self._print_final_stats()
    
    def _print_final_stats(self):
        """打印最终统计信息"""
        print(f"\n" + "="*60)
        print(f"📊 下载任务完成！")
        print(f"⏰ 开始时间: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏰ 结束时间: {self.stats['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        duration = self.stats['end_time'] - self.stats['start_time']
        print(f"⏱️ 总耗时: {duration}")
        
        print(f"\n🐦 鸟类统计:")
        print(f"   总数: {self.stats['total_birds']}")
        print(f"   成功: {self.stats['successful_downloads']}")
        print(f"   失败: {self.stats['failed_downloads']}")
        print(f"   成功率: {self.stats['successful_downloads']/self.stats['total_birds']*100:.1f}%")
        
        print(f"\n📸 图片统计:")
        print(f"   总数: {self.stats['total_images']}")
        print(f"   成功: {self.stats['downloaded_images']}")
        print(f"   失败: {self.stats['failed_images']}")
        if self.stats['total_images'] > 0:
            print(f"   成功率: {self.stats['downloaded_images']/self.stats['total_images']*100:.1f}%")
        
        print(f"\n📁 数据保存在: {os.path.abspath(self.output_dir)}")
        print(f"="*60)
    
    def check_local_data(self):
        """检查本地数据完整性"""
        print(f"🔍 检查本地数据完整性...")
        
        bird_dirs = [d for d in os.listdir(self.output_dir) 
                    if os.path.isdir(os.path.join(self.output_dir, d)) and d.isdigit()]
        
        complete_birds = 0
        incomplete_birds = 0
        
        for bird_dir in bird_dirs:
            bird_path = os.path.join(self.output_dir, bird_dir)
            info_file = os.path.join(bird_path, 'info.json')
            
            if os.path.exists(info_file):
                try:
                    with open(info_file, 'r', encoding='utf-8') as f:
                        info = json.load(f)
                    
                    has_desc = os.path.exists(os.path.join(bird_path, 'description.html'))
                    has_dist = os.path.exists(os.path.join(bird_path, 'distribution.html'))
                    
                    if has_desc or has_dist:
                        complete_birds += 1
                    else:
                        incomplete_birds += 1
                        print(f"  ⚠️ 不完整: {bird_dir} - {info.get('name', '未知')}")
                        
                except Exception as e:
                    incomplete_birds += 1
                    print(f"  ❌ 信息文件损坏: {bird_dir}")
            else:
                incomplete_birds += 1
                print(f"  ❌ 缺少信息文件: {bird_dir}")
        
        print(f"\n📊 本地数据统计:")
        print(f"   完整的鸟类数据: {complete_birds}")
        print(f"   不完整的鸟类数据: {incomplete_birds}")
        print(f"   总计: {len(bird_dirs)}")

def main():
    """主函数"""
    print("🐦 鸟类数据预下载工具")
    print("=" * 40)
    
    # 创建下载器
    downloader = BirdDataDownloader()
    
    # 检查现有数据
    if os.path.exists(downloader.output_dir) and os.listdir(downloader.output_dir):
        print("\n📁 检测到现有数据...")
        downloader.check_local_data()
        
        choice = input("\n是否继续下载剩余数据？(y/n): ").lower().strip()
        if choice != 'y':
            print("👋 退出程序")
            return
    
    # 开始下载
    try:
        # 设置并发数，建议不要太高以免对服务器造成压力
        max_workers = 3
        print(f"\n⚠️ 注意：下载过程可能需要较长时间，请耐心等待...")
        print(f"💡 提示：程序支持断点续传，可以随时中断后重新运行")
        
        downloader.download_all_birds(max_workers=max_workers)
        
    except KeyboardInterrupt:
        print(f"\n⏹️ 用户中断下载")
        print(f"💡 下次运行时将从中断处继续下载")
    except Exception as e:
        print(f"\n❌ 下载过程中发生错误: {e}")
    
    print(f"\n👋 程序结束")

if __name__ == "__main__":
    main()
