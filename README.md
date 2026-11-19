# Agent Anime

本仓库使用 Codex 工作区模板分发角色工作流、Blender 脚本和批量任务启动器。[角色工作流入口](workspace/.agents/skills/agentic-character/SKILL.md) · [静态装配技能](workspace/.agents/skills/agentic-character/assemble/SKILL.md)

## 直接调用

在 Codex 打开本仓库的 `workspace/`，或用启动器创建独立工作区。在该工作区输入：

> 使用 $agentic-character，从我提供的四视图、固定身体和已贴图部件开始，调用 assemble 完成静态装配，给我同机位四视图和穿模结果。

角色入口按当前产物选择拆件、部件生成、装配或绑定。需要委派任务时，可使用工作区的自定义角色 `agent_anime`。[阶段索引](docs/character-pipeline.md)

## 启动器

使用 Python 3.11 或更高版本。执行模型任务需要已配置的 Codex CLI。静态装配需要 Blender，部件生成需要已登录的 Tripo CLI。

```sh
python3 scripts/agents.py validate
python3 scripts/agents.py init ./local/anime --input /path/to/case
python3 scripts/agents.py run --prompt-file workflow/prompts/assemble.md --input /path/to/case --dest runs/assembly --execute
python3 scripts/agents.py batch workflow/tasks.example.json --dest runs/batch --jobs 2 --execute
```

每次运行使用新的目标目录。省略 `--execute` 可先准备任务工作区。[任务格式](workflow/README.md)
