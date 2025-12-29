import os
import argparse
from src.data_loader import DataLoader
from src.pipeline import AutoTutorialPipeline

def main():
    # 1. 设置项目根目录 (获取 main.py 所在目录)
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # 2. 默认路径配置
    default_raw_dir = os.path.join(project_root, "data", "raw")
    default_processed_dir = os.path.join(project_root, "data", "processed")
    
    # 3. (可选) 支持命令行参数，方便以后灵活指定数据文件夹
    parser = argparse.ArgumentParser(description="AutoTutorial Generator")
    parser.add_argument("--raw_dir", type=str, default=default_raw_dir, help="Path to raw input data")
    parser.add_argument("--skip_loader", action="store_true", help="Skip Step 0 (Data Loading)")
    args = parser.parse_args()

    print(f"🌟 Starting Project from: {project_root}")

    # 4. 执行 Step 0: 数据清洗 (Data Loader)
    if not args.skip_loader:
        print("\n[Main] Running Data Loader...")
        print("\n[Main] 正在处理原始数据...")
        loader = DataLoader(args.raw_dir, default_processed_dir)
        loader.process()
    else:
        print("\n[Main] Skipping Data Loader (using existing cache)...")

    # 5. 执行 Pipeline (Steps 1-4)
    print("\n[Main] Initializing Pipeline...")
    print("\n[Main] 初始化文章生成中...")
    pipe = AutoTutorialPipeline(project_root)
    pipe.run_all()

if __name__ == "__main__":
    main()
