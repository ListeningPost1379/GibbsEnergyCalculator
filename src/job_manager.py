import subprocess
import time
import sys
from pathlib import Path
from typing import Optional, List
from . import config
from .parsers import get_parser

class JobManager:
    def __init__(self, tracker=None):
        self.tracker = tracker
        self.last_int = 0.0
        self.current_proc = None # 持有当前进程句柄

    def get_status_from_file(self, filepath: Path, is_opt: bool = False) -> tuple[str, str]:
        if not filepath.exists(): return "MISSING", ""
        try:
            parser = get_parser(filepath)
            if parser.is_failed(): return "ERROR", "Prog Error"
            if not parser.is_finished(): return "ERROR", "Incomplete" 
            if is_opt:
                if not parser.is_converged(): return "ERR_NC", "Not Converged"
                if parser.has_imaginary_freq(): return "ERR_IMG", "Imag Freq"
                # [新增] 强制检查是否提取到了热力学数据
                if parser.get_thermal_correction() is None:
                    return "ERR_DATA", "No G Corr"
            return "DONE", ""
        except Exception as e: return "ERROR", str(e)

    def submit_and_wait(self, job_file: Path, mol_name: str, step: str, xyz_list: Optional[List[str]] = None) -> bool:
        ext = job_file.suffix
        cmd_template = config.COMMAND_MAP.get(ext)
        if not cmd_template:
            if self.tracker: self.tracker.finish_task(mol_name, step, "ERROR", f"No cmd {ext}")
            return False

        output_file = job_file.with_suffix(".out")
        
        # [修复] 获取任务所在的目录和纯文件名
        work_dir = job_file.parent.resolve()
        input_name = job_file.name
        output_name = output_file.name
        
        # [修复] 命令中只使用文件名，因为我们将切换工作目录
        cmd = cmd_template.format(input=input_name, output=output_name)
        
        if self.tracker: 
            self.tracker.start_task(mol_name, step)
            self.tracker.set_running_msg(f"Running: {mol_name} [{step.upper()}] ... 0s")

        try:
            # [修复] 添加 cwd=work_dir，让 Gaussian/ORCA 在子目录中运行
            self.current_proc = subprocess.Popen(
                cmd, 
                shell=True, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                cwd=work_dir  # <--- 关键修改
            )
            
            start_time = time.time()
            
            # 循环检查进程是否结束
            while self.current_proc.poll() is None:
                elap = time.time() - start_time
                from .tracker import StatusTracker
                time_str = StatusTracker.format_duration(elap)
                
                msg = f"Running: {mol_name} [{step.upper()}] ... {time_str}"
                
                if self.tracker:
                    self.tracker.set_running_msg(msg)
                
                time.sleep(0.5)

        except Exception as e:
            # 这里的 Exception 不会捕获 KeyboardInterrupt (Ctrl+C)
            if self.tracker: self.tracker.finish_task(mol_name, step, "ERROR", str(e))
            self.current_proc = None
            return False
        finally:
            self.current_proc = None
        # --- 修改结束 ---

        status, err = self.get_status_from_file(output_file, is_opt=(step=="opt"))
        if self.tracker: self.tracker.finish_task(mol_name, step, status, err)
        return status == "DONE"

    def stop_current_job(self):
        """强制停止当前任务"""
        if self.current_proc:
            try:
                self.current_proc.kill()
            except:
                pass