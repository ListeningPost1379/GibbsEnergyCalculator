import re
from .base import BaseParser

class GaussianParser(BaseParser):
    
    @classmethod
    def detect(cls, content: str) -> bool:
        return "Gaussian, Inc." in content or "Entering Gaussian System" in content

    def is_finished(self) -> bool:
        return "Normal termination" in self.content

    def is_converged(self) -> bool:
        return "Stationary point found" in self.content

    def has_imaginary_freq(self) -> bool:
        parts = self.content.split("Harmonic frequencies")
        if len(parts) < 2: return False 
        target_block = parts[-1] 
        match = re.search(r"Frequencies\s*--\s*(.*)", target_block)
        if match:
            try:
                freqs = [float(x) for x in match.group(1).split()]
                return any(f < -0.1 for f in freqs)
            except ValueError:
                return False
        return False

    def get_electronic_energy(self):
        matches = re.findall(r"SCF Done:.*=\s*(-?\d+\.\d+)", self.content)
        return float(matches[-1]) if matches else None

    def get_thermal_correction(self):
        match = re.search(r"Thermal correction to Gibbs Free Energy=\s*(-?\d+\.\d+)", self.content)
        return float(match.group(1)) if match else None

    def get_charge_mult(self) -> tuple[int, int]:
        """独立提取电荷多重度"""
        cm_match = re.search(r"Charge\s*=\s*(-?\d+)\s+Multiplicity\s*=\s*(\d+)", self.content)
        if not cm_match:
            raise ValueError(f"Critical: Failed to find 'Charge = X Multiplicity = Y' in {self.filepath.name}")
        return int(cm_match.group(1)), int(cm_match.group(2))

    def get_coordinates(self) -> str:
        """独立提取坐标：扫描至虚线结束"""
        # 1. 定位最后一个 Standard orientation (或者 Input)
        orientations = ["Standard orientation", "Input orientation"]
        target_block_start = -1
        
        # 找到最后一个 orientation 在全文中的位置索引
        for tag in orientations:
            # rfind 找最后一次出现的位置
            idx = self.content.rfind(tag)
            if idx > target_block_start:
                target_block_start = idx
        
        if target_block_start == -1:
            raise ValueError(f"Critical: Failed to extract Coordinates block in {self.filepath.name}")

        # 截取从 orientation 开始的内容
        block_content = self.content[target_block_start:]
        lines = block_content.split('\n')
        
        formatted_lines = []
        
        # 状态机
        # Gaussian 格式通常是：
        # Header Line
        # ------------------- (Start Dash)
        # Header Cols
        # Header Cols
        # ------------------- (Header Dash)
        # Data
        # Data
        # ------------------- (End Dash)
        
        dash_count = 0
        period_table = {
            1: 'H', 2: 'He', 6: 'C', 7: 'N', 8: 'O', 9: 'F', 10: 'Ne',
            15: 'P', 16: 'S', 17: 'Cl', 18: 'Ar', 35: 'Br', 53: 'I',
            92: 'U', 94: 'Pu', 90: 'Th'
        } 

        for line in lines:
            if "--------" in line:
                dash_count += 1
                continue
            
            # 数据通常在第3个虚线段之前（有些版本是第2个之后）
            # 一般来说：StartDash -> HeaderDash -> [DATA] -> EndDash
            # 所以当 dash_count == 2 时，是数据区
            if dash_count == 2:
                parts = line.split()
                # 格式: CenterNumber AtomicNumber AtomicType X Y Z
                if len(parts) >= 6:
                    try:
                        atom_num = int(parts[1])
                        symbol = period_table.get(atom_num, "X")
                        x, y, z = parts[3], parts[4], parts[5]
                        formatted_lines.append(f"{symbol:<4} {x:>12} {y:>12} {z:>12}")
                    except ValueError:
                        continue
            
            # 遇到第3个虚线，说明数据块结束
            if dash_count >= 3:
                break
        
        if not formatted_lines:
             raise ValueError("Critical: Found orientation block but failed to parse atom lines.")
             
        return "\n".join(formatted_lines)