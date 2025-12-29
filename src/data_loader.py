import os
import json
import re
from src.utils import clean_input_args

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
        """解析 output.txt """
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
            return None, None

    def _parse_json_file(self, file_path):
        """
        [重构版] 内部方法：解析 function_call_info.json
        将 Agent 的工具流转换为【物理文件视角】(De-Agentify)
        同时提取【物理执行步骤】(Physics Steps)
        """
        simulated_files = {
            "STRU": {},
            "INPUT": {},
            "KPT": {},
            "physics_steps": []  # 提前初始化，保证 key 永远存在
        }

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 如果文件为空或不是字典，直接返回空结构
            if not data:
                return simulated_files

            sorted_keys = sorted(data.keys())
            
            for call_id in sorted_keys:
                info = data[call_id]
                tool_name = info.get('name')
                args = info.get('args', {})
                result = info.get('result', {})

                # === 1. 物理步骤翻译 (Human-Readable Steps) ===
                if tool_name in ['generate_structure', 'generate_bulk_structure']:
                    simulated_files["physics_steps"].append("Step: Build Initial Structure (建模)")
                elif tool_name == 'abacus_do_relax':
                    simulated_files["physics_steps"].append("Step: Geometry Optimization (Relaxation)")
                elif tool_name == 'abacus_cal_band':
                    simulated_files["physics_steps"].append("Step: Band Structure Calculation (Non-SCF)")
                elif tool_name == 'abacus_run':
                    # 细分 scf 还是 relax
                    calc_type = args.get('calculation', 'scf')
                    if 'relax' in str(calc_type):
                        simulated_files["physics_steps"].append("Step: Geometry Optimization (Relaxation)")
                    else:
                        simulated_files["physics_steps"].append("Step: Self-Consistent Field (SCF)")
                
                # === 2. 处理结构生成 (Mapping to STRU) ===
                if tool_name in ['generate_bulk_structure', 'generate_structure']:
                    stru_params = {
                        "element": args.get("element"),
                        "lattice_constant": args.get("a"),
                        "crystal_type": args.get("crystal_structure", "custom"),
                        "wyckoff": args.get("wyckoff_positions")
                    }
                    stru_params = {k: v for k, v in stru_params.items() if v is not None}
                    simulated_files["STRU"].update(stru_params)

                # === 3. 处理输入参数 (Mapping to INPUT/KPT) ===
                elif tool_name == 'abacus_prepare':
                    source_data = {}
                    if isinstance(result, dict) and result.get('input_content'):
                        source_data = result.get('input_content')
                    else:
                        source_data = args
                    
                    clean_data = clean_input_args(source_data, strict_defaults=True)
                    for k, v in clean_data.items():
                        if k in ['kspacing', 'kpath', 'k_points', 'gamma_only']:
                            simulated_files["KPT"][k] = v
                        else:
                            simulated_files["INPUT"][k] = v

                # === 4. 处理运行时改动 ===
                elif tool_name in ['abacus_do_relax', 'abacus_run', 'abacus_cal_band']:
                    clean_exec_args = clean_input_args(args, strict_defaults=True)
                    for k, v in clean_exec_args.items():
                        if k in ['kspacing', 'kpath']:
                            simulated_files["KPT"][k] = v
                        else:
                            simulated_files["INPUT"][k] = v
            
            return simulated_files

        except Exception as e:
            print(f"[Warn] Error parsing json {file_path}: {e}")
            # 出错时返回带空列表的结构，防止后续 KeyError
            return {"STRU": {}, "INPUT": {}, "KPT": {}, "physics_steps": []}


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
                        # [改动] 这里返回的是 File View (STRU/INPUT/KPT)
                        file_view = self._parse_json_file(json_path)
                        
                        record = {
                            "problem_id": base_name,
                            "file_path": root,
                            "extracted_data": {
                                "question": question,
                                "workflow_trace": file_view, # 字段名保持 workflow_trace 以兼容旧代码，但内容已变
                                "final_result_summary": result_summary
                            }
                        }
                        
                        final_report["records"].append(record)
                        count += 1
                        print(f"  [Parse] Found & Cleaned: {base_name}")
                    else:
                        print(f"  [Skip] Missing txt for {base_name} in {root}")

        final_report["total_records"] = count
        
        # 保存结果
        output_path = os.path.join(self.output_dir, "analysis_summary.json")
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(final_report, f, ensure_ascii=False, indent=4)
            print(f"\n[Success] Processed {count} records.\n[Output] Saved to: {output_path}")
            print(f"\n[成功] 已处理 {count} 条记录。\n[输出] 已保存到：{output_path}。")
        except Exception as e:
            print(f"[Error] Failed to save summary json: {e}")
            
        return final_report

if __name__ == "__main__":
    # 测试代码
    # 注意：这里如果单独运行，需要确保 import 路径正确。建议通过 main.py 运行。
    pass