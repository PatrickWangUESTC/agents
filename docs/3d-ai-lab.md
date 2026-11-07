# 3D AI Lab

本库先提供通用的操作闭环，再按每个 case 的实际资产选择步骤：

```text
读取输入与参考 → 记录 case 工作流 → 场景检查与基线
→ Agent 诊断并编写局部操作 → Blender 执行与保存
→ 同相机预览、保护属性检查、独立进程回读
→ Agent 复核 → 接受新检查点 / 保留旧检查点并修订诊断
```

入口是 [three-d-ai-lab](../workspace/.agents/skills/three-d-ai-lab/SKILL.md)，
接口和 case 格式见 [runner contract](../workspace/.agents/skills/three-d-ai-lab/references/runner.md)。
可将 [任务 prompt](../workflow/prompts/3d-ai-lab.md) 交给已有启动器；批量时每项
使用自己的 `inputs/lab-case.json` 和独立 workspace，不共享一个 Lab session。

当前范围：静态资产检查、装配对齐、局部修复或细节编辑、拆分/替换、预览复核。
操作由 agent 针对 case 编写 Blender Python，不假设固定发色、服装或骨骼。
已有 rig/morph 的检查仅用于保护，不扩展到绑定、表情或动画制作。

## 对应 Tripo

[Canvas 教程](https://www.tripo3d.ai/tutorials/agentic-canvas-game-character)
提供 AI 3D Lab/Astra 操作节点；
[Astra + Blender 教程](https://www.tripo3d.ai/blog/gpt-6-astra-3d-character-workflow)
提供 agent 驱动 Blender 的参考。我们的实现使用当前调用模型和后台 Blender
进程，复用公开操作思路；没有安装 live MCP，也没有调用 Tripo 私有 Astra 服务。
这与生成后端分开：现有 N4D mesh 可以直接作为 Lab 输入。

## 文件和状态

`case.json` 固定目标和保护项；`session.json` 记录选定检查点；每个
`revisions/rNNNN/` 保存场景、操作、诊断、日志、预览、检查及哈希收据。
一次命令成功只代表 produced。复核可以拒绝候选；通过本 case 的全部要求才能
更新 selected。这不修改完整角色账本，也不提升既有角色的质量验收状态。

保护检查覆盖明确列出的属性，不能证明视觉或几何语义正确。默认视图是几何
预览；材质、碰撞、导出等额外要求需要对应证据。工具支持写入这些操作不等于
已有通用自动修复算法；每种操作仍需实际 case 的检查与验证。

仓库配置随 `agents.py init` 复制。没有隐式安装到全局 skills，也没有模型覆盖。

用户要求继续交付时，使用 [Lab 后续工作流](post-lab-workflow.md) 从选定检查点接入可选局部升级、装配复核、绑定、姿态测试与导出回读；静态 Lab 任务本身不自动扩大范围。

## 可执行的反馈循环

新增 `observe` 和 `act`：前者固定当前场景、图片、指标及失败反馈；agent 实际查看
图片后，用结构化 diagnosis、修改范围、预期效果和停止条件提交操作。后者检查
观察是否过期并保存决策，再运行 Blender。`review` 决定接受或回退。
调用中的 agent 负责推理；Python 不伪装成另一个大模型服务。

case 可声明 `geometry_checks.surface_pairs`。操作后和独立 Blender 回读时都会
检查指定部件之间的静态三角形交叉。超限时，提交文字“通过”也无法接受模型。
该检测不等于全局碰撞自由证明，视觉、共面接触、封闭体积和运动仍需独立判断。
详见 [agent loop 合约](../workspace/.agents/skills/three-d-ai-lab/references/agent-loop.md)。

新输入先按 [新 case 工作流](new-case-workflow.md) 选择起点。
局部袖口/开口等 mesh 缺陷使用 [局部修复指南](../workspace/.agents/skills/three-d-ai-lab/references/local-repair.md)；
参考肤色等材质问题使用 [材质修正 skill](../workspace/.agents/skills/character-material-refinement/SKILL.md)。
这些指南总结可复用的判断与验证，具体选区、姿态、参数和通过证据仍须由新 case 提供。
