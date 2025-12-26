import os
import json
import re

class DataLoader:
    def __init__(self, raw_data_dir, output_dir):
        """
        初始化数据加载器
        :param raw_data_dir: 原始数据根目录 (e.g., data/raw)
        :param output_dir: 处理后数据保存路径 (e.g., data/processed)
        """
        self.raw_data_dir = raw_data_dir
        self.output_dir = output_dir
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _parse_txt_file(self, file_path):
        """内部方法：解析 output.txt"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 1. 提取用户问题
            question = None
            match_q = re.search(r"\*\* User says:.*?{'text':\s*'(.*?)'}", content, re.DOTALL)
            if match_q:
                question = match_q.group(1)
            else:
                match_q_simple = re.search(r"'text': '([^']*)'", content)
                question = match_q_simple.group(1) if match_q_simple else "Question not found"
                
            # 2. 提取结果摘要
            result = None
            if "## **Results Summary:**" in content:
                temp = content.split("## **Results Summary:**")[1]
                result = temp.split("** abacus_agent")[0].strip()
            else:
                result = "Summary not found in text output"
                
            return question, result
        except Exception as e:
            # print(f"[Warn] Error parsing txt {file_path}: {e}")
            return None, None

    def _parse_json_file(self, file_path):
        """内部方法：解析 function_call_info.json"""
        workflow_steps = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            sorted_keys = sorted(data.keys())
            
            for call_id in sorted_keys:
                info = data[call_id]
                tool_name = info.get('name')
                args = info.get('args', {})
                
                step_info = {
                    "step_id": call_id,
                    "tool": tool_name,
                    "input_args": args,
                    "method_details": {}
                }
                
                # 提取计算参数
                if tool_name == 'abacus_prepare' and 'result' in info:
                    inp = info['result'].get('input_content', {})
                    if inp:
                        step_info["method_details"] = {
                            'calculation_type': inp.get('calculation'),
                            'basis_type': inp.get('basis_type'),
                            'ecutwfc': inp.get('ecutwfc'),
                            'ks_solver': inp.get('ks_solver'),
                            'smearing_method': inp.get('smearing_method'),
                            'nspin': inp.get('nspin')
                        }
                
                workflow_steps.append(step_info)
            return workflow_steps
        except Exception as e:
            print(f"[Warn] Error parsing json {file_path}: {e}")
            return []

    def process(self):
        """
        核心方法：递归遍历 raw 目录，查找并解析文件
        """
        final_report = {
            "root_directory": self.raw_data_dir,
            "total_records": 0,
            "records": []
        }
        
        print(f"[Info] Scanning {self.raw_data_dir} recursively...")

        count = 0
        # === 核心修改：使用 os.walk 递归遍历 ===
        for root, dirs, files in os.walk(self.raw_data_dir):
            for filename in files:
                # 找到目标 JSON 文件
                if filename.endswith("_function_call_info.json"):
                    json_path = os.path.join(root, filename)
                    
                    # 推导同目录下的 txt 文件名
                    base_name = filename.replace("_function_call_info.json", "")
                    txt_filename = f"{base_name}_output.txt"
                    txt_path = os.path.join(root, txt_filename)
                    
                    if os.path.exists(txt_path):
                        # 解析成对文件
                        question, result_summary = self._parse_txt_file(txt_path)
                        workflow = self._parse_json_file(json_path)
                        
                        record = {
                            "problem_id": base_name,
                            "file_path": root,
                            "extracted_data": {
                                "question": question,
                                "workflow_trace": workflow,
                                "final_result_summary": result_summary
                            }
                        }
                        
                        final_report["records"].append(record)
                        count += 1
                        print(f"  [Parse] Found: {base_name}")
                    else:
                        print(f"  [Skip] Missing txt for {base_name} in {root}")

        final_report["total_records"] = count
        
        # 保存结果
        output_path = os.path.join(self.output_dir, "analysis_summary.json")
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(final_report, f, ensure_ascii=False, indent=4)
            print(f"\n[Success] Processed {count} records.\n[Output] Saved to: {output_path}")
        except Exception as e:
            print(f"[Error] Failed to save summary json: {e}")
            
        return final_report

if __name__ == "__main__":
    # 这里的路径仅供测试，请根据实际情况调整
    RAW_DIR = r"C:\MyCode\AutoTutorial\data\raw"
    PROCESSED_DIR = r"C:\MyCode\AutoTutorial\data\processed"
    
    loader = DataLoader(RAW_DIR, PROCESSED_DIR)
    loader.process()
