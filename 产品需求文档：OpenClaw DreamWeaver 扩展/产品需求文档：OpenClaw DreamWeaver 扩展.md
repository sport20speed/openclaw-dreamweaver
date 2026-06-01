# 产品需求文档：OpenClaw DreamWeaver 扩展

**项目名称：** OpenClaw DreamWeaver — 基于 OpenClaw 的梦境自主进化引擎  
**版本：** 1.0  
**日期：** 2026-06-01  
**作者：** DreamWeaver 改造团队  
**文档状态：** 草案  
**基础项目：** OpenClaw (开源桌面 AI Agent 框架)  
**改造目标：** 为其注入“梦境”机制，实现离线自主创新与本地知识库深度同步

---

## 目录
1. [引言与背景](#1-引言与背景)
2. [产品愿景与目标](#2-产品愿景与目标)
3. [OpenClaw 现状分析](#3-openclaw-现状分析)
4. [改造范围与原则](#4-改造范围与原则)
5. [系统架构设计](#5-系统架构设计)
6. [功能需求详述](#6-功能需求详述)
7. [数据模型与存储设计](#7-数据模型与存储设计)
8. [接口与集成规范](#8-接口与集成规范)
9. [用户体验设计](#9-用户体验设计)
10. [非功能需求](#10-非功能需求)
11. [开发与部署路线图](#11-开发与部署路线图)
12. [风险评估与缓解](#12-风险评估与缓解)
13. [附录](#13-附录)

---

## 1. 引言与背景

### 1.1 项目来源
桌面 AI Agent 领域已涌现出多个优秀开源项目，如 OpenClaw、CodeWhale、Reasonix 等，它们解决了任务执行、工具调用、多步规划等通用痛点。但无一例外，这些项目仅工作在 **“按需响应”** 模式——用户下达指令，Agent 执行并返回结果，随即进入休眠。这种模式难以实现真正的智能伴生与主动增值。

DreamWeaver 改造计划瞄准这一空白：将一个 **“自我对弈进化引擎”** 无缝嵌入成熟开源 Agent 框架，使其在用户空闲时自动进入“梦境”状态，生成超前解决方案并沉淀为本地知识资产。OpenClaw 因其优秀的模块化架构、本地优先的设计哲学和活跃的社区，被选为首个改造基座。

### 1.2 核心痛点
- **Agent 无法主动成长：** 现有 Agent 只能在被调用时发挥智能，闲置时间完全浪费。
- **创意生成与用户脱节：** 现有方案生成工具仅能根据明确提示词输出内容，无法围绕用户真实困境进行长时间、多轮自我批判式创新。
- **知识无法闭环：** 用户使用 Agent 后产生的宝贵思路、问题和解决方案散落在对话日志中，未能形成结构化、可检索、可关联的长期记忆，更无法反哺 Agent 自身。

### 1.3 解决方案概述
通过在 OpenClaw 中植入 **Dream Service（梦境服务）** 守护进程，监听用户空闲事件，自动启动强化学习式自我对弈，产出创新方案并写入用户的 Obsidian Vault 及本地向量数据库。改造遵循 **“最小侵入、最大增益”** 原则，力求上游代码影响最小化。

---

## 2. 产品愿景与目标

### 2.1 产品愿景
让每一个使用 OpenClaw 的用户都拥有一个“苏醒时高效执行，沉睡时自主进化”的共生智能体。它不仅是你的手和眼，更是你的第二大脑，在你休息时为你构思超越现有认知的解决方案。

### 2.2 量化目标
- **梦境自主触发率：** 用户空闲状态检测准确率 > 95%，误判时用户打断响应时间 < 1 秒。
- **方案产出质量：** 单次梦境平均迭代 100 轮以上，最终方案批判性评分 ≥ 8.5/10（由内置 Judge 模型给出），用户手动标记“高价值”的梦境比例 > 30%。
- **知识库整合：** 所有梦境结果 100% 自动写入 Obsidian Vault 指定目录，并完成双向链接；向量数据库入库延迟 < 5 秒。
- **系统资源影响：** 梦境运行期间，不影响用户前台正常使用 OpenClaw（若用户返回）；CPU/GPU 占用峰值可控，内存增量 ≤ 500MB。
- **兼容性：** 对 OpenClaw 原有功能零破坏，所有原有 API 和 UI 正常工作，新增功能通过可插拔开关控制。

---

## 3. OpenClaw 现状分析

### 3.1 项目概况
OpenClaw 是一个开源的本地桌面 AI Agent，采用 Python 编写，提供：
- 多模态输入（文字、语音、截屏理解）
- 工具调用框架（文件操作、终端命令、浏览器操控）
- 记忆系统（基于 ChromaDB 的短期记忆）
- 插件式扩展机制
- Web 前端交互界面

### 3.2 架构特点
- 后端采用 FastAPI + WebSocket 实现事件驱动。
- 任务执行采用 Plan-and-Execute 模式，由 Planner 分解步骤，Executor 调用工具。
- 记忆模块独立，可被任何组件调用。
- 前端使用 React，通过 WebSocket 接收状态更新。

### 3.3 可扩展点
- **事件钩子：** 用户在线/离线状态变化事件目前未开放，但系统底层有活动检测机制（如 WebSocket 心跳）。
- **后台任务系统：** 使用 asyncio 后台任务，可干净地增加一个长期运行的 Dream 循环。
- **记忆读写：** 向量数据库接口已封装，可直接复用。
- **配置管理：** 使用 YAML 配置文件，易于添加梦境相关参数。

### 3.4 短板
- **缺乏长期自主行为：** 只有被动服务。
- **没有创新生产功能：** 无法自发产出高价值内容。
- **知识同步仅限对话：** 没有与外部知识库工具（如 Obsidian）的直接连接。
- **空闲时间闲置：** 算力没有得到充分利用。

---

## 4. 改造范围与原则

### 4.1 改造范围
| 模块 | 改造内容 | 影响程度 |
|------|----------|----------|
| 核心调度 | 新增 DreamService 后台协程，监听空闲并启停梦境 | 低（新增文件） |
| 记忆系统 | 扩展向量数据库，增加梦境集合；增加 Obsidian 文件写入器 | 中（扩展接口） |
| 配置 | 增加 dream 段（模型、路径、触发条件等） | 低 |
| 前端 | 增加梦境状态指示器、梦境日志查看面板、手动触发按钮 | 中（新增组件） |
| API | 新增 /dream/start, /dream/stop, /dream/history 等端点 | 低 |
| 工具链 | 复用现有工具执行器，增加沙箱安全策略 | 低 |
| 插件 | 将梦境功能本身设计为一个插件，便于启用/禁用 | 推荐，最小侵入 |

### 4.2 改造原则
1. **非侵入式：** 所有新增代码放在独立的 `dreamweaver/` 包内，通过钩子注入，不修改 OpenClaw 核心逻辑。
2. **可开关：** 通过配置文件 `dreamweaver.enabled: true/false` 控制，关闭后原版 OpenClaw 无任何残留影响。
3. **隐私至上：** 梦境生成内容全部本地存储，云端 API 调用仅用于增强生成质量，且默认关闭，由用户主动开启。
4. **容错降级：** 若梦境子模块异常，不影响主 Agent 正常运行，自动静默退出并记录日志。
5. **社区友好：** 代码风格遵循 OpenClaw 规范，最终目标合并回上游，成为官方 Dreams 插件。

---

## 5. 系统架构设计

### 5.1 整体架构图

```
[OpenClaw 原有架构]
├── Web前端 (React)
│   ├── 聊天面板
│   ├── 工具箱
│   ├── [梦境指示器]         <-- 新增
│   └── [梦境日志面板]       <-- 新增
├── FastAPI 后端
│   ├── 路由层
│   │   ├── /chat, /task ...
│   │   ├── /dream/*          <-- 新增
│   ├── 核心引擎
│   │   ├── Planner
│   │   ├── Executor
│   │   ├── MemoryManager
│   │   └── [DreamService]    <-- 新增（独立模块）
│   ├── 工具注册表
│   └── 事件总线 (WebSocket)
│       └── [新增梦境状态推送]
├── 本地存储
│   ├── ChromaDB (记忆)
│   │   ├── conversations
│   │   ├── tasks
│   │   └── dreams            <-- 新增集合
│   ├── 文件系统
│   │   └── [Obsidian Vault 目录] <-- 新增写入
│   └── SQLite (任务历史)
└── 模型推理 (本地/云端)
    ├── DeepSeek API 适配器
    └── 本地 Ollama 适配器
```

DreamService 作为长期运行的后台任务，通过 OpenClaw 的事件系统获取用户活动状态，独立管理梦境生命周期，并将结果通过 MemoryManager 同步到向量库和 Obsidian。

### 5.2 DreamService 内部组件
- **IdleDetector：** 监听 WebSocket 心跳、鼠标键盘事件（通过前端定期上报），判定用户空闲/活跃状态。
- **DreamScheduler：** 根据空闲时长、时间计划、手动指令等决定何时启动梦境。
- **MotifGenerator：** 梦境主题生成器，从用户笔记、最近任务、全球热点中提炼母题。
- **SelfPlayEngine：** 核心对弈环，管理 Genius、Critic、Judge、Refiner、Mutator 多个 Agent 角色，执行多轮迭代。
- **ResultWriter：** 将最终方案格式化为 Obsidian Markdown 笔记，写入 Vault 指定目录，并更新向量数据库。
- **ResourceMonitor：** 控制 CPU/GPU 占用，确保不影响可能的前台恢复。

### 5.3 与原系统的交互
- **读取记忆：** DreamService 通过 `MemoryManager.query()` 获取用户相关知识和历史对话，用于生成母题和作为对弈上下文。
- **写入记忆：** 调用 `MemoryManager.add_dream(doc_id, embedding, metadata)` 将梦境成果向量化。
- **推送状态：** 使用原有 WebSocket 管理器向客户端发送 `dream_status` 事件（当前轮次、进度、是否完成）。
- **调用模型：** 复用 OpenClaw 的 `LLMProvider` 接口，支持同一套 API 密钥配置。

---

## 6. 功能需求详述

### 6.1 用户空闲检测与梦境触发

#### 6.1.1 空闲状态判定
- **数据源：**
  - 前端每 10 秒通过 WebSocket 发送 `heartbeat` 包含 `last_interaction` 时间戳（鼠标移动、键盘敲击、触摸事件）。
  - 后端同时监听 OpenClaw 的任务队列——若有未完成用户任务则视为活跃。
  - （可选）通过摄像头或麦克风检测人体存在，但为实现简易化，初版只依赖软件活动。
- **判定逻辑：**
  - 连续 15 分钟无用户交互事件 → 进入 `idle` 状态。
  - 用户配置可自定义时长（`dreamweaver.idle_timeout_seconds`，默认 900）。
- **状态切换：**
  - `active` → `idle`：触发 DreamScheduler。
  - `idle` → `active`：若梦境正在运行，向 DreamService 发送终止信号，系统在 10 秒内结束当前迭代并保存中间结果，恢复前台任务响应。

#### 6.1.2 手动控制
- API: `POST /dream/start` (body 可指定母题，若无则由系统自动生成)
- API: `POST /dream/stop` (立即中断并保存当前最佳方案)
- 前端提供“立即做梦”按钮和“中断”按钮，中断时显示确认弹窗以防误触。

#### 6.1.3 计划任务
- 支持 cron-like 表达式，允许用户设定每日深度梦境时段（如凌晨 3:00-5:00），即使此时设备被使用也会弹出通知询问是否允许开始。

### 6.2 梦境母题生成器

#### 6.2.1 母题来源
1. **用户未解问题：** 从 OpenClaw 的任务历史中过滤出状态为“部分完成”或“用户反馈不满意”的任务，抽取核心问题描述。
2. **知识图谱缺口：** 分析 Obsidian Vault 内笔记图谱，识别连接稀疏但常被引用的概念节点，生成“如何关联 A 与 B”类母题。
3. **用户标记：** 用户在聊天或笔记中手动打标签 `#dream` 的内容，优先级最高。
4. **全球趋势匹配：** 每日定时抓取 arXiv、ProductHunt、HackerNews 等摘要，使用用户兴趣向量筛选出 3 个热门主题。
5. **随机跨界变异：** 低概率（5%）从完全不相关领域抽取概念，强行组合，如“将区块链共识机制应用于家庭冰箱库存管理”。

#### 6.2.2 母题评分与选择
- 使用评判模型对每个候选母题打分（维度：相关性 0-10，创新潜力 0-10，可解性 0-10，行动力 0-10）。
- 选择得分最高者作为本次梦境母题，若存在用户标记主题则直接使用。
- 所有候选母题及其评分记录在日志中，供用户事后查看为何选择该题。

### 6.3 自我对弈进化引擎

#### 6.3.1 角色 Prompt 模板（内置，可自定义）
所有角色 prompt 均设计为 system message，注入母题和截止目前的最佳方案。

- **Genius（生成者）：**
  ```
  你是创新突破专家。针对以下问题，提出一个激进且逻辑自洽的完整解决方案。
  忽略现有工程实践，可调用任何已知科学原理。必须包含具体技术路径、关键算法、预期效果和对比现有方案的优势矩阵。
  问题：{motif}
  之前最佳方案参考（如有）：{best_solution_summary}
  请输出完整方案文档。
  ```
- **Critic（批评者）：**
  ```
  你是最严厉的审稿人。你的目标是从根本逻辑、实现可行性、效率、隐含假设、伦理风险、资源消耗、意外后果等维度，找出当前方案中的致命缺陷。至少列出 5 个具体漏洞，并说明每个漏洞的严重程度和可能导致的后果。
  当前方案：{current_solution}
  问题背景：{motif}
  ```
- **Judge（裁判）：**
  ```
  你是一位公正的专家评委。阅读问题和两个方案（当前方案 vs 历史最佳），根据正确性、创新性、实用性、鲁棒性和效率进行 0-10 分综合评分，并给出详细的胜负分析。评分必须基于具体证据。
  问题：{motif}
  当前方案：{solution_A}
  历史最佳方案：{solution_B}
  输出 JSON: {"score_A": .., "score_B": .., "winner": "A"/"B", "reason": "..."}
  ```
- **Refiner（精炼者）：**
  ```
  你是一名高级架构师。在不削弱方案创新性的前提下，解决Critic指出的所有致命漏洞，输出改进后的完整方案。
  原始方案：{solution}
  Critic反馈：{critic_feedback}
  问题背景：{motif}
  ```
- **Mutator（变异器，每 10 轮触发）：**
  ```
  你需要引入一个完全意想不到的跨领域范式来重构当前方案。例如：“现在假设我们只能使用流体力学原理来解决这个软件工程问题。”请给出一个异化但逻辑通顺的新方案原型。
  当前方案：{solution}
  变异方向：{random_paradigm}
  ```

#### 6.3.2 对弈流程
1. **初始：** Genius 生成方案 S0。
2. **循环 i=1 到 MAX_ITERATIONS (默认 100):**
   - Critic 评价 S(i-1)，输出漏洞报告。
   - Judge 将 S(i-1) 与当前全局最佳 S_best 比较，更新 S_best 和 best_score。
   - Refiner 接收 S(i-1) 和 Critic 报告，生成 S_i。
   - 若 i % 10 == 0，Mutator 基于 S_best 生成变异方案 S_mut，直接与 S_best 比较，若 Judge 判定 S_mut 更优则取代 S_best，并记录变异来源。
   - 记录本轮迭代日志（完整 prompt 和响应）。
3. **停止条件：**
   - 达到最大迭代数。
   - 连续 20 轮 best_score 没有增加（收敛）。
   - 收到外部中断信号。
4. **结束：** 最终 S_best 作为梦境成果输出。

#### 6.3.3 模型策略
- 默认全部使用 DeepSeek-v4-pro API（通过 OpenClaw 的配置）。
- 可选择本地 Ollama 模型（如 DeepSeek-coder-33B-instruct-Q4）进行快速迭代，但 Judge 角色建议保留云端高精度模型以保证评判可信度。
- 使用异步并发，Critic 和 Refiner 可部分重叠执行以提高速度，但需注意 API 速率限制。
- 所有 API 调用的提示词和回应全程记录，支持事后审计和可解释性。

#### 6.3.4 安全沙箱
- 若梦境方案中包含可执行代码（如 Python 脚本），系统不会自动执行。仅当用户在查看结果后明确点击“运行验证”时，才会在隔离容器（Docker 或微虚拟机）中执行，网络访问默认关闭。
- 禁止生成涉及武器、恶意软件、社会工程攻击的方案，Judge 评分中包含伦理一票否决项（由专门的伦理模型检测）。

### 6.4 梦境结果输出与知识同步

#### 6.4.1 Obsidian 笔记生成
- 输出路径：`{obsidian_vault_path}/Dreams/{YYYY-MM-DD}/{母题摘要}.md`
- 笔记内容：
  ```markdown
  ---
  dream_id: 20260601-001
  date: 2026-06-01T03:15:00
  motif: "如何用最少的代码重构当前项目核心模块"
  score: 9.2
  iterations: 87
  tags: [refactoring, innovation, code]
  related: []
  ---
  # 梦境方案：{{标题}}

  ## 背景与问题
  {{母题详细描述}}

  ## 最终方案
  {{胜出方案的完整内容，包括技术路径、算法、伪代码、优势矩阵}}

  ## 演化历程摘要
  - 关键转折轮次：第34轮，变异注入“生物愈合机制”后评分跃升...
  - 最终得分趋势图：(ASCII图表或文字描述)

  ## 与现有知识的关联
  - [[相关知识笔记1]]
  - [[相关知识笔记2]]

  ## 行动建议
  - [ ] 在模块X尝试引入方案中的接口抽象
  - [ ] 评测性能提升预期
  ```
- 系统会自动解析正文中的 `[[概念]]` 并在 Vault 中搜索对应笔记，如不存在则创建存根笔记。
- 每次生成后，触发 Obsidian 的“快速切换”更新（通过修改文件时间戳）。

#### 6.4.2 向量数据库同步
- 将梦境方案切分为段落，使用与 OpenClaw 主记忆相同的 embedding 模型（BGE-M3）生成向量。
- 存入 ChromaDB 新集合 `dreams`，元数据包含 dream_id, motif, score, tags, date。
- 同时在主对话记忆集合 `conversations` 中插入一条系统消息摘要，告知“我刚刚在梦境中思考了...”，以便用户后续对话可直接引用。
- 提供 `MemoryManager.search_dreams(query, top_k=5)` 方法，优先级高于通用记忆。

#### 6.4.3 用户通知
- 当用户返回活跃状态且梦境已完成，前端弹出非阻塞通知：“我在你离开时做了 1 个梦，关于[母题摘要]，要看看吗？”
- 点击通知跳转到梦境日志面板，展示最终方案。
- 支持每日/每周邮件摘要（可选，使用用户配置的邮件服务）。

### 6.5 梦境管理与用户界面

#### 6.5.1 前端面板
- **梦境指示器：** 位于主界面右上角，以月相图标表示状态（新月=空闲等待，满月=梦境中，光环=完成）。鼠标悬停显示当前梦境轮次和母题。
- **梦境日志：** 独立标签页，列表展示历史梦境，可按日期、评分、标签排序。点击条目打开详情，可阅读完整方案、演化图表和迭代日志。
- **手动触发：** 按钮“立即做梦”，点击后弹出选项：自动选题 / 输入自定义母题。
- **设置面板：**
  - 开关：启用梦境 (默认开)
  - 空闲时间阈值（分钟）
  - 最大梦境时长（分钟，防止云端费用过高）
  - 是否允许云端 API 用于梦境（勾选）
  - Obsidian Vault 路径
  - 梦境内模型选择（云端/本地）
  - 梦境通知方式

#### 6.5.2 API 端点
- `GET /dream/status`：返回当前状态 (idle, running, completed) 及进度信息。
- `POST /dream/start`：手动触发，body { "motif": "..." } (可选)。
- `POST /dream/stop`：中断。
- `GET /dream/history?limit=20&offset=0&sort_by=score`：历史列表。
- `GET /dream/{dream_id}`：详情。
- `DELETE /dream/{dream_id}`：删除某次梦境及其文件。
- `POST /dream/{dream_id}/apply`：用户标记“已应用”，用于统计采纳率。

### 6.6 资源管控与异常处理
- **资源限制：** DreamService 启动时检测系统当前资源使用率，若 CPU > 80% 或内存 > 85% 则自动延迟开始，等待 5 分钟后重试。
- **进度保存：** 每 10 轮自动将当前最佳方案序列化到磁盘，防止意外中断丢失。
- **错误重试：** 单次 API 调用失败（网络、限流）自动重试最多 3 次，指数退避。若连续失败超过 5 次，本次梦境终止并记录错误。
- **降级：** 若云端 API 不可用而用户允许本地模型，自动切换至本地，但只进行 30 轮简化对弈。

---

## 7. 数据模型与存储设计

### 7.1 数据库扩展
在 OpenClaw 使用的 SQLite 数据库（`openclaw.db`）中新增两张表：

```sql
CREATE TABLE dreams (
    id TEXT PRIMARY KEY,          -- 唯一ID，如 20260601-001
    motif TEXT NOT NULL,
    status TEXT DEFAULT 'idle',   -- idle, running, completed, failed
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    iterations INT,
    best_score REAL,
    outcome_path TEXT,            -- 最终方案Markdown路径
    tags TEXT,                    -- 逗号分隔
    model_used TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dream_iterations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dream_id TEXT NOT NULL,
    round INT,
    role TEXT,                    -- genius, critic, judge, refiner, mutator
    prompt TEXT,
    response TEXT,
    score REAL,
    tokens_used INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dream_id) REFERENCES dreams(id)
);
```

### 7.2 ChromaDB 配置
- 新建 collection `dreams`，metadata 配置同记忆模块。
- 索引：`dream_id`, `motif`, `score`, `tags`。
- 嵌入维度与主模型一致（1024）。

### 7.3 文件系统布局
```
openclaw_data/
├── dreams/
│   ├── checkpoint/          # 中间保存
│   └── logs/                # 详细运行日志
├── obsidian_writer/         # 待写队列（确保原子写入）
└── ...
```

---

## 8. 接口与集成规范

### 8.1 与 OpenClaw 核心的集成点
1. **事件总线：** 订阅 `user.activity` 主题，发布 `dream.state`。
2. **配置注入：** `config.yaml` 中 `dreamweaver` 段由 DreamService 读取，保持与主配置一致。
3. **记忆管理器：** 新增 `add_dream`, `search_dreams` 方法，通过 monkey-patch 或继承扩展。
4. **LLM Provider：** 调用 `openclaw.llm.get_provider()` 获取统一模型接口。

### 8.2 插件式激活
DreamWeaver 被打包为一个 OpenClaw 插件，结构如下：
```
openclaw_plugins/dreamweaver/
├── __init__.py
├── plugin.yaml           # 元数据与开关
├── dream_service.py
├── self_play.py
├── motif_generator.py
├── obsidian_writer.py
├── api.py
└── frontend/
    ├── DreamIndicator.jsx
    └── DreamPanel.jsx
```

在 OpenClaw 启动时自动扫描插件目录，若发现 `dreamweaver` 且配置启用，则初始化并挂载到事件循环。

---

## 9. 用户体验设计

### 9.1 梦境可视化
前端提供一种极简的抽象动画：背景由暗色粒子缓慢浮动，表示正在进行思考。粒子逐渐凝结成星云状，直至最终形成清晰方案时爆发短暂光效。避免任何具体文字泄露，保护隐私同时给予直观反馈。

### 9.2 结果展示
- 方案文档以预览方式呈现，支持 Markdown 渲染，代码块高亮，并提供“在 Obsidian 中打开”按钮。
- 演化过程以可折叠时间轴展示，标注关键轮次和评分跳跃。
- “对比与挑战”区域允许用户直接对方案提出质疑，系统可基于现有方案再启动一个短梦（10 轮）进行深度完善。

### 9.3 交互反馈原则
- **无干扰：** 除非用户主动查看，梦境完成后不自动弹出大窗口。
- **可解释：** 任何方案都附带“为什么做这个梦”的简短说明，建立用户信任。

---

## 10. 非功能需求

### 10.1 性能
- 梦境迭代单轮总耗时 < 30 秒（含 API 调用）。
- 结果写入 Obsidian Vault 延迟 < 2 秒。
- 用户返回后系统退出梦境状态延迟 < 5 秒（保存检查点）。
- 梦境期间主 Agent 对话响应延迟增加不超过 200ms。

### 10.2 可扩展性
- 对弈角色、评判标准、变异策略均可通过配置文件替换 prompt 或直接重写类。
- 支持添加新数据源用于母题生成。

### 10.3 安全性
- 所有用户笔记内容仅在本地处理，母题生成和上下文注入不离开用户设备（除非用户开启云端 API，此时发送最小必要信息）。
- 云端 API 调用日志不保存用户具体梦境内容，仅记录 tokens 消耗。

### 10.4 可靠性
- 梦境服务作为独立进程，崩溃不影响主 Agent，watchdog 自动记录并发送通知。
- 检查点机制保证进度不丢失。

---

## 11. 开发与部署路线图

### Phase 1：基础嵌入与单轮梦境 (2 周)
- Fork OpenClaw，创建 `dreamweaver` 插件骨架。
- 实现 IdleDetector 和基础 DreamScheduler。
- 实现最简单的梦境循环：Genius 生成 + Judge 评分，无 Critic/Refiner，仅输出单方案到 Obsidian。
- 前端状态指示器。

### Phase 2：完整对弈引擎 (2 周)
- 完善 SelfPlayEngine，加入 Critic、Refiner、Mutator 全部角色。
- 实现迭代评分收敛逻辑。
- 结果 Markdown 格式化及双向链接。
- 向量数据库集成 `dreams` 集合。

### Phase 3：管理界面与优化 (1 周)
- 梦境日志面板、设置界面。
- 错误处理和资源管控。
- 多语言 Prompt 调优，确保方案质量。
- 用户测试与反馈调整。

### Phase 4：测试与文档 (1 周)
- 端到端测试（模拟空闲、手动触发、云端降级）。
- 编写用户指南和开发者文档。
- 准备 Pull Request 提交给上游 OpenClaw。

---

## 12. 风险评估与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 梦境方案空洞无用，沦为高级胡言乱语 | 中 | 高 | 内置多道评判，提供用户“踩”反馈，持续优化 prompt；允许用户微调评判标准 |
| OpenClaw 架构大改致插件失效 | 低 | 高 | 采用最小接口依赖，关注上游动态，及时适配 |
| 云端 API 成本失控 | 中 | 中 | 默认限制每日最大 Token 用量，显示实时花费，提供纯本地模式 |
| 用户隐私担忧 | 低 | 高 | 本地优先设计，数据不出设备；提供详尽隐私说明和开关 |
| 空闲检测误判导致不合时宜的梦境 | 中 | 低 | 自定义空闲时间，明显的中断按钮，用户可轻易停止 |

---

## 13. 附录

### 13.1 术语表
- **梦境 (Dream)：** 系统空闲时的自主创新过程。
- **母题 (Motif)：** 梦境要解决的核心问题。
- **自我对弈 (Self-Play)：** 多角色 Agent 相互批判与改进的循环。
- **OpenClaw：** 本项目的基础开源桌面 AI Agent 框架。

### 13.2 配置示例 (config.yaml)
```yaml
dreamweaver:
  enabled: true
  idle_timeout_seconds: 900       # 15 分钟
  max_iterations: 100
  convergence_rounds: 20
  obsidian_vault_path: "/home/user/notes"
  dream_folder: "Dreams"
  cloud_enabled: false            # 初期关闭
  local_model: "deepseek-coder:33b"
  daily_token_limit: 100000
  notification: true
```

### 13.3 相关资源
- OpenClaw GitHub: `https://github.com/openclaw/openclaw`
- DeepSeek API 文档: `https://platform.deepseek.com/docs`
- Obsidian URI 协议: `https://help.obsidian.md/Advanced+topics/Using+obsidian+URI`

---

**此 PRD 详细阐述了如何以最小代价将“梦境”能力注入 OpenClaw，打造全球首个具备自主进化能力的桌面 Agent。立即启动 Phase 1，四周后你将拥有一个实打实的创新引擎，而非又一个只会应声的机器。**