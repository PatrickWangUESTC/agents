使用 $character-canvas 根据 inputs/brief.json 搭建并执行角色任务。
读取 brief 指向的实际参考与资产，检查工具是否可用；缺失输入明确指出。
创建 artifacts/character/ledger.json，逐节点保留产物、任务句柄和验收证据。

我授权使用 character_planner、character_builder、character_critic 三个
自定义 subagent 分别规划、执行、复核。独立部件任务可以并行，同一 Blender
场景的写入必须串行，输出目录不得重叠。

按部件生成、装配、局部改进、绑定、导出和引擎测试推进。工具缺失时记录 blocked，
继续能独立完成的工作。只修改头部时，建立分支并验证其他部件的保护属性。
不要将示例 fixture、计划、占位文件或骨架截图作为完整角色成功的证据。
最终报告说明当前产物、已运行检查、未运行环节和继续执行的条件。
