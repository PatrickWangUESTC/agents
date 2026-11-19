# Agent Anime

## Skill 维护范围

在本项目中创建、修改或整理 skill，只能写入本项目的 `.agents/skills/`。此规则涵盖技能正文、脚本、配置、参考资料和资源文件。编辑前解析目标的真实路径，包含符号链接在内的最终写入位置也必须在该目录内。需要定制外部或全局 skill 时，先复制到项目内，再编辑本地副本。

Skill 记录可跨角色复用的判断依据、处理方法和验证方式。角色名、固定帧号、实测数值和前后对照图归入对应 case 的产物目录。

## 角色制作

本项目的角色制作任务默认从 [.agents/skills/agentic-character/SKILL.md](.agents/skills/agentic-character/SKILL.md) 选择对应阶段，读取该目录下的子技能，并从当前 case 已有产物继续。完整角色默认先完成静态装配，再在装配工程中单独选取最终 body，用 body-rigging 完成身体绑定与蒙皮复核。随后将头颈接入同一骨架，用 assemble-rigging 绑定头发、衣物和鞋，最后复核动作。同版本 body 已有通过复核的绑定时可直接复用。

身体绑定与头部接入完成后，眼睑、嘴部等面部表情绑定属于可选的后续处理，仅在用户单独发起“调试Facial Rigging”时开展。

装配绑定所有角色时保留完整身体表面。静态工程与动作预览均移除角色网格上的 Mask 修改器；通过衣物形状、蒙皮与接触修正处理穿插。

本项目的 assemble-rigging 和装配后发束排骨调试使用项目独立的 [.agents/skills/assemble-rigging/SKILL.md](.agents/skills/assemble-rigging/SKILL.md)。
