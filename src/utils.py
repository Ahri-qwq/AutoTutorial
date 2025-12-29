
import re
import json

# === 1. 系统噪音黑名单 (System Noise) ===
# 这些参数是 Agent 框架或脚本运行时的中间变量，对用户无物理意义，必须无条件剔除。
# 泛用性设计：包含常见的路径、ID、格式字段。
SYSTEM_NOISE = {
    "abacus_inputs_dir", 
    "stru_file", 
    "stru_type", 
    "job_type",
    "files",
    "file_format",
    "step_id",      # Agent 步骤 ID
    "tool_name",    # 工具名
    "work_dir",     # 工作目录
    "out_dir",      # 输出目录
    "save_path"     # 保存路径
}

# === 2. ABACUS 默认参数白名单 (Default Physics Params) ===
# 这些是 ABACUS 的默认值 (K_default)。
# 如果 input_args 中的值与此相同，说明 Agent 只是显式打印了默认值，应该剔除。
# 仅保留与默认值不同的参数 (K_diff)，这才是教程的讲解重点。
ABACUS_DEFAULTS = {
    "suffix": "ABACUS",
    "calculation": "scf",     # 默认计算类型
    "basis_type": "lcao",     # 默认基组
    "symmetry": 1,            # 默认开启对称性
    "nspin": 1,               # 默认无自旋
    "knorm": 0,               # 默认不归一化 K 点
    "cal_force": 0,           # 默认不算法
    "cal_stress": 0,          # 默认不算应力
    "esolver_type": "ksdft",  # 默认求解器
    "smearing_method": "gauss", # 默认展宽 (除非是 mp, mv)
    "mixing_type": "broyden", # 默认混合方法
    "out_chg": 0,             # 默认不输出电荷
    "out_bandgap": 0,         # 默认不输出带隙
    "deepks_out_labels": 0,
    "out_stru": 0,
    "start_charge": "atomic"  # 默认初始电荷
}

def clean_input_args(input_args, strict_defaults=True):
    """
    清洗 input_args 字典 (核心清洗逻辑)
    
    Args:
        input_args (dict): 原始参数字典
        strict_defaults (bool): 是否严格过滤默认值 (K_diff 模式)。默认 True。
        
    Returns:
        dict: 清洗后的参数字典 (K_diff)
    """
    if not isinstance(input_args, dict):
        return input_args
        
    clean_args = {}
    
    for k, v in input_args.items():
        # 1. 强力剔除系统噪音
        if k in SYSTEM_NOISE:
            continue
            
        # 2. 预处理：布尔值转 ABACUS 整数格式 (True->1, False->0)
        # 这也是为了泛用性，防止 Agent 输出 True 而 ABACUS 需要 1
        if isinstance(v, bool):
            v = 1 if v else 0
            
        # 3. 差分过滤 (Differential Filtering)
        if strict_defaults and k in ABACUS_DEFAULTS:
            default_val = ABACUS_DEFAULTS[k]
            # 如果值等于默认值，且不是某些关键参数(如 calculation)，则剔除
            # 注意：这里我们做简单的相等判断。如果类型不同(如 "1" vs 1)，可能需要更复杂的转换
            if str(v) == str(default_val): 
                continue

        clean_args[k] = v
        
    return clean_args




def split_markdown_by_tag(content, tag):
    """
    根据 HTML 注释标记切分 Markdown
    返回切分后的文本列表（不包含空块）
    """
    # 使用正则切分，保留分隔符以便后续检查（可选，这里简化处理直接切分）
    parts = content.split(tag)
    return [p.strip() for p in parts if p.strip()]

def extract_mapped_case_ids(chapter_content):
    """
    从章节 Markdown 中提取所有 `Mapped Case ID: problem_X`
    """
    # 匹配 Mapped Case ID: `problem_1` 或 Mapped Case ID: problem_1
    pattern = r"Mapped Case ID.*?(problem_\d+)"
    ids = re.findall(pattern, chapter_content, re.IGNORECASE)
    return list(set(ids)) # 去重

def get_record_by_id(raw_data_records, problem_id):
    """
    从完整的 raw_data 列表中根据 id 查找特定记录
    """
    for record in raw_data_records:
        if record.get('problem_id') == problem_id:
            # 为了节省 Token，只提取关键字段
            return {
                "id": problem_id,
                "question": record['extracted_data'].get('question'),
                "workflow": record['extracted_data'].get('workflow_trace'),
                "result": record['extracted_data'].get('final_result_summary')
            }
    return None
