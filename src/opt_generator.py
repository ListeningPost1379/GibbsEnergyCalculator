# src/opt_generator.py
import re
from pathlib import Path
from typing import Tuple
from . import config

class OptGenerator:
    """
    专门负责：从 XYZ 文件生成 Optimization 输入文件
    """
    def __init__(self):
        self.template_dir = config.TEMPLATE_DIR
        if not self.template_dir.exists():
            raise FileNotFoundError(f"Template dir not found: {self.template_dir}")

    def _parse_xyz(self, xyz_path: Path) -> Tuple[int, int, str]:
        """解析 XYZ 获取电荷、多重度、坐标"""
        with open(xyz_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if len(lines) < 3:
            raise ValueError(f"XYZ file {xyz_path.name} is too short.")

        # Line 2: Charge = X Multiplicity = Y
        comment_line = lines[1]
        cm_match = re.search(r"Charge\s*=\s*(-?\d+)\s+Multiplicity\s*=\s*(\d+)", comment_line, re.IGNORECASE)
        if not cm_match:
            cm_match = re.search(r"Charge\s*=\s*(-?\d+).*?Mult.*?\=\s*(\d+)", comment_line, re.IGNORECASE)
        
        if not cm_match:
            raise ValueError(f"Could not parse Charge/Mult from line 2 of {xyz_path.name}")
            
        charge = int(cm_match.group(1))
        mult = int(cm_match.group(2))

        # Line 3+: Coords
        coords = "".join([line for line in lines[2:] if line.strip()])
        return charge, mult, coords

    def generate(self, xyz_path: Path) -> Path:
        """
        主入口：XYZ -> Opt Input
        """
        base_name = xyz_path.stem
        charge, mult, coords = self._parse_xyz(xyz_path)
        
        # 1. 寻找 opt 模板 (.gjf 或 .inp)
        template_path = None
        ext = None
        for e in config.VALID_EXTENSIONS:
            p = self.template_dir / f"opt{e}"
            if p.exists():
                template_path = p
                ext = e
                break
        
        if not template_path:
            raise FileNotFoundError("Missing 'opt.gjf' or 'opt.inp' in templates/")

        # 2. 准备输出
        output_dir = config.DIRS["opt"]
        output_dir.mkdir(parents=True, exist_ok=True)
        
        new_filename = f"{base_name}_opt"
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
            
        return output_file