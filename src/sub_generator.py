# src/sub_generator.py
from pathlib import Path
from typing import List
from . import config

class SubGenerator:
    """
    专门负责：基于优化结果，批量生成子任务 (Gas, Solv, SP)
    """
    def __init__(self):
        self.template_dir = config.TEMPLATE_DIR

    def generate_all(self, base_name: str, charge: int, mult: int, coords: str) -> List[Path]:
        """
        主入口：生成 gas, solv, sp 三个输入文件
        返回生成的文件路径列表
        """
        generated_files = []
        tasks = ["gas", "solv", "sp"]
        
        for task in tasks:
            # 1. 找对应模板
            template_path = None
            ext = None
            for e in config.VALID_EXTENSIONS:
                p = self.template_dir / f"{task}{e}"
                if p.exists():
                    template_path = p
                    ext = e
                    break
            
            # 如果某个模板不存在(比如不想算solv)，记录警告但不中断其他
            if not template_path:
                print(f"  ⚠️ Warning: Template for '{task}' not found. Skipping.")
                continue

            # 2. 准备输出
            output_dir = config.DIRS[task]
            output_dir.mkdir(parents=True, exist_ok=True)
            
            new_filename = f"{base_name}_{task}"
            output_file = output_dir / f"{new_filename}{ext}"
            
            # 3. 替换内容
            with open(template_path, 'r', encoding='utf-8') as t:
                content = t.read()
            
            new_content = content.replace("[NAME]", new_filename)
            new_content = new_content.replace("[Charge]", str(charge))
            new_content = new_content.replace("[Multiplicity]", str(mult))
            new_content = new_content.replace("[GEOMETRY]", coords)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            generated_files.append(output_file)
            
        return generated_files