# src/sweeper.py
from pathlib import Path
from . import config
from .job_manager import JobManager

class TaskSweeper:
    """
    清扫器：负责扫描 extra_jobs 目录下的独立任务并执行，同时清理无效记录
    """
    def __init__(self, manager: JobManager):
        self.manager = manager
        self.root_dir = config.SWEEPER_DIR

    def purge_ghost_jobs(self):
        """清理 Tracker 中有记录但实际文件已不存在的 Extra 任务"""
        tracker = self.manager.tracker
        if not tracker: return

        # 找出所有 Extra 任务键
        extra_keys = [k for k in tracker.data.keys() if k.startswith("[Extra]")]
        
        keys_to_remove = []
        for key in extra_keys:
            # key 格式: [Extra]文件名
            # 对应的文件名 stem
            stem = key.replace("[Extra]", "")
            
            # 检查文件是否存在
            # 1. 输入文件 (.gjf / .inp)
            has_input = any((self.root_dir / f"{stem}{ext}").exists() for ext in config.VALID_EXTENSIONS)
            
            # 2. 输出文件 (.out / .log)
            # 输出文件也应该在 extra_jobs 目录下
            has_output = any((self.root_dir / f"{stem}{ext}").exists() for ext in [".out", ".log"])
            
            # 只有当输入和输出都不存在时，才视为"僵尸任务"进行删除
            if not has_input and not has_output:
                keys_to_remove.append(key)
        
        if keys_to_remove:
            # print(f"👻 Purging ghost jobs: {keys_to_remove}") # Debug用，可注释
            for k in keys_to_remove:
                if k in tracker.data:
                    del tracker.data[k]
            tracker.save_data()

    def run(self) -> bool:
        """
        扫描并执行一个任务。
        Returns:
            bool: 如果执行了任务返回 True，否则返回 False
        """
        # 0. 先清理僵尸任务
        self.purge_ghost_jobs()

        # 1. 确保目录存在
        if not self.root_dir.exists():
            return False

        # 2. 递归扫描所有 .gjf 和 .inp
        all_jobs = list(self.root_dir.rglob("*.gjf")) + list(self.root_dir.rglob("*.inp"))
        all_jobs.sort(key=lambda x: x.stat().st_mtime, reverse=False)

        if not all_jobs:
            return False

        # 定义需要忽略的文件名特征（如 ORCA 的中间文件）
        IGNORE_KEYWORDS = [".scfgrad", ".ctx", ".tmp", ".opt"] 

        # 3. 遍历检查
        for job in all_jobs:
            if any(k in job.name for k in IGNORE_KEYWORDS):
                continue

            mol_name = f"[Extra]{job.stem}"
            step_name = job.parent.name if job.parent != self.root_dir else "root"

            # 检查状态
            out_file = job.with_suffix(".out")
            status, _ = self.manager.get_status_from_file(out_file)

            if status == "MISSING":
                print(f"\n🧹 Sweeper found new job: {job.name}")
                success = self.manager.submit_and_wait(job, mol_name, step_name)
                return True
            
        return False