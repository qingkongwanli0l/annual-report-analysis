# 安装与宿主兼容性

本项目维护一份 `skills/annual-report-analysis/`。所有脚本、依赖清单与参考资料都在该目录内；安装时复制完整目录，不能只复制 `SKILL.md`。

以下根据 2026-10-02 官方文档编写。**文档与格式核验不代表宿主端到端运行验证，也不代表已在任何公开插件目录上架。**

| 宿主/模式 | 安装入口 | 当前验证状态 |
| --- | --- | --- |
| ChatGPT 桌面端独立 skill | 按产品 skill 安装入口导入完整目录 | 官方支持此形态；本项目端到端未验证 |
| ChatGPT 网页/桌面/移动端插件 | 包含根 `plugin.json` 与 `skills/` 的插件包，经相应插件分发流程安装 | 官方支持插件 skills；本项目尚未上架，脚本及三种文件导出未验证 |
| Codex 本地 CLI/IDE | `.agents/skills/annual-report-analysis/` 或 `~/.agents/skills/annual-report-analysis/` | 官方支持目录发现；本项目端到端未验证 |
| Claude Code | `.claude/skills/annual-report-analysis/`，或通过本仓库插件加载 | 2.1.218 本地插件 `--print` 冒烟通过（2026-10-02，范围见下）；独立 skill 目录未单独实测 |
| DeepSeek Harness | `.agents/skills/annual-report-analysis/` 或 `.dsh/skills/annual-report-analysis/` | 已核验官方 provider 规则；本项目端到端未验证 |

完整输出需要宿主能读取年报与包内资源，在同一可执行环境运行脚本，并把生成文件交付给用户。普通 Chat、Work、本地与云端的文件访问和执行能力可能不同；不能将插件可安装等同于任意脚本可运行。

## 运行依赖

核心指令不需要单独的模型 API Key。PDF 文本提取、计算和文档生成使用 Python；PPT 生成还使用 Node.js。Python 与 npm 的依赖分别以 skill 内 `requirements.txt`、`package.json` 为准。依赖名称包括 pdfplumber、python-docx、XlsxWriter、PptxGenJS。

在可写的 skill 工作副本内安装依赖，或使用宿主已经提供的对应环境；不要假设插件缓存可写。以下命令由用户或具备相应权限的宿主运行，不通过安装 hooks 自动执行：

```text
python -m pip install -r requirements.txt
npm install --ignore-scripts
```

安装 npm 依赖的目录应与 skill 内 `package.json` 一致，使同目录下的脚本能解析依赖。若宿主限制联网安装、执行或访问文件，应说明实际缺口，不能声称已经成功计算或导出。

从 skill 目录运行的命令形态如下；实际运行时将脚本、输入和输出解析为真实路径：

```text
python scripts/extract.py INPUT --output PATH
python scripts/extract.py INPUT --output PATH --pages 1-3
python scripts/calculate.py INPUT --output PATH
python scripts/export.py CALCULATED_JSON --output-dir DIR
```

提取结果不是财务工作底稿，需要模型核对原文后按 [data-contract.md](../skills/annual-report-analysis/references/data-contract.md) 建立 JSON。`export.py` 调用包内 `export_slides.cjs`。输入、JSON 与生成文件保存在用户任务目录，不在插件安装目录积累报告。

## Claude Code

最简单的本地方式：将完整 `annual-report-analysis` skill 目录放到项目 `.claude/skills/` 或个人 `~/.claude/skills/`，在新会话中调用 `/annual-report-analysis`。

也可从仓库根目录测试插件：

```text
claude --plugin-dir .
```

插件通过 `.claude-plugin/plugin.json` 及默认 `skills/` 目录发现 skill，可显式调用 `/annual-report-analysis:annual-report-analysis`。文件与 shell 仍受宿主权限约束。本项目不要求关闭权限检查，也不依赖 Claude 专用变量或安装提示。

2026-10-02 已在 Claude Code 2.1.218 使用 `--plugin-dir . --print` 完成本地插件冒烟：发现 skill、读取会计与底稿接口参考、抽取茅台年报 4 页并核对 2 个金额，运行计算器得到 14 项指标与 4 项勾稽，生成 Word、Excel、PPT。此测试沿用已有 42 条事实和分析底稿，未独立重做完整年报研究；结果仅适用于该本地模式和环境，不能外推到 ChatGPT、DeepSeek 或所有 Claude 安装方式。

`claude plugin validate .` 已通过，提示未提供作者信息；当前清单不虚构作者身份。这是清单校验结果，与上述运行测试分别记录。

依据：[Claude Code skills](https://code.claude.com/docs/en/skills)、[插件 manifest](https://code.claude.com/docs/en/plugins-reference)。

## DeepSeek Harness

将完整 skill 目录放入目标项目根目录的 `.agents/skills/` 或 `.dsh/skills/`，或个人 `~/.agents/skills/` / `~/.dsh/skills/`。项目根为最近的 `.git` 祖先，没有 Git 根时使用启动 cwd；任意位置克隆本仓库不会自动发现 `skills/`。

目录应为 `.agents/skills/annual-report-analysis/SKILL.md`，不能额外套一层仓库名。官方 provider 不递归发现任意 `**/SKILL.md`。同名 skill 的项目 `.dsh/skills` 优先于项目 `.agents/skills`，避免重复安装不同版本。

显式输入 `/annual-report-analysis`，或在任务中点名该 skill。加载指令不等于运行脚本；实际分析仍需要启用文件读取、执行以及需要时的搜索能力。

依据：[DeepSeek Skills 文档](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md)、[filesystem provider](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/src/index.ts)。

## ChatGPT 与 Codex

OpenAI 文档区分两条路径：独立 skills 支持 ChatGPT 桌面端、Codex CLI 和 IDE；插件封装的 skills 也可用于 ChatGPT 网页、桌面及移动端的 Chat/Work。使用 ChatGPT 的 `@` 或 Codex 的 `$annual-report-analysis` 显式调用。

Codex 本地可直接安装到项目或个人 `.agents/skills/`。ChatGPT 公开插件分发使用根 `plugin.json` 和 `skills/`；本仓库的 portable manifest 遵循 [Agent Plugins schema](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json)，没有私有工具依赖，也没有 MCP 服务。

对 ChatGPT 应先在拥有包内文件访问与代码执行能力的运行模式验证，再声明该模式完整支持 Word/Excel/PPT。向普通聊天发送 ZIP 不等于永久安装 skill，上传 OpenAI API skills 也不等于安装 ChatGPT 插件。

公开发布需遵循 OpenAI 插件提交和审核流程；本仓库提供可准备提交的结构，不承诺审核结果。官方要求在干净环境验证参考文件、可执行文件和依赖；如果核心能力依赖用户本机执行或任意本地文件访问，按其发布说明确认产品适用范围。

依据：[Build skills](https://learn.chatgpt.com/docs/build-skills)、[Package your plugin](https://developers.openai.com/plugins/build/plugins)、[提交与兼容限制](https://developers.openai.com/plugins/guides/submit-claude-plugin)。

## 最小运行验证

在每个准备声明支持的宿主和模式，用同一份小样例验证：skill 被发现并调用、相对参考可读、输入文件可访问、固定脚本完成计算、三种文件实际生成并可打开。记录产品、模式、版本和测试日期；只完成格式检查时不能将表格改成“端到端通过”。

宿主没有执行工具时仍可按 skill 做有来源的分析，但必须说明哪些计算未执行、哪些文件未生成；这不算完整文件输出支持。
