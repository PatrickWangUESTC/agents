实际集成验证任务。必须使用真实工具调用，不要模拟 subagent 或声称未做过的检查。

先说明自动提供给你的可用 skill 元数据是否包含 workspace-intake 和 evidence-review，以及可用 agent 类型是否包含 evidence_reader、implementer、acceptance_reviewer。请在 artifacts/discovery.json 中记录你在扫描目录之前从会话元数据实际看到的名称。不要把手动读取文件当成自动发现的证据。

使用 $workspace-intake 和 $evidence-review：实际读取这两个 SKILL.md，按前者创建 artifacts/task-contract.md，按后者记录验收证据。

调用三个自定义类型的 subagent（必须通过 spawn 工具使用其 agent_type，而不是 default）：
1. evidence_reader：读取 inputs/numbers.json，返回记录数与总和，不修改文件。
2. implementer：创建 artifacts/sum.py，读取输入 JSON 数字数组，输出 JSON 对象 count 和 sum。不要修改其他文件。
前两项可以并发。收齐结果后实际运行 python3 artifacts/sum.py inputs/numbers.json。
3. acceptance_reviewer：独立读取输入与 sum.py，运行正常输入及空数组的测试，报告 pass/fail，不修改文件。

等待全部 subagent 完成，再写 artifacts/report.md：列出实际角色调用、返回的 agent ID、skills 使用证据、执行的测试与结果，区分自动发现和手动文件读取。不要对原始输入做修改。
如果任一指定 skill 或角色没有加载，明确报告阻碍和未验证项，不要降级成 default 冒充成功。
