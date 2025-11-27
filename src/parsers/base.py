from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

class BaseParser(ABC):
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.content = self._read_file(filepath)

    def _read_file(self, filepath: Path) -> str:
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='latin-1') as f:
                return f.read()

    @classmethod
    @abstractmethod
    def detect(cls, content: str) -> bool:
        pass

    @abstractmethod
    def is_finished(self) -> bool:
        pass

    @abstractmethod
    def is_converged(self) -> bool:
        pass
    
    @abstractmethod
    def has_imaginary_freq(self) -> bool:
        pass

    # --- 拆分后的新接口 ---
    @abstractmethod
    def get_charge_mult(self) -> Tuple[int, int]:
        """提取电荷与多重度"""
        pass

    @abstractmethod
    def get_coordinates(self) -> str:
        """提取优化后的坐标 (格式化为 XYZ 字符串)"""
        pass
    # --------------------

    @abstractmethod
    def get_electronic_energy(self) -> Optional[float]:
        pass

    @abstractmethod
    def get_thermal_correction(self) -> Optional[float]:
        pass

    def parse_all(self) -> Dict[str, Any]:
        """辅助方法：提取所有数据"""
        data = {
            "parser_type": self.__class__.__name__,
            "file": self.filepath.name,
            "is_finished": self.is_finished(),
            "is_converged": self.is_converged(),
            "has_imaginary": self.has_imaginary_freq(),
            "energy": self.get_electronic_energy(),
            "thermal_corr": self.get_thermal_correction(),
            "charge_mult": None,
            "coords": None,
            "error": None
        }
        
        try:
            # 只有收敛了才去抓坐标，或者你想强制抓取也行
            if self.is_converged() or self.is_finished(): 
                data["charge_mult"] = self.get_charge_mult()
                data["coords"] = self.get_coordinates()
        except ValueError as e:
            data["error"] = str(e)
            
        return data