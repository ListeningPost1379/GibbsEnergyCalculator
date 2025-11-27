# 🐶 狗都会用的量子化学吉布斯自由能计算脚本
**(Automated Gibbs Free Energy Workflow)**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Manager](https://img.shields.io/badge/uv-enabled-purple)](https://github.com/astral-sh/uv)
[![Status](https://img.shields.io/badge/Status-Stable-green)](https://github.com/)

> **核心理念**：把 `.xyz` 扔进去，把 $\Delta G$ 拿出来。中间发生了什么？你不必知道，脚本会搞定一切。

---

## ✨ 核心功能

* **全自动流水线**：`XYZ` $\rightarrow$ `Opt` $\rightarrow$ `SP/Gas/Solv` $\rightarrow$ `Gibbs Free Energy`。
* **双核驱动**：同时支持 **Gaussian 16** 和 **ORCA 5.x**，混用也没问题（比如用 Gaussian 优化，ORCA 算单点）。
* **智能阻塞调度**：专为资源受限的节点设计。一个任务算完才提交下一个，不挤爆队列，不浪费机时。
* **断点续传**：脚本挂了？服务器重启了？没关系，重启脚本后自动检测已完成的任务，绝不重复计算。
* **动态插队**：中途想加个新分子？直接把 `.xyz` 扔进文件夹，脚本跑完当前任务立刻优先处理新来的。
* **炫彩仪表盘**：实时显示的彩色面板，任务状态（RUNNING/DONE/ERROR）一目了然。

---

## 📂 目录结构 (这很重要)

你的项目目录应该长这样，脚本会自动维护 `data/` 目录：

```text
GibbsEnergy/
├── xyz/                <-- [投料口] 把你的 .xyz 文件扔这就行
├── templates/          <-- [模具间] 存放 .gjf 或 .inp 模板文件
├── data/               <-- [产物区] 自动生成，里面是分门别类的计算文件
│   ├── opt/            # 结构优化任务
│   ├── sp/             # 高精度单点能
│   ├── gas/            # 气相校正
│   └── solv/           # 液相校正
├── src/                <-- [核心代码] 没事别动它
├── main.py             <-- [启动器] 双击(或者命令行)运行它
├── pyproject.toml      <-- [配置] 项目依赖管理
└── run.sh              <-- [脚本] 服务器后台运行脚本
```

---

## 🚀 傻瓜式用法 (Quick Start)

### 1. 环境准备
确保服务器安装了 `uv` (一个极速 Python 包管理器)。
```bash
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh
```

### 2. 准备模板 (Templates)
在 `templates/` 目录下放入你的计算模板。文件名必须固定，后缀决定调用哪个软件（`.gjf` -> Gaussian, `.inp` -> ORCA）。

**必需的四个模板：**
* `opt.gjf` (结构优化)
* `sp.gjf` (高精度单点)
* `gas.gjf` (气相低精度单点)
* `solv.gjf` (液相溶剂化能)

**模板规则 (必须包含以下占位符)：**
* `[NAME]`: 会被替换为任务名
* `[Charge]`: 会被替换为电荷
* `[Multiplicity]`: 会被替换为多重度
* `[GEOMETRY]`: 会被替换为坐标

> **示例 (opt.gjf):**
> ```text
> %chk=[NAME].chk
> #p M062X/6-31G(d) opt freq
> 
> Title: [NAME] optimization
> 
> [Charge] [Multiplicity]
> [GEOMETRY]
> 
> ```

### 3. 准备原料 (XYZ)
在 `xyz/` 目录下放入 `.xyz` 文件。
**注意：第二行必须写明电荷和多重度！**

> **示例 (h2o.xyz):**
> ```text
> 3
> Charge = 0 Multiplicity = 1  <-- 这一行非常重要！！
> O       0.00000000      0.00000000      0.00000000
> H       0.75860200      0.00000000      0.50428400
> H       0.75860200      0.00000000     -0.50428400
> ```

### 4. 启动！
```bash
# 赋予运行权限
chmod +x run.sh

# 后台启动 (推荐，防止断网)
./run.sh

# 或者直接前台运行看效果
uv run main.py
```

然后你就可以去喝咖啡了 ☕️。

---

## ⚙️ 高级配置

打开 `src/config.py` 可以修改核心设置：

1.  **修改运行命令** (`COMMAND_MAP`)：
    * 默认是 `g16 < {input} > {output}`。
    * 如果你用 Slurm，可以改成 `sbatch {input}`。
    * 如果你用 ORCA，记得改成绝对路径 `/opt/orca/orca {input} > {output}`。

2.  **特殊物种校正** (`_SPECIAL_CORRECTIONS_KCAL`)：
    * 默认标准态校正为 1.89 kcal/mol (1 atm $\to$ 1 M)。
    * 如果是纯溶剂水 (`h2o`)，可能需要其他校正值。

---

## 📊 仪表盘图例

脚本运行时会显示如下面板：

| 状态 | 颜色 | 含义 |
| :--- | :--- | :--- |
| **[PENDING]** | 灰色 | 排队中，还没轮到它 |
| **[RUNNING]** | 🟨 黄色 | 正在玩命计算中，请勿打扰 |
| **[DONE 2h]** | 🟩 绿色 | 算完了，耗时 2 小时 |
| **[ERROR]** | 🟥 红色 | 报错了 (收敛失败/格式错误)，详情看下方日志 |

---

## 🛠 常见问题 (Q&A)

**Q: 我想加个新分子怎么办？**
A: 直接把新的 `.xyz` 文件扔进 `xyz/` 目录。脚本会在跑完当前这一步后，立刻发现新文件，并根据修改时间优先处理它。

**Q: 任务算错了，我想重算怎么办？**
A: 删掉 `data/` 对应子目录下生成的 `.out` 或 `.log` 文件，脚本下一次扫描时会发现它是 MISSING 或 ERROR，然后自动重新提交。

**Q: 为什么我的 ORCA 任务没跑？**
A: 检查 `config.py` 里的 ORCA 路径是否正确，以及 `templates/` 下是否有对应的 `.inp` 模板。

---

## ⚖️ 免责声明
* 本脚本计算结果仅供参考，发表文章前请务必人工核对关键数据。
* 机时宝贵，请确认模板基组和泛函设置正确后再批量运行。

**(C) 2025 Listener1379**