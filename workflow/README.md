# 工作方式

`workflow/` 是本库的组织约定，Codex 不会自动加载其中的文件。
任务 prompt 由启动器传入；角色文件由 workspace 的 `.codex/agents/` 提供。

1. 将任务目标、输入路径、输出形式和验收条件写进 prompt。
2. 从 `workspace/` 复制一个完整工作目录，按需复制任务输入。
3. 用 Codex 打开这个目录，或通过启动器调用 `codex exec -C <workspace>`。
4. 检查 `artifacts/` 的实际产物及证据。根据失败案例迭代对应 skill。

单任务可以由主 agent 自己完成；如果明确要求协作，可以让
`evidence_reader` 查材料、`implementer` 产出、`acceptance_reviewer` 复核。
每个角色继承运行环境权限，prompt 中的“只读”不等于 OS 级只读隔离。

批量任务是另一层并发：一个清单条目启动一个独立 Codex 进程，各有自己的
workspace。`--jobs` 控制进程数，配置中的 subagent 上限只作用于单个任务。
运行目录隔离防止文件相互覆盖，但不是容器隔离；用户级配置、登录和工具连接
仍由同一运行环境提供。对强隔离有要求时，在独立容器/账号中运行。

清单是 JSON 数组。每项有唯一 `id`、非空 `prompt`，可选 `input` 为目录路径，
相对路径以清单所在目录为基准。请将私有清单和输入放到被 Git 忽略的 `local/`。
批量运行前会检查整份清单，避免跑到一半才发现重复 ID 或不存在的输入。
