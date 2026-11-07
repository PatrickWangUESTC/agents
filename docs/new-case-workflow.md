# 用新角色测试

复用的是技能和检查流程，不是上一角色的坐标、颜色阈值、骨骼或验收结论。
当前角色已实际跑过局部袖口修复和参考肤色调整；新角色的自动泛化效果尚待验证。
合成 Blender 测试用于检查工具约束，不代表所有角色自动处理成功。

| 当前输入 | 从哪里开始 | 主要 skill |
| --- | --- | --- |
| 原始图片 | 参考分析，必要时 A-pose，按参考拆分，生成并检查 | character-canvas / mesh-generation |
| 已有分件 mesh | 库存、单位/朝向/姿态检查，装配 | character-assembly / three-d-ai-lab |
| 已有装配角色 | 新检查点，诊断并修复指定区域 | three-d-ai-lab / character-local-edit |
| 裸露皮肤或其他颜色错误 | 参考取色、按当前 mesh 划定面选区、材质修正 | character-material-refinement |
| 请求替换部件 | 保留非目标部件，替换并复核接缝 | character-part-upgrade |
| 请求骨架交付 | 装配验收，实际参考骨架，全部部件绑定，姿态检查，导出回读 | character-rigging / character-fbx-export |

每个 case 先写 `artifacts/case-plan.md`，确认输入与目标、真实对象清单、坐标和单位、
保护项、可修改范围、后端依赖、检查标准。生成供应商、骨架、mesh 预算、部件数量、
材质选区都由新 case 决定。没有提供骨架时不要默认用旧 COM0；没有低模要求时不减面。
既有 rig/morph 输入要保留，不强行用只支持静态输入的脚本清空后重做。

## 单个例子

在仓库根目录把新图片/模型和 brief 放入 `local/case-a/`。brief 用普通文字说明
期望结果、保护哪些部件、是否需要绑定/FBX以及可用生成后端即可。

```bash
python3 scripts/agents.py init runs/case-a --input local/case-a
codex -C runs/case-a
```

在新 workspace 中粘贴 [新角色任务 prompt](../workflow/prompts/new-character.md)，
或用启动器准备同样的任务：

```bash
python3 scripts/agents.py run --input local/case-a \
  --prompt-file workflow/prompts/new-character.md --dest runs/case-a-preview
```

上述 run 默认只准备。实际执行选择另一个新目录并加 `--execute`。不覆盖已存在的
workspace；持续修订用其已有 Lab session。

## 多个例子

在 `local/characters.json` 写：

```json
[
  {"id":"case-a", "input":"case-a", "prompt":"读取 inputs/。先写本 case 工作流，再使用 three-d-ai-lab 和相关角色 skills 完成 brief；保存四视图和实际验收证据。"},
  {"id":"case-b", "input":"case-b", "prompt":"读取 inputs/。先写本 case 工作流，再使用 three-d-ai-lab 和相关角色 skills 完成 brief；保存四视图和实际验收证据。"}
]
```

input 相对 manifest 所在目录解析。先查看准备结果，再选择新目录实际运行：

```bash
python3 scripts/agents.py batch local/characters.json --dest runs/batch-preview --jobs 2
python3 scripts/agents.py batch local/characters.json --dest runs/batch-live --jobs 2 --execute
```

并发数还需符合生成账号额度和本机 Blender 内存；不要让多个 case 共用 session 或
运行目录。失败要保留任务 ID 和检查点，重试前先核对是否已有任务在运行。

## 新例子的通过标准

- 实际加载本 workspace 的 skills，并根据新输入写出不同的 case 配置。
- 原始资产和明确保护的部件保持不变，未沿用旧角色的硬编码选区。
- 修改前后相同相机的四视图与局部近景，真实看过再记录视觉复核。
- 几何和材质各自检查，局部检查只声明局部通过；不覆盖失败记录。
- 保存并独立加载交付文件；请求绑定时再增加真实骨架、姿态和蒙皮验证。

局部 mesh 修复策略见 [local-repair](../workspace/.agents/skills/three-d-ai-lab/references/local-repair.md)，
肤色/材质策略见 [material refinement](../workspace/.agents/skills/character-material-refinement/SKILL.md)。
旧的色彩专用 assembly/rig 策略仅保留兼容，不是新 case 的默认路径。

新建账本的 `constraints.rig_required` 默认为 false；需要绑定时显式设置 true。
引擎步骤需要 `delivery.engine.enabled=true` 和明确 target，未启用记为 not_run。
已有账本不会被自动改写。
