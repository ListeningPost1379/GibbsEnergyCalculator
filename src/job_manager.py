# src/job_manager.py
import subprocess
import time
from pathlib import Path
from . import config
from .parsers import get_parser

class JobManager:
    """
    任务管理器：负责提交任务并监控其运行状态 (阻塞模式)
    """
    def __init__(self, tracker=None):
        self.tracker = tracker # 用于回调更新状态

    def get_status_from_file(self, filepath: Path, is_opt: bool = False) -> tuple[str, str]:
        """
        通过解析输出文件判断任务状态
        Returns: (status, error_msg)
        Status enum: "DONE", "RUNNING", "ERROR", "MISSING"
        """
        if not filepath.exists():
            return "MISSING", ""
        
        try:
            # 使用 Parser 模块解析
            parser = get_parser(filepath)
            
            # 1. 检查程序是否正常结束
            if not parser.is_finished():
                # 文件存在但未写完结束语，视为运行中
                return "RUNNING", ""
            
            # 2. 如果是 Opt 任务，必须检查收敛
            if is_opt and not parser.is_converged():
                return "ERROR", "Optimization not converged"
            
            # 3. 检查虚频 (根据需求，有虚频视为错误)
            if is_opt and parser.has_imaginary_freq():
                 return "ERROR", "Imaginary frequency detected"
            
            return "DONE", ""

        except Exception as e:
            # 解析发生异常，通常意味着文件格式错误或被截断
            return "ERROR", str(e)

    def submit_and_wait(self, job_file: Path, mol_name: str, step: str) -> bool:
        """
        【阻塞式】提交任务并轮询等待完成
        Returns: True (成功), False (失败)
        """
        # 1. 准备命令
        ext = job_file.suffix
        cmd_template = config.COMMAND_MAP.get(ext)
        
        if not cmd_template:
            err_msg = f"No command configured for extension {ext}"
            print(f"  ❌ {err_msg}")
            if self.tracker: self.tracker.finish_task(mol_name, step, "ERROR", err_msg)
            return False

        # 推断输出文件名 (同名 .out)
        output_file = job_file.with_suffix(".out")
        
        # 格式化命令
        cmd = cmd_template.format(input=str(job_file), output=str(output_file))
        
        # 2. 记录开始
        print(f"  🚀 [Submit] {mol_name} - {step.upper()}")
        if self.tracker: self.tracker.start_task(mol_name, step)
        
        # 3. 启动进程
        try:
            # 启动后台进程，不阻塞 Python，以便我们手动轮询
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"  ❌ Submission failed: {e}")
            if self.tracker: self.tracker.finish_task(mol_name, step, "ERROR", str(e))
            return False

        # 4. 阻塞等待循环 (Polling)
        print(f"  ⏳ Waiting for {step}...", end="", flush=True)
        
        POLL_INTERVAL = 30 # 轮询间隔 (秒)
        
        while True:
            # 检查输出文件状态
            status, err = self.get_status_from_file(output_file, is_opt=(step=="opt"))
            
            if status == "DONE":
                print(f"\r  ✅ {step.upper()} Finished!            ")
                if self.tracker: self.tracker.finish_task(mol_name, step, "DONE")
                return True
            
            elif status == "ERROR":
                print(f"\r  ❌ {step.upper()} Failed: {err}        ")
                if self.tracker: self.tracker.finish_task(mol_name, step, "ERROR", err)
                return False
            
            # 检查进程是否意外退出 (文件是 MISSING 但进程也没了)
            if proc.poll() is not None and status == "MISSING":
                 err = "Process exited but no output generated."
                 print(f"\r  ❌ {step.upper()} Crashed: {err}")
                 if self.tracker: self.tracker.finish_task(mol_name, step, "ERROR", err)
                 return False

            # 等待下一轮检查
            time.sleep(POLL_INTERVAL)