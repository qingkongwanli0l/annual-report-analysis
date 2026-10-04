# 安装与宿主能力

同一份 `skills/annual-report-analysis` 目录包含入口、专业方法、脚本和依赖。无需金融数据订阅或本项目单独的模型 API Key；使用者仍需要对应宿主的正常模型访问权限。默认读取用户提供的年报，在线找报告需要宿主浏览能力。

当前为开发版，尚未合并主分支、正式发布重建版或上架宿主公共目录。试用时取得开发分支：

```bash
git clone --branch rebuild/annual-report-expert https://github.com/qingkongwanli0l/annual-report-analysis.git
cd annual-report-analysis
```

## Claude Code

复制整个技能目录到项目 `.claude/skills/annual-report-analysis/` 或个人 `~/.claude/skills/annual-report-analysis/`，不要只复制 `SKILL.md`。用 `/annual-report-analysis` 调用。也可在本仓库运行 `claude --plugin-dir .` 加载插件；插件技能的命名空间为 `/annual-report-analysis:annual-report-analysis`。本项目不修改用户全局权限，不安装 MCP。

官方说明：[Skills](https://code.claude.com/docs/en/skills)、[插件清单](https://code.claude.com/docs/en/plugins-reference)。

## DeepSeek harness

将技能目录复制到项目 `.agents/skills/annual-report-analysis/` 或 `.dsh/skills/annual-report-analysis/`。这里指官方 [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)，不是任意接入 DeepSeek 模型的第三方聊天界面。技能发现方式见其[技能子系统说明](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md)。模型访问与工具执行由宿主配置。

这里的项目目录是从运行目录向上找到的最近含 `.git` 的目录；没有 Git 根目录时才使用当前运行目录。应将技能放在该根目录下，放入普通子目录的 `.agents/skills` 不会成为独立项目技能。手动读取 `SKILL.md` 不等于已被宿主发现。

## ChatGPT 与 Codex

仓库提供 `.codex-plugin/plugin.json`，引用同一 `skills/`，不依赖 MCP 服务。`.agents/plugins/marketplace.json` 将仓库根目录登记为本地插件来源。安装了 Codex CLI 的用户可在仓库目录注册来源、安装并检查状态：

```bash
codex plugin marketplace add .
codex plugin list --marketplace annual-report-analysis-local --available --json
codex plugin add annual-report-analysis@annual-report-analysis-local --json
codex plugin list --marketplace annual-report-analysis-local --json
```

`plugin add` 完成本地安装；`plugin list` 应显示 `installed: true` 和 `enabled: true`。也可重启支持本地来源的 ChatGPT 桌面应用，在插件目录选择“企业年报分析（开发版）”来源并安装 `annual-report-analysis`，再在新会话中调用技能。Codex 也可将整个技能目录放到支持的项目或个人技能位置。参考官方[打包说明](https://developers.openai.com/plugins/build/plugins)与[构建技能说明](https://learn.chatgpt.com/docs/build-skills)。

上述来源注册、插件安装及启用状态已在 Codex CLI 0.160.0 验证（2026-10-04）；安装副本的必要文件与来源逐一核对一致。本地安装不等于 ChatGPT 已加载或已经执行，也不代表插件已上架公共目录或可在网页端直接安装。

完整三文件工作流需要宿主具备文件读取、Python/Node 脚本执行和文件交付能力。发现或读取技能本身不能证明这些能力可用；ChatGPT 原生完整工作流尚未完成实测。

## 依赖与运行

需要 Python 3.11+ 与 Node 18+。在可写仓库副本中安装依赖；托管插件缓存不可写时，复制到用户工作目录或使用宿主现成依赖。

```bash
python -m pip install -r skills/annual-report-analysis/requirements.txt
npm install --prefix skills/annual-report-analysis
python skills/annual-report-analysis/scripts/export.py examples/catl-2025/workpaper.json --output output/catl
```

此命令导出已有的宁德时代示例底稿。分析另一家公司时，向宿主提供原始年报、企业及期间和分析目的，由其依照[全面分析程序](../skills/annual-report-analysis/references/analysis-program.md)取证、形成判断并建立共同底稿，再运行导出。分析范围依据完整披露及适用评级方法逐项确定。

产物写入任务目录，不能写入技能安装目录。共同底稿格式及脚本用法见 [workpaper.md](../skills/annual-report-analysis/references/workpaper.md)。Excel 数值编辑可触发公式重算，但不会回写底稿或同步改写叙述、Word 和 PPT；正式更新应修订共同底稿并重新导出三份文件。

## 已知能力与限制

| 宿主 | 已有实测情况 |
|---|---|
| Claude Code | 已执行技能并生成三种文件；实测使用其已配置的 DeepSeek 模型，不代表 Anthropic 模型测试；全面分析初稿仍需专业核验 |
| 官方 DeepSeek harness | 已执行技能并生成三种文件；全面分析初稿仍需专业核验 |
| ChatGPT 原生入口 | 尚未完成安装、分析和导出的完整工作流实测 |
| Codex CLI | 已执行并生成三种文件；同一底稿经当前导出器重导出，抽查关键数值显示完整；不等同于 ChatGPT 原生入口验证 |

已有执行结果中仍发现取数、财务口径和因果判断错误。文件可打开、公式可重算，不代表分析内容正确；实际使用应核对关键原文、计算和专业判断，并检查文件版式。本地依赖安装与导出已运行，但尚未证明所有操作系统或托管宿主的首次安装体验。
