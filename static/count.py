import os
import matplotlib.pyplot as plt

def count_files_in_subfolders(directory):
    file_counts = []
    
    for root, dirs, files in os.walk(directory):
        # Skip the root folder itself
        if root == directory:
            continue
        
        file_counts.append(len(files))
    
    return file_counts

def plot_file_counts(file_counts):
    plt.figure(figsize=(10, 6))
    plt.bar(range(len(file_counts)), file_counts)
    plt.ylabel("Number of Files")
    plt.title("File Count in Subfolders")
    plt.xticks([])  # 隐藏横轴的刻度和标签
    plt.tight_layout()
    plt.show()

# 替换为你要统计的目录路径
directory_path = "data"

file_counts = count_files_in_subfolders(directory_path)
plot_file_counts(file_counts)