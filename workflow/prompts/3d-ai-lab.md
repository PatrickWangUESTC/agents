使用 $three-d-ai-lab 搭建并执行这个 case 的本地 3D AI Lab 工作流。
先读取 inputs/lab-case.json、实际资产和参考，概括本库的
“case 规划 → 检查 → 操作 → 预览 → 复核 → 选择修订”流程。
按这个 case 的目标、保护项与验收条件执行，不套用其他角色的颜色或骨骼规则。
已有模型从检查点继续，不重新生成。每次修改先保存诊断，再执行 Blender 脚本，
检查新视图及原生回读，记录接受或拒绝；拒绝候选不替换当前选定检查点。
当前只处理静态检查、装配、局部修复、拆分/替换与预览；不做表情、动画或绑定。
最终返回原生场景、预览、case 工作流和实测范围，未通过项明确保留。

Use the Lab observe/act/review loop for iterative edits. Inspect the packet's actual
images before authoring a decision; record the defect, exact object/region, bounded
operation, expected improvement and stopping condition. For static inter-part
crossing requirements, declare geometry_checks.surface_pairs in the case before
initialization. Read both machine checks and fresh native-material images. Failures
retain the selected checkpoint; do not promote malformed or intersecting candidates.
