from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Static
from textual.containers import Container
from textual import work
from typing import List

class GibbsApp(App):
    """一个现代化的 Btop 风格终端界面"""
    
    CSS = """
    DataTable {
        height: 1fr;
        border: solid green;
    }
    #status_bar {
        height: 1;
        background: $primary;
        color: white;
        padding-left: 1;
    }
    """
    
    # 新增按键绑定 S -> stop_task
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "stop_task", "Stop Current Task")
    ]

    def __init__(self, workflow_func, tracker, job_manager):
        super().__init__()
        self.workflow_func = workflow_func
        self.tracker = tracker
        self.job_manager = job_manager # 持有引用
        self.processed_mols = set()
        self.col_keys = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DataTable(zebra_stripes=True)
        yield Static(id="status_bar", content="Initializing...")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        self.col_keys = table.add_columns("MOLECULE", "OPT", "GAS", "SOLV", "SP", "G(kcal)")
        
        self.set_interval(0.5, self.update_table)
        self.run_workflow()

    @work(thread=True)
    def run_workflow(self):
        self.workflow_func()
        
    def action_stop_task(self):
        """响应 S 键：停止当前任务"""
        self.job_manager.stop_current_job()
        self.query_one("#status_bar", Static).update("⚠️ Sending Kill Signal...")

    def update_table(self):
        table = self.query_one(DataTable)
        status_bar = self.query_one("#status_bar", Static)
        status_bar.update(f"⏳ {self.tracker.current_msg}")

        data = self.tracker.data
        order = self.tracker.xyz_order
        
        # 1. 主任务列表
        if not order:
            mains = sorted([k for k in data.keys() if not k.startswith("[Extra]")])
        else:
            mains = order
            
        # 2. 清扫模式任务列表 (Extra Jobs)
        extras = sorted([k for k in data.keys() if k.startswith("[Extra]")])

        # 合并列表：先显示主任务，再显示清扫任务
        all_tasks = mains + extras

        for mol in all_tasks:
            mol_info = data.get(mol, {})
            
            # Mol Name 处理
            if mol.startswith("[Extra]"):
                # 清扫模式任务特殊显示
                clean_name = mol.replace("[Extra]", "")
                mol_disp = f"[magenta]🧹 {clean_name}[/]"
            elif mol_info.get("xyz_missing"):
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
                # 只有 Opt 完成了或者是清扫模式(其目录结构可能不同，但这里复用显示逻辑)
                if not is_opt_ok and opt.get("status") != "RUNNING" and not mol.startswith("[Extra]"):
                    cells.append("[dim]-[/dim]")
                else:
                    cells.append(self._fmt_status(mol_info.get(step, {})))
            
            # Result
            res = mol_info.get("result_g")
            cells.append(f"[bold white]{res:.2f}[/]" if res else "")

            row_key = mol 
            if row_key in self.processed_mols:
                # 更新行
                for col_idx, content in enumerate(cells):
                    if col_idx < len(self.col_keys):
                        table.update_cell(row_key, self.col_keys[col_idx], content)
            else:
                # 添加新行
                table.add_row(*cells, key=row_key)
                self.processed_mols.add(row_key)

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