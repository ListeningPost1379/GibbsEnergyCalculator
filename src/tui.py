from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Static, Label
from textual.containers import Container
from textual import work
from typing import List
import threading

class GibbsApp(App):
    """一个现代化的 Btop 风格终端界面"""
    
    CSS = """
    DataTable {
        height: 1fr;
        border: solid green;
    }
    Label {
        background: $boost;
        color: auto;
        padding: 0 1;
        width: 100%;
        text-align: center;
        text-style: bold;
    }
    #status_bar {
        height: 1;
        background: $primary;
        color: white;
        padding-left: 1;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "stop_task", "Stop Current Task")
    ]

    def __init__(self, workflow_func, tracker, job_manager, stop_event):
        super().__init__()
        self.workflow_func = workflow_func
        self.tracker = tracker
        self.job_manager = job_manager
        self.stop_event = stop_event
        # 使用两个集合分别记录已添加到界面的行
        self.processed_mains = set()
        self.processed_sweeps = set()
        self.main_col_keys = []
        self.sweep_col_keys = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        # 上半部分：主流程
        yield Label("🔹 Main Workflow (Gibbs Energy)")
        yield DataTable(id="main_table", zebra_stripes=True)
        
        # 下半部分：清扫模式
        yield Label("🧹 Sweeper Tasks (Extra Jobs)")
        yield DataTable(id="sweep_table", zebra_stripes=True)
        
        yield Static(id="status_bar", content="Initializing...")
        yield Footer()

    def on_mount(self) -> None:
        # 1. 设置主表 (Main)
        main_table = self.query_one("#main_table", DataTable)
        main_table.cursor_type = "row"
        self.main_col_keys = main_table.add_columns("MOLECULE", "OPT", "GAS", "SOLV", "SP", "G(kcal)")
        
        # 2. 设置清扫表 (Sweeper) - 列更通用
        sweep_table = self.query_one("#sweep_table", DataTable)
        sweep_table.cursor_type = "row"
        self.sweep_col_keys = sweep_table.add_columns("JOB NAME", "STEP", "STATUS", "DURATION", "INFO")
        
        # 设置定时器，每 0.5 秒调用 self.update_table
        self.set_interval(0.5, self.update_table)
        self.run_workflow()

    @work(thread=True)
    def run_workflow(self):
        self.workflow_func()
        
    def action_stop_task(self):
        self.job_manager.stop_current_job()
        self.query_one("#status_bar", Static).update("⚠️ Sending Kill Signal...")

    # --- 最终修复：保持 async 以匹配父类，但去掉 await 因为 exit() 是同步的 ---
    async def action_quit(self):
        if self.stop_event:
            self.stop_event.set()
        self.job_manager.stop_current_job()
        self.exit()  # 这里不要加 await

    def update_table(self):
        main_table = self.query_one("#main_table", DataTable)
        sweep_table = self.query_one("#sweep_table", DataTable)
        status_bar = self.query_one("#status_bar", Static)
        
        status_bar.update(f"⏳ {self.tracker.current_msg}")

        data = self.tracker.data
        
        # === 1. 更新主表 (Main Table) ===
        order = self.tracker.xyz_order
        if not order:
            mains = sorted([k for k in data.keys() if not k.startswith("[Extra]")])
        else:
            mains = order 

        for mol in mains:
            mol_info = data.get(mol, {})
            
            if mol_info.get("xyz_missing"):
                mol_disp = f"[red][X] {mol}[/red]"
            else:
                mol_disp = f"[cyan]{mol}[/cyan]"

            cells = [mol_disp]
            
            # OPT
            opt = mol_info.get("opt", {})
            cells.append(self._fmt_status(opt))
            
            # SUBS
            is_opt_ok = (opt.get("status") == "DONE")
            for step in ["gas", "solv", "sp"]:
                if not is_opt_ok and opt.get("status") != "RUNNING":
                    cells.append("[dim]-[/dim]")
                else:
                    cells.append(self._fmt_status(mol_info.get(step, {})))
            
            # Result
            res = mol_info.get("result_g")
            cells.append(f"[bold white]{res:.2f}[/]" if res else "")

            row_key = mol
            if row_key in self.processed_mains:
                for col_idx, content in enumerate(cells):
                    if col_idx < len(self.main_col_keys):
                        main_table.update_cell(row_key, self.main_col_keys[col_idx], content)
            else:
                main_table.add_row(*cells, key=row_key)
                self.processed_mains.add(row_key)

        # === 2. 更新清扫表 (Sweep Table) ===
        extras = sorted([k for k in data.keys() if k.startswith("[Extra]")])
        
        for mol in extras:
            mol_info = data.get(mol, {})
            clean_name = mol.replace("[Extra]", "")
            
            for step, info in mol_info.items():
                if step in ["xyz_missing", "result_g"]: continue
                if not isinstance(info, dict): continue
                
                row_key = f"{mol}::{step}"
                
                status_str = self._fmt_status(info)
                dur = info.get("duration_str", "")
                err = info.get("error", "")
                
                cells = [
                    f"[magenta]{clean_name}[/]", 
                    step, 
                    status_str, 
                    dur, 
                    f"[red]{err}[/]" if err else ""
                ]

                if row_key in self.processed_sweeps:
                    for col_idx, content in enumerate(cells):
                        if col_idx < len(self.sweep_col_keys):
                            sweep_table.update_cell(row_key, self.sweep_col_keys[col_idx], content)
                else:
                    sweep_table.add_row(*cells, key=row_key)
                    self.processed_sweeps.add(row_key)

    def _fmt_status(self, info):
        st = info.get("status", "PENDING")
        dur = info.get("duration_str", "")
        err = info.get("error", "")
        
        if st == "DONE": return f"[green]DONE {dur}[/]"
        if st == "RUNNING": return f"[yellow]RUNNING...[/]"
        if st.startswith("ERR") or st == "ERROR":
            disp = f"{st}: {err}" if err else st
            return f"[red]{disp}[/]"
        return "[dim]PENDING[/]"