---
name: agentic-character
description: Agent Anime 角色制作技能入口，根据当前输入选择 A-pose 与拆件、部件网格与贴图、静态装配或人体绑定与接头。
---

按当前任务读取对应的子技能。从用户已有的产物继续，只运行请求的阶段。

- 角色参考图生成正面 A-pose、分离部件图 → [character-part-extraction](character-part-extraction/SKILL.md)
- 从部件图生成低模、UV 和贴图 → [component-gen](component-gen/SKILL.md)
- 将已贴图部件对齐到角色参考并在 Blender 静态装配 → [assemble](assemble/SKILL.md)
- 无头人体绑骨、蒙皮，或将装配好的头部接入身体骨架 → [body-rigging](rigging/human-rigging/body-rigging/SKILL.md)

## 完整角色的绑定顺序

新角色默认先完成静态装配，从装配副本拆出最终的无头 body，按该身体网格定位关节，独立生成身体及手指蒙皮。独立身体必须通过[身体绑定验收](rigging/human-rigging/body-rigging/SKILL.md#身体绑定验收)，才能将头颈接入同一骨架，另存只含身体、头部和骨架的静态工程。在头身副本回放目标动作，检查颈缝、膝踝屈伸与交叉步时双腿是否相交，再按项目的 [assemble-rigging](../assemble-rigging/SKILL.md) 接回头发、服装、袖口和鞋。用相同动作逐帧对照头身与着装版本，分别记录身体自身、衣物与身体、衣物之间的相交；身体层已出现的异常先回到头身检查点修正。独立面部控制另行开展。已有案例按新角色重做时，从指定静态装配的几何与材质重新拟合骨架、权重及动作修正，并另存工程。完整计时从第一次分析输入开始，见[绑定计时与交付](../assemble-rigging/SKILL.md#完整计时与交付)。

同一版本的身体已有合格绑定时，直接复用骨架和权重，从接头或剩余的装配绑定步骤继续。复用时优先保留已确认的原顶点对应关系，只在领口新增或改形的区域局部映射。单独交付 body 的任务仍可在装配前完成。
