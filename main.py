import time
from pathlib import Path

# 导入核心模块
from src import config
from src.parsers import get_parser
from src.opt_generator import OptGenerator
from src.sub_generator import SubGenerator
from src.job_manager import JobManager
from src.tracker import StatusTracker
from src.calculator import ThermodynamicsCalculator

def scan_xyz_source(xyz_dir: Path):
    """
    扫描 xyz 目录，按最后修改时间倒序排列
    """
    if not xyz_dir.exists():
        try:
            xyz_dir.mkdir(parents=True)
        except OSError:
            pass 
        return []
    
    files = list(xyz_dir.glob("*.xyz"))
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files

def main():
    tracker = StatusTracker()
    manager = JobManager(tracker=tracker)
    opt_gen = OptGenerator()
    sub_gen = SubGenerator()
    
    print("🚀 启动 Gibbs Free Energy 自动化工作流")
    print(f"📂 原料目录: {config.XYZ_DIR}")
    print("⏳ 模式: 阻塞式串行调度 (Blocking Mode)")

    while True:
        # 1. 扫描原料目录
        xyz_files = scan_xyz_source(config.XYZ_DIR)
        
        if not xyz_files:
            print("💤 xyz 目录为空，等待 60s...")
            time.sleep(60)
            continue
        
        tracker.print_dashboard()
        
        action_taken = False
        
        for xyz_file in xyz_files:
            mol_name = xyz_file.stem 
            
            # =========================================================
            # STAGE 1: Optimization (OPT)
            # =========================================================
            
            # 1.1 检查 Opt 输入文件是否存在
            opt_input_path = None # 初始化为 None
            opt_input_exists = False
            for ext in config.VALID_EXTENSIONS:
                f = config.DIRS["opt"] / f"{mol_name}_opt{ext}"
                if f.exists():
                    opt_input_path = f
                    opt_input_exists = True
                    break
            
            # 1.2 如果不存在，从 XYZ 生成
            if not opt_input_exists:
                print(f"✨ [Init] Generating OPT input for {mol_name}")
                try:
                    opt_input_path = opt_gen.generate(xyz_file)
                    action_taken = True
                except Exception as e:
                    print(f"❌ 生成 Opt 失败 {mol_name}: {e}")
                    tracker.finish_task(mol_name, "opt", "ERROR", str(e))
                    continue # 跳过此分子

            # --- [修复 1] ---
            # 经过上面的逻辑，如果生成失败，opt_input_path 依然可能是 None
            # 必须进行检查，否则 IDE 会报错，运行时也会崩溃
            if opt_input_path is None:
                print(f"❌ 严重错误: 无法获取 {mol_name} 的 Opt 输入路径")
                continue

            # 1.3 检查 Opt 运行状态
            opt_out_file = opt_input_path.with_suffix(".out") # 此时 opt_input_path 确保是 Path
            status, err = manager.get_status_from_file(opt_out_file, is_opt=True)
            
            if status == "DONE":
                if tracker.data.get(mol_name, {}).get("opt", {}).get("status") != "DONE":
                     tracker.finish_task(mol_name, "opt", "DONE")
            
            elif status == "ERROR":
                if tracker.data.get(mol_name, {}).get("opt", {}).get("status") != "ERROR":
                    tracker.finish_task(mol_name, "opt", "ERROR", err)
                continue
            
            elif status == "MISSING":
                # --- [修复 2] --- 
                # 这里 opt_input_path 确定不是 None，符合 submit_and_wait 的参数要求
                success = manager.submit_and_wait(opt_input_path, mol_name, "opt")
                action_taken = True
                if not success: continue 
            
            else: # RUNNING
                tracker.start_task(mol_name, "opt")
                continue 

            # =========================================================
            # STAGE 2: Sub-tasks (Gas, Solv, Sp)
            # =========================================================
            
            # 2.1 检查/生成子任务
            sub_tasks = ["gas", "solv", "sp"]
            need_gen_sub = False
            
            for t in sub_tasks:
                found = False
                for ext in config.VALID_EXTENSIONS:
                    if (config.DIRS[t] / f"{mol_name}_{t}{ext}").exists():
                        found = True; break
                if not found: 
                    need_gen_sub = True; break
            
            if need_gen_sub:
                try:
                    parser = get_parser(opt_out_file)
                    q, m = parser.get_charge_mult() 
                    final_coords = parser.get_coordinates()
                    
                    sub_gen.generate_all(mol_name, q, m, final_coords)
                    action_taken = True
                except Exception as e:
                    print(f"❌ 生成子任务失败 {mol_name}: {e}")
                    tracker.finish_task(mol_name, "opt", "ERROR", f"SubGen Failed: {e}")
                    continue

            # 2.2 运行子任务
            group_failed = False
            for t in sub_tasks:
                job_in = None
                for ext in config.VALID_EXTENSIONS:
                    f = config.DIRS[t] / f"{mol_name}_{t}{ext}"
                    if f.exists(): job_in = f; break
                
                # 如果找不到输入文件，说明上面生成步骤有问题
                if job_in is None:
                    print(f"⚠️ 找不到输入文件 {mol_name}_{t}")
                    group_failed = True; break

                st, er = manager.get_status_from_file(job_in.with_suffix(".out"))
                
                if st == "DONE":
                    if tracker.data.get(mol_name, {}).get(t, {}).get("status") != "DONE":
                        tracker.finish_task(mol_name, t, "DONE")
                    continue 
                
                elif st == "ERROR":
                    if tracker.data.get(mol_name, {}).get(t, {}).get("status") != "ERROR":
                        tracker.finish_task(mol_name, t, "ERROR", er)
                    group_failed = True; break 
                
                elif st == "MISSING":
                    # job_in 确定不为 None
                    success = manager.submit_and_wait(job_in, mol_name, t)
                    action_taken = True
                    if not success: 
                        group_failed = True; break
                
                else: # RUNNING
                    tracker.start_task(mol_name, t)
                    group_failed = True; break 
            
            if group_failed: continue

            # =========================================================
            # STAGE 3: Final Calculation
            # =========================================================
            
            try:
                energies = {}
                energies['thermal_corr'] = get_parser(opt_out_file).get_thermal_correction()
                
                for t in sub_tasks:
                    job_out = None
                    for ext in [".out", ".log"]:
                         f = config.DIRS[t] / f"{mol_name}_{t}{ext}"
                         if f.exists(): job_out = f; break
                    
                    # --- [修复 3] ---
                    # 必须检查 job_out 是否为 None
                    if job_out is None:
                        raise FileNotFoundError(f"Output file missing for {t}")

                    energies[t] = get_parser(job_out).get_electronic_energy()
                
                res = ThermodynamicsCalculator.calculate_g(energies, mol_name)
                
                print(f"🎉 {mol_name} G_Final = {res['G_Final (kcal)']:.2f} kcal/mol")
                
            except Exception as e:
                # 可能是还没有全部算完，或者解析出错
                # 暂时 pass，等待下一次循环再次尝试
                pass

            if action_taken:
                break 
        
        if not action_taken:
            print("💤 所有任务暂无更新，等待 60s 扫描新文件...")
            time.sleep(60)

if __name__ == "__main__":
    main()