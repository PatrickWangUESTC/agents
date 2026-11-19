# 工作流任务

单例可使用 [角色入口提示](prompts/character.md) 或 [静态装配提示](prompts/assemble.md)。批量清单是 JSON 数组，每项包含唯一的 `id`、任务 `prompt` 和可选的 `input` 路径。相对输入路径从清单所在目录解析。[批量示例](tasks.example.json)

启动器把模板与各自输入复制到独立工作区，通过 `result/` 保存运行状态和输出。静态装配的几何、视觉和用户验收由对应技能记录。
