# src/tracker.py
import json
import time
import shutil
from pathlib import Path
from typing import Dict, Any

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'   # 完成
    YELLOW = '\033[93m'  # 进行中
    RED = '\033[91m'     # 失败
    ENDC = '\033[0m'     # 重置
    BOLD = '\033[1m'

class StatusTracker:
    def __init__(self, log_file: str = "task_status.json"):
        self.log_file = Path(log_file)
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        """加载历史记录"""
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_data(self):
        """保存记录到文件 (含备份)"""
        if self.log_file.exists():
            try:
                shutil.copy(self.log_file, self.log_file.with_suffix('.json.bak'))
            except IOError:
                pass 
        
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def start_task(self, mol_name: str, step: str):
        """标记任务开始"""
        self._ensure_record(mol_name, step)
        self.data[mol_name][step]["status"] = "RUNNING"
        # 如果是重跑，更新开始时间
        self.data[mol_name][step]["start_time"] = time.time()
        self.data[mol_name][step]["error"] = ""
        self.save_data()

    def finish_task(self, mol_name: str, step: str, status: str, error_msg: str = ""):
        """标记任务结束 (DONE or ERROR)"""
        self._ensure_record(mol_name, step)
        record = self.data[mol_name][step]
        
        # 计算耗时
        if record.get("start_time"):
            duration_sec = time.time() - record["start_time"]
            record["duration_sec"] = duration_sec
            record["duration_str"] = self._format_duration(duration_sec)
        
        record["status"] = status
        if error_msg:
            record["error"] = error_msg
        
        self.save_data()

    def _ensure_record(self, mol_name, step):
        if mol_name not in self.data:
            self.data[mol_name] = {}
        if step not in self.data[mol_name]:
            self.data[mol_name][step] = {
                "status": "PENDING",
                "start_time": None,
                "duration_sec": 0,
                "duration_str": "",
                "error": ""
            }

    def _format_duration(self, seconds: float) -> str:
        if seconds is None: return ""
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        parts = []
        if h > 0: parts.append(f"{int(h)}h")
        if m > 0: parts.append(f"{int(m)}m")
        parts.append(f"{int(s)}s")
        return " ".join(parts)

    def print_dashboard(self):
        """打印彩色状态面板"""
        print(f"\n{Colors.BOLD}{'='*95}{Colors.ENDC}")
        # 表头
        print(f"{Colors.BOLD}{'MOLECULE':<15} {'OPT':<20} {'GAS':<20} {'SOLV':<20} {'SP':<20}{Colors.ENDC}")
        print(f"{Colors.BOLD}{'-'*95}{Colors.ENDC}")

        # 简单排序：按分子名
        sorted_mols = sorted(self.data.keys())

        for mol_name in sorted_mols:
            steps = self.data[mol_name]
            row_str = f"{Colors.CYAN}{mol_name:<15}{Colors.ENDC}"
            
            # 依次打印四个步骤的状态
            for step in ["opt", "gas", "solv", "sp"]:
                info = steps.get(step, {})
                status = info.get("status", "PENDING")
                duration = info.get("duration_str", "")
                
                # 颜色与格式逻辑
                if status == "DONE":
                    # 显示: [DONE 1h 2m] (绿色)
                    text = f"DONE {duration}" if duration else "DONE"
                    colored_text = f"{Colors.GREEN}[{text}]{Colors.ENDC}"
                elif status == "RUNNING":
                    # 显示: [RUNNING...] (黄色)
                    colored_text = f"{Colors.YELLOW}[RUNNING...]{Colors.ENDC}"
                elif status == "ERROR":
                    # 显示: [ERROR] (红色)
                    colored_text = f"{Colors.RED}[ERROR]{Colors.ENDC}"
                else:
                    # 显示: [PENDING] (灰色)
                    colored_text = f"[{status}]"
                
                # <30 是为了留足空间给ANSI颜色代码
                row_str += f"{colored_text:<30}" 
            
            print(row_str)
            
            # 如果有错误，在下方单独打印详情
            for step, info in steps.items():
                if info.get("status") == "ERROR" and info.get("error"):
                    print(f"  └── {Colors.RED}{step.upper()} Failed: {info['error']}{Colors.ENDC}")

        print(f"{Colors.BOLD}{'='*95}{Colors.ENDC}\n")