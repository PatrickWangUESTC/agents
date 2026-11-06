# N4D generation provider

当前生成后端为 N4D。`mesh-generation` skill 包含标准库适配器，产出稳定的
`job.json` 和原始网格，默认保留原始精度。只有用户明确要求时才派生 lowpoly。以后接 Tripo
时更换提交/查询适配器，下游继续消费产物路径和哈希；Tripo adapter 尚未实现。

## 凭据与任务记录

本机凭据从 `N4D_API_TOKEN` 或 `~/.config/agents-providers/n4d.token` 读取。
token 文件应设为 0600，放在 Git 仓库外。不要把密钥写进 prompt、任务清单、
命令参数或公开日志。授权用户已有的单次生成需求后才加 `--execute`。

在仓库根目录执行：

```bash
python3 workspace/.agents/skills/mesh-generation/scripts/generate.py balance

# 文字输入：先看计划，再在新目录提交一次
python3 workspace/.agents/skills/mesh-generation/scripts/generate.py generate \
  --prompt-file workflow/prompts/n4d-robot.txt --out runs/my-mesh

python3 workspace/.agents/skills/mesh-generation/scripts/generate.py generate \
  --prompt-file workflow/prompts/n4d-robot.txt --out runs/my-mesh --execute

# 图片输入：保留原图，准备并检查抠图，再提交一个候选
python3 workspace/.agents/skills/mesh-generation/scripts/generate.py prepare-image \
  --image local/reference.png --out runs/my-character --execute

# 查看 runs/my-character/matted.png 后执行
python3 workspace/.agents/skills/mesh-generation/scripts/generate.py generate-image \
  --out runs/my-character --execute

# 已有 UUID 的任务中断/超时后，使用同一目录续等，不创建新任务
python3 workspace/.agents/skills/mesh-generation/scripts/generate.py resume \
  --out runs/my-character --timeout 600
```

复制 workspace 后，相应脚本路径为 `.agents/skills/mesh-generation/scripts/`。
原图和预处理图有哈希记录，job.json 保存 provider、job_id、有效请求、状态、
原始产物路径/哈希，以及服务端返回的费用和配置字段。单目录只允许一个写者。

当前只请求一个候选，`disablePbr=1`。该选项关闭 PBR，不能据此声称没有
基础色贴图：实测身体/衣服 GLB 各含一张内嵌图片和一个贴图。旧运行记录里的
`request.texture=false` 是适配器早期的错误解释，不是有效传给服务端的字段；
新记录改为 `pbr=false, texture=provider_default_unverified`。原始产物保持不变，
验收状态始终先设为 unverified；下载成功不等于角色可用。

提交前先持久化 submitting 状态；未拿到 UUID 的不确定提交禁止自动重试。
有 UUID 后可恢复查询或下载。准备图片也保留 matting requestId，重复调用会
恢复该请求。显式校验错误应先修正原因，不应把同一失败请求盲目循环提交。

## 当前接口契约及文档差异

依据 [官方 API 1.2 文档](https://blog.neural4d.com/wp-content/uploads/2026/01/Neural4D-API-Documentation.pdf)
确认主机、鉴权与查询流程，再于 2026-11-06 实测。当前主机为
`https://alb.neural4d.com:3000/api`。

- 余额：`queryPointsInfo`。
- 文生网格：`generateModelWithText`，保存 uuids。
- 图片准备：`mattingImage` → `getMattedResult`，保存 requestId。
- 图生网格：当前实际要求 multipart `image` 文件上传，附 modelCount=1、
  disablePbr=1。旧文档的 fileKey JSON 在实测中被明确拒绝为 HTTP 400，
  服务端提示 Image file is required；该负结果保留，不再使用旧提交方式。
- 查询：`retrieveModel`，0=ready、1=running，负数错误单独报告。
- 下载直接使用返回 URL，不向存储主机转发 API 凭据。

实测图生请求回执包含 `pointsDeducted=20`，与旧文档标价不同；应以实际请求
回执和账户用量为准。网页 Smart Mesh 控件不能证明该 API 支持同名参数，本
适配器没有猜测 topology/modelType/polycount 参数。

## 角色分件顺序

坐姿、裁剪等非规范图先通过图片生成工具生成完整正面 A-pose，核对身份、服装、
手脚和站姿；随后从同一 A-pose 提取 body（含头部和头发）、clothing、shoes
三组独立参考，再逐组 prepare-image、检查 matted.png、generate-image。丝袜默认
归 clothing。鞋及被遮挡身体是推断时必须说明，不能当成原图观测。

brief 设 `reference_preparation.apose_required=true`，账本会增加 apose 依赖门槛。
没有面数预算时 `triangle_budget=null`，不运行减面或体素重建。

N4D 服务可能拒绝并发任务，包括抠图，返回
`Your task is already being processed, please submit again later`。应串行处理，
先完成当前远程任务再提交下一组；保存明确拒绝或不确定响应，不盲目重复扣费。

原始 GLB 可用以下命令只做导入、保存和几何预览，不改变几何：

```bash
blender --background --factory-startup --python-exit-code 1 \
  --python workspace/.agents/skills/mesh-generation/scripts/inspect_blender.py \
  -- runs/my-body/source.glb runs/my-body/inspection --part body
```

中性几何图不代表贴图效果；生成衣服资产也不证明空心、厚度或装配适配。
另一条实测拒绝为 `The task submitted by the user exceeds the limit`：即使队列为
0、已有任务进度 100%、余额充足，也可能出现；原因/额度周期尚未查明。保留响应、
核对历史和余额后最多一次有界人工恢复尝试；仍被拒绝就记录 blocked，不反复重投。

## 可选：派生 lowpoly（用户要求时）

```bash
blender --background --factory-startup --python-exit-code 1 \
  --python workspace/.agents/skills/mesh-generation/scripts/lowpoly_blender.py \
  -- runs/my-character/source.glb runs/my-character/lowpoly --budget 20000
```

输出 source-import.blend、lowpoly.blend、lowpoly.glb、多视角中性几何图以及
lowpoly-report.json。采用本地 Blender DECIMATE/COLLAPSE，保留原始下载文件。
报告核对三角面预算、有限坐标、源文件哈希及 GLB 回读；不证明外观忠实、可靠
变形、无穿插或游戏引擎就绪。程序异常使用 --python-exit-code 1 传播。

预算过低时检查会失败，不会把超标文件标为通过。必要时可以依据新观察调整
预算，或单独测试 `--merge-coincident`；后者是显式的副本拓扑操作，不能视为
保留 rig、UV/morph 对应关系的通用修复。未使用时不合并重合顶点。

如果原件有大量分离碎片、直接减面出现破面，可在新目录明确添加
`--voxel-resolution 500`，先体素重建再减面。它是新的几何候选，会改变表面与
UV/rig 对应关系，不是无损修复；原件、失败版本和同视角对照必须保留。
候选会清除减面后失效的导入自定义法线、重算法线并校验网格数据，再导出回读。

## 实际验证范围

2026-11-06 已成功调用 N4D 文生网格，以及用户提供参考图的图生网格。用户图
和模型只保存在忽略的运行目录/本地交付包，不上传公共仓库。
图生任务拿到真实 UUID 并下载 GLB；首轮 5,000 三角面预算的两次检查失败，
没有将失败结果当作合格低模。具体成功候选的统计与范围以交付报告为准。

离线测试覆盖提交前记录、UUID 续等、下载恢复、不确定提交保护、源文件变化、
multipart 候选数约束、图片准备续等和输入变化保护；这些测试不调用生成服务。

本次坐姿输入已实际执行 A-pose 生成、三组参考提取、N4D 身体与衣服独立生成。
身体与衣服各返回一个 UUID 并下载 GLB。衣服夹带大腿连接面，严格分件验收未通过；
局部清理候选保留，但衣物内部和装配仍待检。鞋组参考/抠图完成，模型生成被提交
上限拒绝，未得到 UUID。不能据此声称三组模型全部生成或角色完整可用。
当前共 29 项离线测试通过，包括新增 A-pose 依赖失效和拒绝响应持久化测试。
