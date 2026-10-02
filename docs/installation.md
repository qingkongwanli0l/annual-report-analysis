# 三宿主安装与实际能力

同一份 `skills/annual-report-analysis` 目录包含入口、专业方法、脚本和依赖。无需金融数据订阅或本项目单独的模型 API Key；使用者仍需要对应宿主的正常模型访问权限。默认读取用户提供的年报，在线找报告需要宿主浏览能力。

## Claude Code

复制整个技能目录到项目 `.claude/skills/annual-report-analysis/` 或个人 `~/.claude/skills/annual-report-analysis/`，不要只复制SKILL.md。用 `/annual-report-analysis` 调用。也可在本仓库运行 `claude --plugin-dir .` 测试插件；插件技能的命名空间为 `/annual-report-analysis:annual-report-analysis`。本项目不修改用户全局权限，不安装MCP。

官方依据：[Skills](https://code.claude.com/docs/en/skills)、[插件清单](https://code.claude.com/docs/en/plugins-reference)。

## DeepSeek harness

将技能目录复制到项目 `.agents/skills/annual-report-analysis/` 或 `.dsh/skills/annual-report-analysis/`。其本地发现器按项目 `.dsh`、项目 `.agents` 等优先级寻找直接子目录中的 SKILL.md；最近 `.git` 祖先决定项目根。不要把另一项目同名技能误当本包。

这里指官方 [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) 及其[技能子系统](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md)，不是任意接入DeepSeek模型的第三方聊天界面。模型提供者与工具执行配置由该宿主负责，本项目不读取其他应用OAuth凭据代替它的API凭据。

## ChatGPT 与 Codex

仓库提供 `.codex-plugin/plugin.json` 的官方兼容布局，引用同一 `skills/`，不依赖MCP服务。通过支持本地插件源的ChatGPT桌面Work/Codex环境安装并验证；正式公共目录审核与GitHub发布分别记录。没有审核通过之前不宣称已上架。最新官方也支持根 `plugin.json` 的便携格式，兼容清单仍受支持。[打包说明](https://developers.openai.com/plugins/build/plugins)、[构建技能](https://learn.chatgpt.com/docs/build-skills)。

能发现并读取技能，不等于当前模式能执行Python/Node或导出文件。完整三文件工作流需要文件读取、脚本执行和交付能力；在仅聊天模式准确标注不能执行的部分。Codex可将整个技能目录放到支持的项目或个人技能位置使用。

## 依赖与运行

Python 3.11+ 与 Node 18+。在任务环境安装技能目录的 `requirements.txt` 和 `package.json`；托管插件缓存不可写时，复制到用户工作目录或使用宿主现成依赖。三个宿主使用相同脚本及 JSON，没有独立维护三套提示词。

```bash
python -m pip install -r skills/annual-report-analysis/requirements.txt
npm install --prefix skills/annual-report-analysis
python skills/annual-report-analysis/scripts/export.py examples/catl-2025/workpaper.json --output output/catl
```

以上命令应在仓库可写副本运行。`output` 可改成任务目录，脚本禁止输出到技能安装目录。具体底稿契约见技能的 `references/workpaper.md`。
