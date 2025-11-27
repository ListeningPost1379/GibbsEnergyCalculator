# src/config.py
from pathlib import Path

# ================= 项目路径配置 =================
# 获取当前文件的上级目录的上级目录，即项目根目录 workflow/GibbsEnergy/
ROOT_DIR = Path(__file__).parent.parent 

# 原料目录：存放 .xyz 文件
XYZ_DIR = ROOT_DIR / "xyz"

# 数据产物目录
DATA_DIR = ROOT_DIR / "data"
TEMPLATE_DIR = ROOT_DIR / "templates"

# 任务类型对应的子目录
DIRS = {
    "opt": DATA_DIR / "opt",
    "sp": DATA_DIR / "sp",
    "gas": DATA_DIR / "gas",
    "solv": DATA_DIR / "solv"
}

# ================= 模板与软件配置 =================

# 允许的模板后缀
VALID_EXTENSIONS = [".gjf", ".inp"]

# 运行命令映射 (Command Map)
# {input} -> 输入文件的绝对路径
# {output} -> 输出文件的绝对路径 (通常是同名 .out 或 .log)
# 请根据实际服务器环境修改命令
COMMAND_MAP = {
    # Gaussian: 使用标准输入重定向
    ".gjf": "g16 < {input} > {output}", 
    
    # ORCA: 需要全路径调用 (示例)
    ".inp": "/path/to/orca {input} > {output}",
    
    # 如果使用 Slurm 提交脚本
    # ".sh": "sbatch {input}"
}

# ================= 物理常数与单位 =================
HARTREE_TO_KCAL = 627.509474

# ================= 热力学校正配置 =================

# 默认标准态校正 (1 atm -> 1 M): ~1.89 kcal/mol
_DG_CONC_KCAL = 1.89 
DEFAULT_CONC_CORR_HARTREE = _DG_CONC_KCAL / HARTREE_TO_KCAL

# 特殊物种校正 (例如纯溶剂水)
# Key: 文件名(不含后缀, 小写), Value: kcal/mol
_SPECIAL_CORRECTIONS_KCAL = {
    "h2o": 0.0,
    "water": 0.0
}

# 转换为 Hartree 供计算模块使用
SPECIAL_CONC_CORR_HARTREE = {
    k: v / HARTREE_TO_KCAL 
    for k, v in _SPECIAL_CORRECTIONS_KCAL.items()
}