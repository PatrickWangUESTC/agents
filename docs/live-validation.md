# 真实集成验证：2026-11-06

使用库内启动器创建全新 workspace 并执行 `codex exec`。运行环境为 macOS、
`codex-cli 0.165.0-alpha.1.2`，继承用户配置的 `gpt-6-astra`、high reasoning，
沙箱为 workspace-write。本次未更改全局配置或登录信息。

| 验证项 | 实际证据 | 结果 |
| --- | --- | --- |
| skills 自动发现 | 主会话初始 Available skills 目录包含 evidence-review 和 workspace-intake，路径指向新 workspace 的 .agents/skills | 通过 |
| skills 实际使用 | CLI events 中记录读取两个 SKILL.md，随后生成 task-contract.md 和逐项验收报告 | 通过 |
| 自定义角色启动 | 主会话原始记录包含三次 collaboration.spawn_agent，agent_type 分别为三个自定义角色 | 通过 |
| 角色配置生效 | 三个子会话均指向本次主会话；各自 developer instructions 与对应 TOML 的内容一致 | 通过 |
| 协作产物 | reader 计算结果，implementer 创建 sum.py，reviewer 独立测试后主会话收齐结果 | 通过 |
| 程序功能 | 额外由外层验证程序断言正常数组、空数组、单元素、负数与小数的输出 | 4/4 通过 |
| 输入保留 | 工作目录输入与原始 fixture 字节一致 | 通过 |

主会话：`01a1af9a-f309-71a2-a71d-bfa74050c340`。

| 自定义角色 | 子会话 ID |
| --- | --- |
| evidence_reader | 01a1af9b-a862-7b12-8206-507896de279e |
| implementer | 01a1af9b-c3a0-74a1-b2ff-c0ba74c8e3c1 |
| acceptance_reviewer | 01a1af9c-390a-77d0-a90b-20c9280b3f50 |

功能检查的输入与实际输出：

| 输入 | count | sum |
| --- | --- | --- |
| [2, 5, -1, 7] | 4 | 13 |
| [] | 0 | 0 |
| [0] | 1 | 0 |
| [-3, 1.5] | 2 | -1.5 |

主会话及三个子会话的本地原始记录已核对。这里保存可复核的结果摘要，原始
全局会话上下文和日志不上传公共仓库。启动器本身仍将 acceptance 保留为
unverified；上述通过结论来自额外查看原始记录、配置注入内容及实际执行断言。

可复跑 prompt 为 `workflow/prompts/integration.md`，输入 fixture 为
`workflow/fixtures/sum/numbers.json`；运行命令见 README。此测试验证可用链路，
不评估复杂业务任务质量，也不证明在所有机器和 CLI 版本上均可运行。
