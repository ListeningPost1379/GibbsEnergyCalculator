# src/calculator.py
from typing import Dict
from . import config

class ThermodynamicsCalculator:
    """
    专门负责热力学公式计算
    G = E_sp + G_corr + (E_solv - E_gas) + dG_conc
    """
    
    @staticmethod
    def calculate_g(energies: Dict[str, float], mol_name: str) -> Dict[str, float]:
        """
        Args:
            energies: 字典, 需包含 'sp', 'gas', 'solv', 'thermal_corr' (单位: Hartree)
            mol_name: 分子名 (用于查找特殊浓度校正)
            
        Returns:
            Dict: 包含各分项及最终结果 (同时提供 Ha 和 kcal/mol)
        """
        required_keys = ['sp', 'gas', 'solv', 'thermal_corr']
        for k in required_keys:
            if k not in energies or energies[k] is None:
                raise ValueError(f"Missing energy component: {k}")

        E_sp = energies['sp']
        E_gas = energies['gas']
        E_solv = energies['solv']
        G_corr = energies['thermal_corr']

        # 1. 计算溶剂化自由能校正 dG_solv
        # 公式: dG_solv = E_solv - E_gas (低精度差值)
        dG_solv = E_solv - E_gas

        # 2. 获取标准态校正 (Concentration Correction)
        # 查找 config 中定义的特殊物种 (忽略大小写)
        special_corr = config.SPECIAL_CONC_CORR_HARTREE.get(mol_name.lower())
        
        if special_corr is not None:
            conc_corr = special_corr
        else:
            conc_corr = config.DEFAULT_CONC_CORR_HARTREE

        # 3. 计算最终 G
        G_final_hartree = E_sp + G_corr + dG_solv + conc_corr

        return {
            "dG_solv (Ha)": dG_solv,
            "dG_solv (kcal)": dG_solv * config.HARTREE_TO_KCAL,
            "Conc_Corr (kcal)": conc_corr * config.HARTREE_TO_KCAL,
            "G_Final (Ha)": G_final_hartree,
            "G_Final (kcal)": G_final_hartree * config.HARTREE_TO_KCAL
        }