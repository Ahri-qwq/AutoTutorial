import os
import json
from src.data_loader import DataLoader
from src.llm_client import LLMClient
from src.utils import split_markdown_by_tag, extract_mapped_case_ids, get_record_by_id


class AutoTutorialPipeline:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.config_path = os.path.join(root_dir, "config.yaml")
        self.prompts_dir = os.path.join(root_dir, "prompts")
        self.processed_dir = os.path.join(root_dir, "data", "processed")
        
        # 初始化组件
        self.llm = LLMClient(self.config_path)
        
    def load_prompt(self, filename):
        path = os.path.join(self.prompts_dir, filename)
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def run_step1(self):
        print("\n=== Running Step 1: Knowledge Enrichment ===")
        
        # 1. 确保有 analysis_summary.json
        summary_path = os.path.join(self.processed_dir, "analysis_summary.json")
        if not os.path.exists(summary_path):
            print("[Error] analysis_summary.json not found. Run Data Loader first!")
            return

        # 2. 读取原始数据
        with open(summary_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            
        # 3. 准备 Prompt
        prompt_tmpl = self.load_prompt("step1_enrich.txt")
        # 将整个 raw_data 塞进去 (如果太长可以只塞 records 列表)
        final_prompt = prompt_tmpl.replace("[INSERT_DATA]", json.dumps(raw_data['records'], indent=2))
        
        # 4. 调用 LLM
        print("[LLM] Sending request... (This may take a while)")
        response = self.llm.chat(final_prompt)
        
        # 5. 清洗并保存结果 (去除可能存在的 ```
        cleaned_response = response.replace("```json", "").replace("```", "")
        
        output_path = os.path.join(self.processed_dir, "step1_result.json")
        try:
            # 验证一下是否是合法的 JSON
            json_obj = json.loads(cleaned_response)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_obj, f, indent=4)
            print(f"[Success] Step 1 complete. Saved to {output_path}")
        except json.JSONDecodeError:
            print("[Error] LLM did not return valid JSON. Saving raw text instead.")
            with open(output_path + ".txt", 'w', encoding='utf-8') as f:
                f.write(cleaned_response)
    
    def run_step2(self):
        print("\n=== Running Step 2: Adaptive Outline Generation ===")
        
        # 1. 读取 Step 1 的结果
        input_path = os.path.join(self.processed_dir, "step1_result.json")
        if not os.path.exists(input_path):
            print("[Error] step1_result.json not found. Run Step 1 first!")
            return

        with open(input_path, 'r', encoding='utf-8') as f:
            step1_data = json.load(f)
            
        # 2. 准备 Prompt
        prompt_tmpl = self.load_prompt("step2_outline.txt")
        # 将 JSON 数据插入 Prompt
        final_prompt = prompt_tmpl.replace("[INSERT_DATA]", json.dumps(step1_data, indent=2))
        
        # 3. 调用 LLM
        print("[LLM] Generating Outline... (Thinking hard)")
        response = self.llm.chat(final_prompt)
        
        # 4. 保存 Markdown 结果
        output_path = os.path.join(self.processed_dir, "step2_outline.md")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(response)
            
        print(f"[Success] Step 2 complete. Saved to {output_path}")
        
        # 简单验证一下标记是否存在，防止 Step 3 报错
        if "<!-- CHAPTER_START -->" not in response:
            print("[Warn] ⚠️ Generated outline is missing '<!-- CHAPTER_START -->' tags. Step 3 may fail.")


    def run_step3(self):
        print("\n=== Running Step 3: Drafting Chapters ===")
        
        # 1. 加载资源
        outline_path = os.path.join(self.processed_dir, "step2_outline.md")
        raw_data_path = os.path.join(self.processed_dir, "analysis_summary.json")
        
        if not os.path.exists(outline_path) or not os.path.exists(raw_data_path):
            print("[Error] Missing outline or raw data. Run previous steps first!")
            return

        with open(outline_path, 'r', encoding='utf-8') as f:
            outline_text = f.read()
        
        with open(raw_data_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            records = raw_data.get('records', [])

        # 2. 切分大纲
        # 我们假设大纲结构是：[META] [CHAPTER_1] [CHAPTER_2] ... [APPENDIX]
        # 使用 <!-- CHAPTER_START --> 切分
        # 注意：split 出来的第一部分通常是 META，后面才是正文章节
        # 我们需要更精细的逻辑：
        
        # 策略：先用 CHAPTER_START 切，第0部分包含META，最后一部分可能包含APPENDIX
        # 为了稳健，我们简单地处理所有包含 "Mapped Case ID" 的块作为正文章节
        
        chunks = split_markdown_by_tag(outline_text, "<!-- CHAPTER_START -->")
        
        drafts = []
        chapter_idx = 0
        
        # 加载 Prompt 模板
        prompt_tmpl = self.load_prompt("step3_drafting.txt")

        for chunk in chunks:
            # 简单判断：如果这个块里没有 "Mapped Case ID"，可能它只是前言或附录，跳过正文生成逻辑
            case_ids = extract_mapped_case_ids(chunk)
            
            if not case_ids:
                print(f"[Skip] Chunk {chapter_idx} has no cases (likely Preface or Appendix).")
                continue
            
            chapter_idx += 1
            # 提取标题 (第一行)
            title = chunk.strip().split('\n')[0]
            print(f"[Drafting] Chapter {chapter_idx}: {title} (Cases: {case_ids})")
            
            # 3. 准备 Evidence 数据
            evidence_list = []
            for pid in case_ids:
                rec = get_record_by_id(records, pid)
                if rec:
                    evidence_list.append(rec)
            
            evidence_json = json.dumps(evidence_list, indent=2)
            
            # 4. 组装 Prompt
            final_prompt = prompt_tmpl.replace("{{FULL_BOOK_OUTLINE}}", outline_text) \
                                      .replace("{{CHAPTER_TITLE}}", title) \
                                      .replace("{{CHAPTER_OUTLINE}}", chunk) \
                                      .replace("{{EVIDENCE_JSON}}", evidence_json)
            
            # 5. 调用 LLM
            response = self.llm.chat(final_prompt)
            drafts.append(response)
            
            # 实时保存每一章
            with open(os.path.join(self.processed_dir, f"draft_chapter_{chapter_idx}.md"), 'w', encoding='utf-8') as f:
                f.write(response)
                
        print(f"[Success] Generated {len(drafts)} chapters.")
        return drafts

    def run_step4(self):
        print("\n=== Running Step 4: Final Assembly & Polish ===")
        
        # 1. 收集所有 draft_chapter_*.md
        draft_files = []
        # 遍历 processed 目录，找到所有 draft_chapter_X.md 并按数字排序
        for f in os.listdir(self.processed_dir):
            if f.startswith("draft_chapter_") and f.endswith(".md"):
                draft_files.append(f)
        
        # 按章节号排序 (draft_chapter_1, draft_chapter_2...)
        # 这里假设文件名格式固定，提取数字进行排序
        draft_files.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))
        
        if not draft_files:
            print("[Error] No draft chapters found. Run Step 3 first!")
            return

        # 2. 读取章节内容并生成摘要
        full_chapters_content = []
        summaries = []
        
        for f_name in draft_files:
            path = os.path.join(self.processed_dir, f_name)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                full_chapters_content.append(content)
                # 截取前 500 字符作为摘要喂给 LLM，节省 Token
                summaries.append(f"--- {f_name} ---\n{content[:800]}...\n")
        
        # 3. 调用 LLM 生成 Meta Info (标题, 前言, 附录)
        prompt_tmpl = self.load_prompt("step4_assembly.txt")
        final_prompt = prompt_tmpl.replace("{{CHAPTER_SUMMARIES}}", "\n".join(summaries))
        
        print("[LLM] Finalizing book metadata...")
        response = self.llm.chat(final_prompt)
        
        # 4. 解析 JSON 输出
        try:
            # 清洗可能存在的 markdown 标记
            clean_json = response.replace("``````", "").strip()
            meta_data = json.loads(clean_json)
            
            title = meta_data.get("book_title", "ABACUS Tutorial")
            preface = meta_data.get("preface_markdown", "")
            appendix = meta_data.get("appendix_markdown", "")
            
        except json.JSONDecodeError:
            print("[Error] LLM failed to return valid JSON in Step 4. Using fallback.")
            title = "ABACUS 实战指南 (Auto-Generated)"
            preface = "## 前言\n(生成失败，请手动补充)"
            appendix = "## 附录\n(生成失败，请手动补充)"
        
        # 5. 物理拼接全书
        final_book_content = f"# {title}\n\n"
        final_book_content += f"{preface}\n\n"
        final_book_content += "---\n\n"
        
        # 插入正文
        for chapter_text in full_chapters_content:
            final_book_content += f"{chapter_text}\n\n---\n\n"
            
        # 插入附录
        final_book_content += f"{appendix}\n"
        
        # 6. 保存最终文件
        output_dir = os.path.join(self.root_dir, "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        final_path = os.path.join(output_dir, "ABACUS_Tutorial_Final.md")
        with open(final_path, 'w', encoding='utf-8') as f:
            f.write(final_book_content)
            
        print(f"[Success] Book assembled! Saved to: {final_path}")

    def run_all(self):
        """
        一键运行全流程：Step 1 -> Step 4
        """
        print("🚀 Starting AutoTutorial Pipeline...")
        
        # Step 0: 数据加载 (可选，如果确认数据已就绪可跳过，但建议加上以防万一)
        # 注意：需要在头部 import DataLoader
        print("\n[Step 0] Checking/Loading Raw Data...")
        # 假设 raw_data 路径在 config 中配置了，或者硬编码
        # 这里为了演示，我们假设 data/processed/analysis_summary.json 已经由 data_loader.py 生成好了
        # 如果想集成得更紧密，可以在这里实例化 DataLoader 并调用 process()
        summary_path = os.path.join(self.processed_dir, "analysis_summary.json")
        if not os.path.exists(summary_path):
             print("[Error] Raw data summary not found! Please run 'data_loader.py' first.")
             return

        # Step 1: 知识图谱构建
        self.run_step1()
        
        # Step 2: 大纲生成
        self.run_step2()
        
        # Step 3: 正文撰写 (最耗时)
        drafts = self.run_step3()
        if not drafts:
            print("[Error] Step 3 failed to generate drafts. Stopping.")
            return

        # Step 4: 组装终稿
        self.run_step4()
        
        print("\n🎉 Pipeline Finished Successfully! Check the 'output' folder.")


if __name__ == "__main__":
    pipe = AutoTutorialPipeline(r"C:\MyCode\AutoTutorial")
    #pipe.run_step1()
    #pipe.run_step2()
    #pipe.run_step3()
    #pipe.run_step4()

    # 初始化 Pipeline
    # 使用您的项目根目录路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pipe = AutoTutorialPipeline(project_root)
    
    # 一键启动！
    pipe.run_all()

