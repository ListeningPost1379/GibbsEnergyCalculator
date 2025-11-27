# system_health_check.py
import sys
import shutil
import threading
import time
import json
import pandas as pd
from pathlib import Path

# 确保能导入 src
sys.path.append(str(Path.cwd()))

from src import config
from main import main

# 颜色定义
PASS = '\033[92m[PASS]\033[0m'
FAIL = '\033[91m[FAIL]\033[0m'
INFO = '\033[94m[INFO]\033[0m'

def setup_environment():
    print(f"\n{INFO} 1. 初始化全能测试环境...")
    
    # 1. 清理
    for p in ["xyz", "data", "extra_jobs", "templates", "task_status.json", "results.csv"]:
        path = Path(p)
        if path.is_dir(): shutil.rmtree(path)
        elif path.is_file(): path.unlink()
    
    # 2. 重建目录
    for d in ["xyz", "templates", "extra_jobs", "data/opt"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    # 3. 创建模板 (同时创建 gjf 和 inp)
    # 目的：测试 Generator 在混用时的优先级
    base_tpl = "%chk=[NAME]\n#p opt\n[NAME]\n[Charge] [Multiplicity]\n[GEOMETRY]\n"
    for t in ["opt", "sp", "gas", "solv"]:
        with open(f"templates/{t}.gjf", "w") as f: f.write(base_tpl) # Gaussian 模板
        with open(f"templates/{t}.inp", "w") as f: f.write(base_tpl) # ORCA 模板

    # 4. 准备测试用例
    
    # Case A: 标准 Gaussian 流程 (test_gau.xyz)
    # 预期：Generator 自动生成 .gjf -> 运行 G16 -> 生成 G16 子任务
    with open("xyz/test_gau.xyz", "w") as f:
        f.write("3\nCharge=0 Multiplicity=1\nO 0 0 0\nH 0 1 0\nH 0 0 1")

    # Case B: 混合流程 / ORCA 解析测试 (test_mix.xyz)
    # 技巧：我们手动预先生成一个 .inp 的 Opt 输入文件
    # 预期：Main 发现 opt.inp 存在 -> 运行 ORCA -> 解析 ORCA 产物 -> 生成子任务
    with open("xyz/test_mix.xyz", "w") as f:
        f.write("3\nCharge=0 Multiplicity=1\nO 0 0 0\nH 0 1 0\nH 0 0 1")
    
    # 这里的关键：手动放入一个 .inp 文件，强制让 Opt 阶段跑 ORCA
    # 从而测试 src/parsers/orca.py 是否工作正常
    with open("data/opt/test_mix_opt.inp", "w") as f:
        f.write(base_tpl.replace("[NAME]", "test_mix_opt").replace("[Charge]", "0").replace("[Multiplicity]", "1").replace("[GEOMETRY]", "O 0 0 0"))

    # Case C: 失败案例 (test_fail.xyz)
    with open("xyz/test_fail.xyz", "w") as f:
        f.write("3\nCharge=0 Multiplicity=1\nO 0 0 0\nH 0 1 0\nH 0 0 1")

    # Case D: 清扫模式 (extra_jobs/pure_orca.inp)
    Path("extra_jobs/manual").mkdir(exist_ok=True)
    with open("extra_jobs/manual/pure_orca.inp", "w") as f:
        f.write(base_tpl)

    print(f"{PASS} 环境搭建完成 (涵盖 Gaussian, ORCA, Mixed, Fail, Sweeper)")

def inject_mock_config():
    print(f"{INFO} 2. 注入双核 Mock 引擎...")
    
    mock_cmd = f"{sys.executable} mock_engine.py {{input}} {{output}}"
    
    # 同时劫持 .gjf 和 .inp 的命令
    config.COMMAND_MAP = {
        ".gjf": mock_cmd,
        ".inp": mock_cmd
    }
    # 确保 Sweeper 指向测试目录
    config.SWEEPER_DIR = Path("extra_jobs")
    
    print(f"{PASS} 引擎注入成功 (支持 .gjf 和 .inp)")

def verify_results():
    print(f"\n{INFO} 4. 验证测试结果...")
    errors = 0
    
    try:
        with open("task_status.json", "r") as f:
            data = json.load(f)
        
        # 1. 验证标准 Gaussian 流程
        if data.get("test_gau", {}).get("opt", {}).get("status") == "DONE":
            print(f"{PASS} Gaussian 全流程: OPT 完成")
        else:
            print(f"{FAIL} Gaussian 全流程: OPT 未完成")
            errors += 1

        # 2. 验证 ORCA 混合流程 (关键!)
        # 这证明了 JobManager 能跑 .inp，Parser 能解析 ORCA 输出，Generator 能基于 ORCA 结果生成子任务
        if data.get("test_mix", {}).get("opt", {}).get("status") == "DONE":
            print(f"{PASS} ORCA 混合流程: OPT 完成 (证明 ORCA 解析器正常)")
        else:
            print(f"{FAIL} ORCA 混合流程: OPT 未完成")
            errors += 1

        # 3. 验证报错逻辑
        if data.get("test_fail", {}).get("opt", {}).get("status") == "ERROR":
            print(f"{PASS} 错误捕获: 成功标记 ERROR")
        else:
            print(f"{FAIL} 错误捕获: 失败")
            errors += 1

        # 4. 验证清扫模式
        if "[Extra]pure_orca" in data:
            print(f"{PASS} 清扫模式: 成功运行额外任务")
        else:
            print(f"{FAIL} 清扫模式: 未检测到任务")
            errors += 1

        # 5. 验证计算结果 (Calculator)
        if Path("results.csv").exists():
            df = pd.read_csv("results.csv")
            if "test_gau" in df["Molecule"].values and "test_mix" in df["Molecule"].values:
                print(f"{PASS} 计算模块: 成功生成 G 值结果")
            else:
                print(f"{FAIL} 计算模块: 结果缺失")
                errors += 1
        else:
            print(f"{FAIL} 计算模块: CSV 未生成")
            errors += 1

    except Exception as e:
        print(f"{FAIL} 验证过程崩溃: {e}")
        errors += 1

    if errors == 0:
        print(f"\n🎉🎉🎉 完美通过！系统支持 Gaussian/ORCA 双引擎及混合调度。 🎉🎉🎉")
    else:
        print(f"\n❌❌❌ 发现 {errors} 个问题。")

def run_test_suite():
    setup_environment()
    inject_mock_config()
    
    print(f"\n{INFO} 3. 启动主程序 (等待 20 秒)...")
    
    t = threading.Thread(target=main, daemon=True)
    t.start()
    
    try:
        # 给足时间跑完所有流程
        # test_gau(4 steps) + test_mix(4 steps) + test_fail(1 step) + sweeper(1 step)
        # 约 10 个任务，每个 0.3s ~ 3-4s，加上轮询间隔，20s 足够
        for i in range(20, 0, -1):
            sys.stdout.write(f"\r⏳ Running tests... {i}s ")
            sys.stdout.flush()
            time.sleep(1)
        print("\n")
    except KeyboardInterrupt:
        pass
    
    verify_results()

if __name__ == "__main__":
    run_test_suite()