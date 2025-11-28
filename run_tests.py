import os
import shutil
import sys
import time
import json
import unittest
from pathlib import Path

# --- 1. 环境劫持 ---
# 在导入 src 之前，我们需要欺骗 config，让它指向测试目录
# 注意：这需要 config.py 使用的是动态路径 (Path(__file__))，
# 或者我们可以在导入后动态修改 config 的变量

from src import config
from src.job_manager import JobManager
from src.tracker import StatusTracker
from src.opt_generator import OptGenerator
from src.sub_generator import SubGenerator
from src.sweeper import TaskSweeper

# 定义测试目录
TEST_ROOT = Path("test_env")
TEST_XYZ = TEST_ROOT / "xyz"
TEST_DATA = TEST_ROOT / "data"
TEST_TEMPLATES = TEST_ROOT / "templates"
TEST_EXTRA = TEST_ROOT / "extra_jobs"
TEST_LOG = TEST_ROOT / "task_status.json"

class GibbsWorkflowTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n🔵 Setting up Test Environment...")
        if TEST_ROOT.exists(): shutil.rmtree(TEST_ROOT)
        TEST_ROOT.mkdir()
        TEST_XYZ.mkdir()
        TEST_TEMPLATES.mkdir()
        TEST_EXTRA.mkdir()
        TEST_DATA.mkdir()
        for d in ["opt", "gas", "solv", "sp"]:
            (TEST_DATA / d).mkdir()

        # 劫持 Config 路径
        config.XYZ_DIR = TEST_XYZ
        config.TEMPLATE_DIR = TEST_TEMPLATES
        config.DATA_DIR = TEST_DATA
        config.SWEEPER_DIR = TEST_EXTRA
        config.DIRS = {
            "opt": TEST_DATA / "opt", "sp": TEST_DATA / "sp",
            "gas": TEST_DATA / "gas", "solv": TEST_DATA / "solv"
        }
        
        # 劫持命令：指向 mock_program.py
        # 注意：这里使用 sys.executable 获取当前 python 路径
        mock_script = Path("mock_program.py").absolute()
        cmd_base = f"{sys.executable} {mock_script} {{input}} {{output}} 0.5" # 0.5秒模拟时间
        config.COMMAND_MAP = {
            ".gjf": cmd_base,
            ".inp": cmd_base
        }

        # 创建 Dummy Templates
        with open(TEST_TEMPLATES / "opt.gjf", 'w') as f: f.write("Opt Template [NAME] [Charge] [Multiplicity]")
        with open(TEST_TEMPLATES / "gas.gjf", 'w') as f: f.write("Gas Template")
        with open(TEST_TEMPLATES / "solv.gjf", 'w') as f: f.write("Solv Template")
        with open(TEST_TEMPLATES / "sp.gjf", 'w') as f: f.write("SP Template")

        # 创建 Dummy XYZ
        cls.mol_name = "test_mol"
        with open(TEST_XYZ / f"{cls.mol_name}.xyz", 'w') as f:
            f.write("3\nCharge=0 Multiplicity=1\nC 0 0 0\nH 0 0 1\nH 0 1 0")

    def test_01_generators(self):
        """测试 Opt 和 Sub 文件生成"""
        print("\n🧪 Test 1: Generators")
        
        # Opt Gen
        opt_gen = OptGenerator()
        opt_path = opt_gen.generate(TEST_XYZ / f"{self.mol_name}.xyz")
        self.assertTrue(opt_path.exists(), "Opt input not generated")
        
        # Sub Gen (Mock coords)
        sub_gen = SubGenerator()
        sub_paths = sub_gen.generate_all(self.mol_name, 0, 1, "C 0 0 0")
        self.assertEqual(len(sub_paths), 3, "Should generate 3 sub tasks")
        for p in sub_paths:
            self.assertTrue(p.exists(), f"Sub task {p.name} missing")

    def test_02_execution_tracking(self):
        """测试任务提交、运行与状态记录"""
        print("\n🧪 Test 2: Execution & Tracking")
        
        tracker = StatusTracker(str(TEST_LOG))
        mgr = JobManager(tracker)
        
        opt_file = config.DIRS["opt"] / f"{self.mol_name}_opt.gjf"
        
        # 运行模拟任务
        print("   >> Submitting Mock Gaussian Job...")
        success = mgr.submit_and_wait(opt_file, self.mol_name, "opt")
        
        self.assertTrue(success, "Job submission failed")
        self.assertTrue(opt_file.with_suffix(".out").exists(), "Output file missing")
        
        # 验证 Tracker 数据
        data = tracker.data[self.mol_name]["opt"]
        self.assertEqual(data["status"], "DONE", "Status should be DONE")
        self.assertTrue("duration_str" in data, "Duration should be recorded")
        print(f"   >> Job Finished. Duration: {data['duration_str']}")

    def test_03_history_persistence(self):
        """测试历史记录读取 (关闭程序后再打开)"""
        print("\n🧪 Test 3: History Persistence")
        
        # 销毁旧实例，重新加载
        new_tracker = StatusTracker(str(TEST_LOG))
        
        record = new_tracker.data.get(self.mol_name, {}).get("opt", {})
        self.assertEqual(record.get("status"), "DONE", "History failed to load DONE status")
        print(f"   >> History loaded successfully: {record}")

    def test_04_stop_functionality(self):
        """测试强制停止功能"""
        print("\n🧪 Test 4: Stop Button")
        
        tracker = StatusTracker(str(TEST_LOG))
        mgr = JobManager(tracker)
        
        # ... (之前的代码不变) ...
        long_job = TEST_EXTRA / "long_job.gjf"
        with open(long_job, 'w') as f: f.write("Mock")
        
        # 修改 Mock 命令
        mock_script = Path("mock_program.py").absolute()
        cmd_long = f"{sys.executable} {mock_script} {{input}} {{output}} 5.0"
        original_cmd = config.COMMAND_MAP[".gjf"]
        config.COMMAND_MAP[".gjf"] = cmd_long

        print("   >> Starting long process...")
        # 模拟 JobManager 的 submit 行为，手动启动进程
        mgr.current_proc = import_subprocess().Popen(
            f"{sys.executable} -c 'import time; time.sleep(5)'", 
            shell=True
        )
        
        time.sleep(0.5)
        self.assertIsNone(mgr.current_proc.poll(), "Process should be running")
        
        print("   >> Sending Stop signal...")
        mgr.stop_current_job()
        
        # --- 修复：显式等待进程结束以消除 ResourceWarning ---
        try:
            mgr.current_proc.wait(timeout=2)
        except:
            pass
        # ------------------------------------------------
        
        # 恢复命令配置
        config.COMMAND_MAP[".gjf"] = original_cmd

    def test_05_sweeper(self):
        """测试清扫模式"""
        print("\n🧪 Test 5: Sweeper Mode")
        
        # --- 修复：先清理 Test 4 残留的文件 ---
        for f in TEST_EXTRA.glob("*"):
            f.unlink()
        # ------------------------------------

        mgr = JobManager(StatusTracker(str(TEST_LOG)))
        sweeper = TaskSweeper(mgr)
        
        # 创建一个额外的任务
        extra_job = TEST_EXTRA / "manual_calc.gjf"
        with open(extra_job, 'w') as f: f.write("Mock Extra")
        
        print("   >> Running Sweeper...")
        ran = sweeper.run()
        
        self.assertTrue(ran, "Sweeper should have found and run the job")
        
        # 此时应该只运行了 manual_calc.gjf
        self.assertTrue(extra_job.with_suffix(".out").exists(), "Sweeper output missing")
        
        # 检查是否记录在 Tracker (带 [Extra] 前缀)
        key = "[Extra]manual_calc"
        with open(TEST_LOG, 'r') as f:
            data = json.load(f)
        self.assertIn(key, data, "Sweeper job not in history")

def import_subprocess():
    import subprocess
    return subprocess

if __name__ == "__main__":
    unittest.main()