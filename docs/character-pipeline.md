# 角色工作流

从 agentic-character 入口按输入选择阶段。身体已有合格绑定时可直接复用，再进入装配绑定。

- [agentic-character](../workspace/.agents/skills/agentic-character/SKILL.md)
- [assemble](../workspace/.agents/skills/agentic-character/assemble/SKILL.md)
- [character-part-extraction](../workspace/.agents/skills/agentic-character/character-part-extraction/SKILL.md)
- [component-gen](../workspace/.agents/skills/agentic-character/component-gen/SKILL.md)
- [human-rigging](../workspace/.agents/skills/agentic-character/rigging/human-rigging/SKILL.md)
- [body-rigging](../workspace/.agents/skills/agentic-character/rigging/human-rigging/body-rigging/SKILL.md)
- [assemble-rigging](../workspace/.agents/skills/assemble-rigging/SKILL.md)

身体绑定的 review_body.py 使用本机 avatar-rigging 提供的 diagnostic_run、motion_extrema 和 four_view 模块，路径见脚本。
