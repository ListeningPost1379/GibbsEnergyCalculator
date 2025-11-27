import json
import time
import shutil
import os
from pathlib import Path
from typing import Dict, Any

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    WHITE = '\033[97m'
    GREY = '\033[90m'

class StatusTracker:
    def __init__(self, log_file: str = "task_status.json"):
        self.log_file = Path(log_file)
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_data(self):
        if self.log_file.exists():
            try:
                shutil.copy(self.log_file, self.log_file.with_suffix('.json.bak'))
            except IOError: pass
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def start_task(self, mol_name: str, step: str):
        self._ensure_record(mol_name, step)
        self.data[mol_name][step]["status"] = "RUNNING"
        self.data[mol_name][step]["start_time"] = time.time()
        self.data[mol_name][step]["error"] = ""
        self.save_data()

    def finish_task(self, mol_name: str, step: str, status: str, error_msg: str = ""):
        self._ensure_record(mol_name, step)
        record = self.data[mol_name][step]
        if record.get("start_time"):
            duration = time.time() - record["start_time"]
            record["duration_sec"] = duration
            # 注意：这里调用的是静态方法 format_duration
            record["duration_str"] = self.format_duration(duration)
        
        record["status"] = status
        if error_msg:
            record["error"] = error_msg
        self.save_data()

    def set_result(self, mol_name: str, g_val: float):
        if mol_name not in self.data: self.data[mol_name] = {}
        self.data[mol_name]["result_g"] = g_val
        self.save_data()

    def _ensure_record(self, mol_name, step):
        if mol_name not in self.data: self.data[mol_name] = {}
        if step not in self.data[mol_name]:
            self.data[mol_name][step] = {
                "status": "PENDING", "start_time": None, "duration_sec": 0, "duration_str": "", "error": ""
            }

    @staticmethod
    def format_duration(seconds: float) -> str:
        """格式化时间为 HHh MMm SSs"""
        if seconds is None: return ""
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0: return f"{h}h {m}m"
        if m > 0: return f"{m}m {s}s"
        return f"{s}s"

    def print_dashboard(self):
        """清屏并打印双表格"""
        os.system('cls' if os.name == 'nt' else 'clear')

        all_keys = sorted(self.data.keys())
        main_tasks = [k for k in all_keys if not k.startswith("[Extra]")]
        extra_tasks = [k for k in all_keys if k.startswith("[Extra]")]

        W_MOL = 16
        W_STEP = 16
        W_G = 14
        
        # --- 主表格 ---
        print(f"\n{Colors.BOLD}{'='*120}{Colors.ENDC}")
        print(f"{Colors.BOLD}{'MOLECULE':<{W_MOL}} {'OPT':<{W_STEP}} {'GAS':<{W_STEP}} {'SOLV':<{W_STEP}} {'SP':<{W_STEP}} {'G(kcal)':<{W_G}} {'NOTE'}{Colors.ENDC}")
        print(f"{Colors.BOLD}{'-'*120}{Colors.ENDC}")
        
        if not main_tasks:
            print(f"{Colors.GREY}  (No main workflow tasks yet){Colors.ENDC}")

        for mol_name in main_tasks:
            steps = self.data[mol_name]
            row = f"{Colors.CYAN}{mol_name[:W_MOL-1]:<{W_MOL}}{Colors.ENDC} "
            error_notes = []

            for step in ["opt", "gas", "solv", "sp"]:
                info = steps.get(step, {})
                st = info.get("status", "PENDING")
                dur = info.get("duration_str", "")
                err = info.get("error", "")

                content = "PENDING"
                color = Colors.GREY
                if st == "DONE":
                    content = f"DONE {dur}" if dur else "DONE"
                    color = Colors.GREEN
                elif st == "RUNNING":
                    content = "RUNNING..."
                    color = Colors.YELLOW
                elif st == "ERROR":
                    content = "ERROR"
                    color = Colors.RED
                    if err: error_notes.append(f"{step.upper()}:{err}")
                
                row += f"{color}{f'[{content}]':<{W_STEP}}{Colors.ENDC} "

            res = steps.get("result_g")
            if res is not None:
                row += f"{Colors.WHITE}{Colors.BOLD}{res:<{W_G}.2f}{Colors.ENDC} "
            else:
                row += f"{Colors.GREY}{'-':<{W_G}}{Colors.ENDC} "

            if error_notes:
                note_str = " | ".join(error_notes)
                if len(note_str) > 30: note_str = note_str[:27] + "..."
                row += f"{Colors.RED}{note_str}{Colors.ENDC}"
            
            print(row)

        # --- 清扫模式表格 ---
        if extra_tasks:
            print(f"\n{Colors.BOLD}{'='*60}{Colors.ENDC}")
            print(f"{Colors.YELLOW}{'SWEEPER MODE TASKS (Extra Jobs)':^60}{Colors.ENDC}")
            print(f"{Colors.BOLD}{'-'*60}{Colors.ENDC}")
            print(f"{Colors.BOLD}{'JOB FILE':<25} {'FOLDER':<15} {'STATUS':<20}{Colors.ENDC}")
            
            for key in extra_tasks:
                display_name = key.replace("[Extra]", "")
                task_data = self.data[key]
                for folder, info in task_data.items():
                    if folder == "result_g": continue

                    st = info.get("status", "PENDING")
                    dur = info.get("duration_str", "")
                    err = info.get("error", "")

                    status_str = f"[{st}]"
                    if st == "DONE":
                        status_str = f"{Colors.GREEN}[DONE {dur}]{Colors.ENDC}"
                    elif st == "RUNNING":
                        status_str = f"{Colors.YELLOW}[RUNNING...]{Colors.ENDC}"
                    elif st == "ERROR":
                        status_str = f"{Colors.RED}[ERROR: {err}]{Colors.ENDC}"
                    
                    print(f"{Colors.CYAN}{display_name:<25}{Colors.ENDC} {folder:<15} {status_str}")

        print(f"{Colors.BOLD}{'='*120}{Colors.ENDC}")
        print(f"{Colors.YELLOW}Real-time Status:{Colors.ENDC}")