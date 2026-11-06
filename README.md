# agents

一个可复制、可版本管理的 Codex workspace 库。把任务规则、可复用 skills、
可选 subagent 配置放进工作目录，指向这个目录并传入 prompt 即可开始任务。
批量任务分别创建完整 workspace，避免共用输出目录。

已增加 [角色制作 pipeline](docs/character-pipeline.md)：参考 Tripo 的分件构建、
装配、局部改进与交付流程，提供四个角色 skills、三个专用 subagents，以及带
依赖和产物哈希的节点账本。实际后端按任务可用工具选择；已用 Blender 实测
分件装配、局部头部编辑、保护部件检查、渲染及 GLB 回读。

生成后端已加入 [N4D adapter](docs/n4d-provider.md)：支持文本和图片输入、任务
续等、原件保留和原精度分件检查；lowpoly 为按需选项。图片路径已真实调用验证，使用当前接口
要求的 multipart 上传；以后接 Tripo 时复用同一 job/artifact 交付约定。

## 目录

```text
agents/
├── workspace/                    # 可直接打开，也可复制的运行模板
│   ├── AGENTS.md                 # 输入、产物、证据约定
│   ├── .agents/skills/
│   │   ├── workspace-intake/      # 梳理任务输入和验收条件
│   │   ├── evidence-review/       # 依据实际产物复核结果
│   │   ├── mesh-generation/       # N4D 生成、原件检查与可选 lowpoly
│   │   ├── character-canvas/      # 角色节点与修订记录
│   │   ├── character-assembly/    # 分件装配
│   │   ├── character-local-edit/  # 局部修改与保护检查
│   │   └── character-delivery/    # 绑定、导出和引擎验证
│   └── .codex/
│       ├── config.toml           # 单任务 subagent 并发上限
│       └── agents/               # 通用及角色制作专用的 TOML 定义
├── workflow/                     # prompt、批量清单及使用方式
├── scripts/agents.py              # 初始化、单次运行、批量运行
└── tests/                         # 不调用模型的启动器测试
```

运行时创建 `inputs/`、`artifacts/` 和 `work/`。库中只保存通用配置和示例；
私有输入、原始沟通材料和运行日志放在被 Git 忽略的 `local/` 或 `runs/`。

## 直接在 Codex 中使用

需要 Git、Python 3.11+。交互使用或真实运行还需要已安装并登录的 Codex。

```bash
git clone https://github.com/PatrickWangUESTC/agents.git
cd agents
python3 scripts/agents.py validate
python3 scripts/agents.py init runs/my-task
codex -C runs/my-task
```

也可以在桌面应用中将 `runs/my-task` 作为项目目录打开，再输入你的任务。
例如：“请检查 inputs/ 中的材料，产出 artifacts/report.md，缺失证据明确标注。”
项目配置只在受信任的项目中加载；在 Codex 的正常信任流程中确认你自己的目录。
启动器不修改全局配置，不复制登录凭据，也不自动将目录设为受信任。

## 单任务与批量运行

先准备 workspace、查看实际 prompt 和命令（不会调用模型）：

```bash
python3 scripts/agents.py run \
  --prompt-file workflow/prompts/smoke.md --dest runs/smoke-preview
```

实际执行使用一个新目录，加上 `--execute`：

```bash
python3 scripts/agents.py run \
  --prompt-file workflow/prompts/smoke.md --dest runs/smoke-live --execute

python3 scripts/agents.py batch workflow/tasks.example.json \
  --dest runs/batch-preview --jobs 2

python3 scripts/agents.py batch workflow/tasks.example.json \
  --dest runs/batch-live --jobs 2 --execute
```

`run` 可以用 `--prompt '任务文本'` 替代文件，`--input <目录>` 复制任务输入。
`batch` 的可选 `input` 相对清单文件解析。只复制普通文件和目录，拒绝符号链接。
已有目标目录会报错，重跑请换一个目录；没有隐式覆盖、自动重试或续跑。
每个任务默认超时 1800 秒，可用 `--timeout` 修改。

模型继承当前 Codex 配置，也可显式传 `--model`。`--codex-bin` 可指定 CLI 路径。
启动器通过 stdin 传 prompt，以 `workspace-write` 沙箱和 `approval_policy=never`
运行；需要额外权限的操作可能直接失败。按具体任务配置环境，不绕过沙箱。
用户级工具连接和配置仍可能影响任务，运行目录隔离不是安全容器。

一次 batch 的输出如下：

```text
runs/batch-live/
├── inventory/
│   ├── workspace/                # 独立 Git 根目录、inputs、artifacts
│   └── result/
│       ├── prompt.txt
│       ├── events.jsonl
│       ├── stderr.log
│       ├── final.md
│       └── status.json
├── check-roles/...
└── summary.json
```

未执行状态为 `prepared`；执行后为 `process_completed`、`failed` 或 `timed_out`。
进程完成不等于产物验收，`acceptance` 保留为 `unverified`，需要检查实际输出。
任一任务失败/超时，启动器退出码为 1；配置或输入错误为 2。

## 扩充自己的库

- 通用任务约定放入 `workspace/AGENTS.md`，保持简短。
- 可复用能力放入 `workspace/.agents/skills/<name>/SKILL.md`，包含 YAML 的
  `name` 和 `description`。必要时在同一 skill 下添加 `scripts/`、`references/`
  或 `assets/`；一次性 prompt 留在 `workflow/`。
- 角色放入 `workspace/.codex/agents/<name>.toml`，包含 `name`、`description`
  和 `developer_instructions`。本库的角色没有强制模型覆盖。
- 更改模板只影响以后创建的 workspace；已有任务目录不会被静默同步。

`workflow/` 是本库约定，不是 Codex 自动发现入口。两个 starter skills 和三个角色
提供通用骨架，实际业务工具、领域规则及评测样例需要随具体任务添加。

## 验证范围

```bash
python3 scripts/agents.py validate
python3 -m unittest discover -s tests -v
```

测试用假的 Codex 可执行文件验证复制隔离、并发启动、prompt 传递、日志记录、
失败、超时和已有文件保护。不会调用模型，不证明真实模型的 skill 选择、
subagent 启动或业务产物质量。真实 smoke prompt 位于 `workflow/prompts/smoke.md`。
GitHub Actions 运行相同的离线检查。

已于 2026-11-06 在本机完成真实集成运行：两个 skills 自动发现并读取，三个
自定义角色真实启动，子会话中加载的指令与角色 TOML 一致，生成程序通过功能测试。
详见 [实测记录](docs/live-validation.md)。可使用一个新目录重跑（会调用模型）：

```bash
python3 scripts/agents.py run \
  --prompt-file workflow/prompts/integration.md \
  --input workflow/fixtures/sum --dest runs/integration-live --execute --timeout 600
```

这条命令会使用两个 skills 并调用三个 subagents；验证自动发现需结合会话初始
skills 元数据，角色配置生效需核对真实 spawn 类型和子会话指令。仅有最终文字
声称成功或文件存在不足以证明这两项。实测覆盖当前 CLI 和账号的执行路径；
其他机器的安装、认证和项目配置仍需各自验证。

## 配置依据

配置按 2026-11-06 核对的官方文档组织，CLI 参数对照本机
`codex-cli 0.165.0-alpha.1.2` 的帮助信息。旧版 CLI 的自定义角色格式可能不同。

- [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Skills 与 .agents/skills 发现路径](https://learn.chatgpt.com/docs/build-skills)
- [自定义 subagents 与 .codex/agents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)
