# 📐 上海物理等级考智能命题助手

> 让 AI 自动命制符合**上海物理等级考**风格的试题 · 一次上传/描述，生成可直接打印的 **HTML 试卷**。

基于 Streamlit 构建的本地 Web 应用：描述一个情境或上传资料（图片 / PDF / Word / 文本），
双提供商（Claude · DeepSeek）即可生成格式规范、公式用 **MathJax** 渲染的完整试卷，
浏览器 `Ctrl+P` 直接另存为 PDF。内置 **141 子考点考纲库**、**双向细目表结构化校验**、
**缺考点自动补题**、**SQLite 题库**与**出题历史**，并提供多轮对话改题与新旧版源码级比对。

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)]()

---

## ✨ 功能亮点

| 页面 | 功能 |
|------|------|
| **命题** | 描述情境 / 上传资料 → 生成试卷；生成后展示**细目表校验**（考点合法性 / 重复 / 必考点覆盖 / 分值 / 难度顺序）；完整卷可**勾选未覆盖必考点补题**（自动合并进原卷或独立成页） |
| **题目修改** | 出完题后与 AI **多轮对话改题**：在原卷基础上做最小修改，每轮输出新版本，并给出**新旧版源码级比对**（difflib 红绿标注），各版本可独立下载 |
| **题库** | 题目的新增 / 编辑 / 删除 / 检索（题型 / 难度 / 状态 / 考点 / 关键词）、分页浏览、JSON 导入导出 |
| **题目校对** | 校对状态机：草稿 → 已审核 → 已定稿 / 驳回 |
| **考纲对标** | 141 子考点覆盖总览 + 考纲-题目映射总表 + 薄弱考点（收录 <2 题）一键去命题页补题 |
| **出题历史** | 最近 50 次生成记录，可重开落盘 HTML、查看细目表 JSON |
| **设置** | 关于 / 版本、题库数据维护、**考点库在线编辑**（改考点 / 难度 / 是否必考，写回 JSON 并自动备份）、命题规范只读预览 |

### 命题输入支持

- **情境描述**：自然语言描述想考的知识点 / 情境
- **上传资料**：图片（jpg/png/gif/webp，直接发给视觉模型）、PDF（≤10 页）、Word、txt/md（超 6000 字符自动截断）
- **题型多选**：单选 / 多选 / 填空 / 计算 / 论证简答
- **两种规模**：1 道大题（3-5 小题）或完整试卷（6 道大题，满分 100）

> ⚠️ **配图说明**：AI 生成的物理示意图为**示意性草稿**，箭头方向 / 标注文字 / 线条粗细可能不准，请按实际物理情境核对调整。绘图模板见 `绘图参考/drawing_prompts.md`，程序化出图见 `绘图脚本/generate_physics_diagram.py`。

> 💡 **概念辨析说明**：命制「概念辨析题」「开放论证题」时，可参考 `概念辨析/concept-pitfalls.md`（易错概念辨析·命题陷阱库，源自 enjoyphysics.cn 疑难解析栏目约 260 篇蒸馏）。命题规范已内置高频易错点与命题红线（如弃用「光滑平面」「滚动摩擦」）。

---

## 🚀 快速开始（3 步）

### 1. 安装依赖（只需一次）

建议先创建虚拟环境（Windows）：

```bat
cd 物理命题助手
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

依赖：`streamlit`、`anthropic`、`pypdf`、`python-docx`、`pytest`（测试用）。

### 2. 获取 API 密钥

- **Claude**：<https://console.anthropic.com> → API Keys → Create Key（形如 `sk-ant-xxx`）
- **DeepSeek**：<https://platform.deepseek.com> → API Keys（价格便宜、国内直连，文本模型）

密钥按需填入侧边栏（**BYOK 模式，密钥只存于你本地会话，不落盘**）。

### 3. 运行程序

```bat
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`。

---

## 🧠 工作原理

```
你在页面选参数 / 描述情境 / 上传资料
        ↓
engine/builder 组装 user_text + engine/prompts 的命题规范（唯一真源）
        ↓
engine/provider 调用 Claude（视觉）或 DeepSeek（文本）
        ↓
AI 输出 HTML + 末尾细目表 JSON 注释块
        ↓
engine/validator 校验细目表 → 展示结果；strip 注释块后落盘 试卷_*.html
        ↓
题库 / 历史写入 SQLite（data/physics_assistant.db）
```

**命题规范**（`engine/prompts.py`）是把命题经验写成 system prompt：情境化命题、大题内考点不重复、
由易到难、两阶段配图工作流、细目表结构化 JSON 输出等——这是本项目最核心的"资产"之一。

---

## 📁 目录结构

```
物理命题助手/
├── app.py                  # 入口（sidebar.radio 分发 7 个页面）
├── engine/                 # 命题引擎（不 import streamlit，可单测）
│   ├── prompts.py          #   命题规范唯一真源 + 完整性自检
│   ├── builder.py          #   文件解析/截断/文本组装/HTML清理/补题合并
│   ├── provider.py         #   Claude / DeepSeek 适配层
│   └── validator.py        #   双向细目表 JSON 提取/校验/覆盖分析
├── question_bank/          # SQLite 题库
│   ├── models.py           #   Question/ExamRecord/QuestionFilter
│   ├── storage.py          #   建表 SQL + CRUD + 检索 + 历史
│   └── io_utils.py         #   JSON 导入导出
├── knowledge/              # 考纲考点库
│   ├── points.py           #   KnowledgeBase 加载/查询/校验/持久化
│   └── data/gaokao_knowledge.json   # 6模块/28大考点/141子考点
├── diagram/generator.py    # 程序化示意图懒加载包装
├── ui/                     # Streamlit 界面层（唯一依赖 streamlit）
│   ├── app_state.py        #   session_state 封装 + DB 懒加载
│   ├── pages_prop.py       #   命题页
│   ├── pages_revise.py     #   题目修改页（对话改题 + 新旧版比对）
│   ├── pages_bank.py       #   题库页
│   ├── pages_review.py     #   题目校对页
│   ├── pages_kaogang.py    #   考纲对标页
│   ├── pages_history.py    #   出题历史页
│   └── pages_settings.py   #   设置页
├── tests/                  # pytest（不触网，provider 全 mock）
├── scripts/                # count_loc / check_prompt_sync
├── docs/软件说明书_骨架.md  # 软著说明书素材
├── 绘图参考/drawing_prompts.md
├── 绘图脚本/generate_physics_diagram.py
├── 概念辨析/concept-pitfalls.md   # 易错概念辨析·命题陷阱库（出概念辨析/论证题取材）
└── index.html              # 网页版（保留现状，命题规范副本已同步）
```

生成的 `试卷_*.html`、`补题_*.html` 与 `data/*.db` 均已在 `.gitignore` 中忽略。

---

## ✅ 测试与校验

```bat
pytest tests/ -q
```

- **不触网**：provider 网络调用全部 mock
- **覆盖**：文件解析、文本组装、双提供商（含多轮对话）、考点库、SQLite CRUD、细目表校验、覆盖分析、补题合并、改题组装 / 新旧版 diff、JS 转义往返

```bat
python scripts/check_prompt_sync.py        # 校验 index.html 与 prompts.py 命题规范同步
python scripts/check_prompt_sync.py --fix  # 用真源覆盖 index.html 副本
python scripts/count_loc.py                # 软著代码量统计（≈3700 行）
```

---

## 🌐 外部资源链接

侧边栏提供两个直通外部资源库的链接：

- **📚 物含妙理 · 物理题库**：<https://enjoyphysics.cn/Tiku>
- **🗄️ EduVault 数字资源库**：<https://linkium.mtszedu.com/replix-db/>

---

## ❓ 常见问题

**Q1：浏览器没自动打开？** 手动访问 `http://localhost:8501`。

**Q2：提示「API 密钥无效」？** 检查密钥是否完整、有无空格；DeepSeek 需在平台创建 Key。

**Q3：生成失败 / 超时？** 首次调用较慢属正常（30~60 秒）；网络受限时换 DeepSeek（国内直连）。

**Q4：生成的试卷能打印成 PDF 吗？** 可以：下载 HTML → 浏览器打开 → `Ctrl+P` → 目标打印机选「另存为 PDF」。

**Q5：修改命题规范？** 编辑 `engine/prompts.py` 的 `命题规范`（保持 6 个规则块标题完整），然后 `python scripts/check_prompt_sync.py --fix` 同步网页版副本。

**Q6：题库数据存在哪？** `data/physics_assistant.db`（SQLite）。题库页可导出 JSON 备份。

---

## 🔬 技术说明

- 分层设计：**引擎 / 存储层不依赖 streamlit**，便于单独测试、复用与展示
- 双提供商适配层：Claude（视觉 / 多模态）与 DeepSeek（文本 / 国内直连）可在侧边栏切换
- 完整试卷末尾自动追加**结构化双向细目表 JSON 注释块**，保存前剥离，保证打印稿干净
- 源代码约 **3,700 行**（业务代码 + 测试/脚本），`scripts/count_loc.py` 输出明细
- 申请软著材料骨架见 `docs/软件说明书_骨架.md`

---

## 📄 许可证

本项目尚未附带许可证文件。若用于开源发布，建议在根目录补充一个 `LICENSE`（例如 [MIT](https://choosealicense.com/licenses/mit/)）。

<a href="https://github.com/your-username/physics-exam-assistant">⭐ Star</a> · <a href="https://github.com/your-username/physics-exam-assistant/issues">Report Bug</a>
