import re
import json

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
