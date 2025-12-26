import os
import sys
from openai import OpenAI
import yaml

class LLMClient:
    def __init__(self, config_path=None):
        # 自动定位 config.yaml (假设在项目根目录)
        if config_path is None:
            # 获取当前文件 (src/llm_client.py) 的上级目录 (src) 的上级目录 (AutoTutorial)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.yaml")

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found at: {config_path}")

        # 读取配置
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            api_key = self.config['llm']['api_key']
            base_url = self.config['llm']['base_url']
            self.model = self.config['llm']['model_name']
            
            print(f"[Init] LLM Client connecting to: {self.model}")
            
            # 初始化 OpenAI 客户端
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            
        except Exception as e:
            print(f"[Error] Failed to init LLM Client: {e}")
            raise

    def chat(self, prompt, system_role="You are a helpful assistant."):
        """
        发送 Prompt 并获取回复
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_role},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7 # 根据需要调整创造性
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[Error] LLM Call Failed: {e}")
            return ""

# 测试
if __name__ == "__main__":
    try:
        client = LLMClient()
        print("Testing connection to Qwen-Max...")
        reply = client.chat("你是谁？请简短回答。")
        print(f"Reply: {reply}")
    except Exception as e:
        print(f"Test Failed: {e}")
