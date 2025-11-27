import re
from .base import BaseParser

class OrcaParser(BaseParser):

    @classmethod
    def detect(cls, content: str) -> bool:
        return "* O   R   C   A *" in content or "Program Version" in content

    def is_finished(self) -> bool:
        return "ORCA TERMINATED NORMALLY" in self.content

    def is_converged(self) -> bool:
        return "THE OPTIMIZATION HAS CONVERGED" in self.content

    def has_imaginary_freq(self) -> bool:
        if "VIBRATIONAL FREQUENCIES" not in self.content: return False
        freq_block = self.content.split("VIBRATIONAL FREQUENCIES")[-1]
        freqs = re.findall(r":\s+(-?\d+\.\d+)\s+cm\*\*-1", freq_block)
        for f in freqs:
            if float(f) < -0.1: return True
        return False

    def get_electronic_energy(self):
        match = re.search(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", self.content)
        return float(match.group(1)) if match else None

    def get_thermal_correction(self):
        match = re.search(r"G-E\(el\)\s+.*?(-?\d+\.\d+)\s+Eh", self.content)
        return float(match.group(1)) if match else None

    def get_charge_mult(self) -> tuple[int, int]:
        """独立提取电荷多重度"""
        # 模式A: * xyz -2 1
        cm_match_a = re.search(r"\*\s+xyz\s+(-?\d+)\s+(\d+)", self.content)
        if cm_match_a:
            return int(cm_match_a.group(1)), int(cm_match_a.group(2))
        
        # 模式B: Total Charge ...
        c_match = re.search(r"Total Charge\s+Charge\s+\.+\s+(-?\d+)", self.content)
        m_match = re.search(r"Multiplicity\s+Mult\s+\.+\s+(\d+)", self.content)
        if c_match and m_match:
            return int(c_match.group(1)), int(m_match.group(1))
            
        raise ValueError(f"Critical: Failed to extract Charge/Multiplicity in {self.filepath.name}")

    def get_coordinates(self) -> str:
        """独立提取坐标：扫描至空行结束"""
        marker = "FINAL ENERGY EVALUATION AT THE STATIONARY POINT"
        if marker in self.content:
            search_content = self.content.split(marker)[-1]
        else:
            # 兜底：如果是单点或者未优化完全，尝试用全部内容
            search_content = self.content

        header = "CARTESIAN COORDINATES (ANGSTROEM)"
        if header not in search_content:
             raise ValueError(f"Critical: Found Stationary Point marker but failed to find '{header}' block.")
        
        # 截取 header 之后的内容
        coord_section = search_content.split(header)[1]
        lines = coord_section.strip().split('\n')
        
        formatted_coords = []
        
        for line in lines:
            stripped = line.strip()
            
            # 1. 终止条件：遇到空行
            if not stripped:
                if formatted_coords: # 如果已经读到了数据又遇到空行，说明结束了
                    break
                else: # 如果还没读到数据就遇到空行（header后可能有空行），继续
                    continue

            # 2. 终止条件：遇到虚线（有些 ORCA 版本结尾有虚线）
            if "-------" in stripped:
                # 如果是第一行可能是 header 分隔符，跳过
                # 如果我们已经收集了数据，那就是结束符
                if formatted_coords:
                    break
                continue

            # 3. 解析数据
            parts = stripped.split()
            if len(parts) >= 4:
                try:
                    # 验证这行是不是原子数据 (后面3位能转float)
                    float(parts[1])
                    formatted_coords.append(f"{parts[0]:<4} {parts[1]:>12} {parts[2]:>12} {parts[3]:>12}")
                except ValueError:
                    continue

        if not formatted_coords:
             raise ValueError(f"Critical: Coordinate block was found but no valid atom lines were extracted.")

        return "\n".join(formatted_coords)