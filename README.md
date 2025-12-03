# ⚗️ Automated Gibbs Free Energy Workflow
### (自动化吉布斯自由能计算工作流)

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Manager](https://img.shields.io/badge/uv-enabled-purple)](https://github.com/astral-sh/uv)
[![UI](https://img.shields.io/badge/Textual-TUI-green)](https://textual.textualize.io/)

> **核心理念**：把 `.xyz` 分子文件扔进去，脚本自动吐出 $\Delta G$ 数据。
> 这是一个专为计算化学家设计的“挂机神器”，支持断点续传、自动纠错、资源调度和实时监控。

---

## ✨ 核心功能 (Features)

* **全自动流水线 (Auto-Pipeline)**：
    * 自动执行 `XYZ` $\rightarrow$ `Opt` (优化) $\rightarrow$ `Gas/Solv/SP` (子任务) $\rightarrow$ `Gibbs Calculation` 流程。
    * 自动生成输入文件，无需手动编辑坐标。
* **双引擎支持 (Dual Engine)**：
    * 完美兼容 **Gaussian 16** (`.gjf`) 和 **ORCA 5.x** (`.inp`)。
    * 支持混合使用（例如：用 Gaussian 做优化，用 ORCA 算高精度单点能）。
* **清扫模式 (Sweeper Mode)** [NEW]：
    * 主线任务跑完了？脚本不会闲着。
    * 将独立的计算任务扔进 `extra_jobs/` 目录，脚本会在空闲时自动扫描并运行它们。
* **智能调度 (Smart Scheduling)**：
    * **阻塞式运行**：一个任务算完才提交下一个，避免挤爆服务器队列或内存。
    * **动态插队**：随时添加新的 `.xyz` 文件，脚本会自动发现并优先处理。
* **数据持久化**：
    * 计算结果自动汇总写入 `results.csv`，告别手动抄数据的痛苦。
* **现代化 TUI 界面**：
    * 基于 Textual 的终端界面，实时展示主线任务进度和清扫任务状态。

---

## 📂 目录结构 (Directory Structure)

项目运行后会自动维护以下结构，请确保 `templates` 和 `xyz` 目录已准备好：

```text
GibbsEnergy/
├── xyz/                <-- [投料口] 放入你的 .xyz 分子结构文件
├── templates/          <-- [模具间] 存放 .gjf 或 .inp 计算模板 (核心配置)
├── extra_jobs/         <-- [清扫区] 存放不属于主线的独立计算任务 (如额外的单点)
├── data/               <-- [产物区] 脚本自动生成，请勿手动混乱修改
│   ├── opt/            # 结构优化任务文件
│   ├── sp/             # 高精度单点能文件
│   ├── gas/            # 气相校正文件
│   └── solv/           # 液相校正文件
├── results.csv         <-- [结果表] 最终计算出的吉布斯自由能汇总表
├── src/                <-- [源代码] 核心逻辑
├── main.py             <-- [启动器] 程序入口
└── run.sh              <-- [脚本] 推荐使用此脚本启动
```

---

## 🚀 快速开始 (Quick Start)

### 1. 环境安装
本项目使用 `uv` 进行极速依赖管理（如果没有 `uv`，请先安装：`curl -LsSf https://astral.sh/uv/install.sh | sh`）。

```bash
# 克隆项目后，在项目根目录执行：
chmod +x run.sh
```

### 2. 准备计算模板 (Templates)
在 `templates/` 文件夹中放入你的输入文件模板。脚本会根据后缀名自动判断调用哪个程序（`.gjf` -> Gaussian, `.inp` -> ORCA）。

**必须包含的 4 个模板：**
* `opt.gjf` 或 `opt.inp` (结构优化)
* `sp.gjf` 或 `sp.inp` (高精度单点能)
* `gas.gjf` 或 `gas.inp` (气相热力学校正)
* `solv.gjf` 或 `solv.inp` (液相溶剂化能)

**⚠️ 模板占位符规则 (必须严格遵守)：**
脚本通过替换以下关键词来生成输入文件：
* `[NAME]`: 任务名称
* `[Charge]`: 电荷
* `[Multiplicity]`: 自旋多重度
* `[GEOMETRY]`: 分子坐标部分

> **Gaussian 模板示例 (`templates/opt.gjf`):**
> ```text
> %chk=[NAME].chk
> %nprocshared=16
> %mem=32GB
> #p M062X/6-31G(d) opt freq
>
> Title: [NAME] optimization
>
> [Charge] [Multiplicity]
> [GEOMETRY]
>
> ```

### 3. 准备分子文件 (XYZ)
将 `.xyz` 文件放入 `xyz/` 目录。
**注意：XYZ 文件的第二行注释行必须包含 `Charge` 和 `Multiplicity` 信息！**

> **示例 (`xyz/test_mol.xyz`):**
> ```text
> 3
> Charge = 0 Multiplicity = 1    <-- 脚本通过正则读取这一行
> O       0.00000000      0.00000000      0.00000000
> H       0.75860200      0.00000000      0.50428400
> H       0.75860200      0.00000000     -0.50428400
> ```

### 4. 启动运行
```bash
# 方式一：后台运行 (推荐，防止断网中断，日志在 workflow.log)
./run.sh

# 方式二：前台运行 (可以直接看到 TUI 界面)
uv run main.py
```

---

## 🧹 清扫模式 (Sweeper Mode)

有时候你可能想算一些与主线流程无关的任务（比如某个分子的特殊基组单点，或者手动测试一个输入文件）。

1.  直接将写好的输入文件（`.gjf` 或 `.inp`）放入 `extra_jobs/` 文件夹。
2.  脚本会在主线任务（XYZ 流程）全部完成或暂时无事可做时，**自动扫描并运行**该文件夹下的任务。
3.  状态会显示在 TUI 界面的下半部分 "Sweeper Tasks" 面板中。

---

## 📊 结果输出 (Output)

当一个分子的所有步骤 (`opt` -> `gas`, `solv`, `sp`) 都完成后，脚本会自动计算吉布斯自由能：

$$G_{final} = E_{sp} + G_{corr} + \Delta G_{solv} + \Delta G_{conc}$$

结果会追加写入根目录下的 `results.csv`：

| Molecule | G_Final (kcal/mol) | E_SP (Ha) | E_Gas (Ha) | ... |
| :--- | :--- | :--- | :--- | :--- |
| test_mol | -12345.67 | -100.123 | -100.120 | ... |

---

## ⚙️ 高级配置 (Configuration)

编辑 `src/config.py` 可修改核心参数：

* **程序路径与命令** (`COMMAND_MAP`)：
    * 修改调用 Gaussian 或 ORCA 的具体命令（例如改为 `sbatch` 提交作业）。
    * 默认：
        * `.gjf`: `g09 < {input} > {output}`
        * `.inp`: `/usr/local/quantum/orca/orca {input} > {output}`
* **浓度校正** (`_DG_CONC_KCAL`)：
    * 默认校正值为 1.89 kcal/mol (1 atm -> 1 M)。
* **特殊溶剂校正** (`_SPECIAL_CORRECTIONS_KCAL`)：
    * 针对特定分子（如水分子的气液相变标准态不同）进行特殊处理。

---

## ⌨️ 快捷键 (Shortcuts)

在 TUI 界面中：
* `q`: 安全退出程序（会尝试停止当前正在运行的子进程）。
* `s`: 强制停止当前正在运行的任务（Kill Process）。

---

## ⚠️ 注意事项

1.  **文件名规范**：尽量使用英文、数字和下划线命名 `.xyz` 文件，避免特殊字符。
2.  **错误处理**：如果某个任务显示 `[ERROR]`，请检查 `data/` 对应目录下的 `.out` 或 `.log` 文件。修复问题后，**只需删除该报错的输出文件**，脚本在下一轮扫描时会自动检测到“文件缺失”并重新提交计算。
3.  **Orca 并行**：如果使用 ORCA 并行计算，请确保在模板中正确书写 `%pal nprocs ... end`，并在 `config.py` 的命令中无需额外修改。

---

**(C) 2025 Automated Gibbs Workflow Project**