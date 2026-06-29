---
title: "Sandbox"
description: "agent 的 isolated bash environment，包括 built-in file tools、seeded /workspace、backends、lifecycle 和 network policy。"
---

sandbox 是 agent 的 isolated bash environment：一个以 `/workspace` 为 root 的 filesystem，agent 可以在其中运行 shell commands、执行 scripts，并读写 files，而不会触碰你的 app runtime。每个 eve agent 正好有一个 sandbox。built-in `bash`、`read_file`、`write_file`、`glob` 和 `grep` tools 已经以它为目标，你的 authored code 也可以使用它。

默认情况下已经有可工作的 sandbox，不需要编写任何内容。只有在需要添加 setup、seed files、选择 backend 或锁定 network 时才覆盖它。

default sandbox 不能替代你的 application 所需的 network policy、credentials、retention、deletion 或其他 controls 配置。

## 使用 sandbox

model 已经通过 default tools 拥有 shell 和 file access：

| Tool                       | 作用                            |
| -------------------------- | ------------------------------- |
| `bash`                     | 在 sandbox 中运行 shell command |
| `read_file` / `write_file` | 读写 `/workspace` 下的 files    |
| `glob`                     | 按 pattern 查找 files           |
| `grep`                     | 搜索 file contents              |

它们都以 `/workspace` 作为 working directory 运行。任何 authored runtime function（tool、step、model callback）都可以用 `ctx.getSandbox()` 获取 live sandbox handle。

```ts title="agent/tools/run_analysis.ts"
import { defineTool } from "eve/tools";
import { z } from "zod";

export default defineTool({
  description: "Run a Python analysis script and return its output.",
  inputSchema: z.object({ script: z.string() }),
  async execute({ script }, ctx) {
    const sandbox = await ctx.getSandbox();
    await sandbox.writeTextFile({ path: "analysis/run.py", content: script });
    const result = await sandbox.run({ command: "python analysis/run.py" });
    return { stdout: result.stdout };
  },
});
```

`ctx.getSandbox()` 不接受参数，是 async 的，并且只在 authored runtime execution 内工作。

`/workspace` 是跨所有 backend 的同一个 namespace，因此无论 backend 是 local 还是 Vercel，`/workspace/foo` 都指向同一个文件。当你需要把 path 插入 generated command 时，`sandbox.resolvePath("repo/build.py")` 会把 relative path anchor 到其 absolute `/workspace/repo/build.py` 形式。

该 handle 不只提供 `run` 和 `writeTextFile`。在每个 method 中，relative paths 都从 `/workspace` 解析，absolute paths 则原样通过：

| Method                                   | 作用                                                                                    |
| ---------------------------------------- | --------------------------------------------------------------------------------------- |
| `run({ command })`                       | 运行一个 command，阻塞到退出，并返回 `{ stdout, stderr, ... }`                          |
| `spawn(options)`                         | 启动 long-running process（server、watcher），并返回 `SandboxProcess` handle            |
| `readTextFile` / `writeTextFile`         | 读写 UTF-8（或指定 encoding）file；`readTextFile` 支持 1-based line ranges              |
| `readBinaryFile` / `writeBinaryFile`     | 读写 raw bytes（images、archives、任何非文本内容）                                      |
| `readFile` / `writeFile`                 | 以 bytes stream file in/out                                                             |
| `removePath({ path, force, recursive })` | 删除一个 file 或 directory；`force` 忽略 missing paths，`recursive` 移除 non-empty dirs |
| `resolvePath(path)`                      | 将 relative path anchor 到其 absolute `/workspace/...` 形式                             |
| `setNetworkPolicy(policy)`               | 在 mid-turn 改变 egress policy（取决于 backend；见 [Network policy](#network-policy)）  |

由于 `run` 会阻塞到 command 退出，当 process 应在 agent 做其他工作时继续运行，请使用 `spawn`：

```ts
const sandbox = await ctx.getSandbox();
const server = await sandbox.spawn({ command: "python -m http.server 8000" });
// ...do other work against the server...
await server.kill();
```

`SandboxProcess` 暴露 `stdout`/`stderr` byte streams、`wait()`（以 exit code resolve）和 `kill()`（幂等）。

`sandbox.id` 是 stable per-session identifier，会在同一 logical session 的 reconnects 之间保留。可将其用作必须超过单个 step executions 生命周期的 per-session state 的 cache key。

option types（`SandboxSpawnOptions`、`SandboxReadBinaryFileOptions`、`SandboxWriteBinaryFileOptions` 等）与 `SandboxProcess` 一起作为 named exports 从 `eve/sandbox` 导出。

## Seeding `/workspace`

将 authored files 放在 `agent/sandbox/workspace/` 下，即可在 session start 时把它们 mount 到 sandbox 中。这需要 folder layout（`agent/sandbox/sandbox.ts`），而不是 top-level shorthand：

```text
agent/sandbox/
  sandbox.ts                ← optional override (see below)
  workspace/
    schema.sql              ← lands at /workspace/schema.sql
    scripts/run.sh          ← lands at /workspace/scripts/run.sh
```

`workspace/` 下的每个 file 都会以完整结构 mirror 到 sandbox cwd 中，eve 还会自动在 prompt 中向 model 列出 top-level entries。有一个 subtree 不允许使用。Skill discovery 已经会把 skill files seed 到 `/workspace/skills/` 下，因此编写 `agent/sandbox/workspace/skills/...` 会被拒绝；请改放到 `agent/skills/` 下。

## 覆盖 sandbox

若要添加 setup、seed files 或选择 backend，请编写 `defineSandbox`。有两种 layout：

- `agent/sandbox.ts`：shorthand。当你只需要 definition、不需要 seeded files 时使用。
- `agent/sandbox/sandbox.ts`：folder layout。当你还要 seed `agent/sandbox/workspace/**` 时使用。如果两者都存在，folder layout 胜出。

```ts title="agent/sandbox/sandbox.ts"
import { defineSandbox } from "eve/sandbox";
import { vercel } from "eve/sandbox/vercel";

export default defineSandbox({
  backend: vercel({ runtime: "node24", resources: { vcpus: 2 } }),
  revalidationKey: () => "repo-bootstrap-v1",
  async bootstrap({ use }) {
    const sandbox = await use();
    await sandbox.run({ command: "apt-get install -y jq" });
  },
  async onSession({ use }) {
    await use({ networkPolicy: "deny-all" });
  },
});
```

`defineSandbox` 和 `defaultBackend` 位于 `eve/sandbox`。省略 `backend` 时，runtime 会 fallback 到 `defaultBackend()`（见 [Backends](#backends)）。

## Backends

backend 决定 sandbox 在哪里运行。eve 从嵌套的 `eve/sandbox/*` imports 提供四个 pinned factories，并从 `eve/sandbox` 提供一个 availability-aware default：

| Backend            | sandbox 运行位置                                                                          |
| ------------------ | ----------------------------------------------------------------------------------------- |
| `vercel()`         | 在 [Vercel Sandbox](https://vercel.com/docs/sandbox) 上运行。                             |
| `docker()`         | 通过 `docker` CLI 驱动，在本地 Docker container 中运行。                                  |
| `microsandbox()`   | 在本地轻量 [microsandbox](https://www.npmjs.com/package/microsandbox) VM 中运行。         |
| `justbash()`       | 在本地 pure-JS `just-bash` interpreter 中运行（无 daemon 或 VM，但也没有真实 binaries）。 |
| `defaultBackend()` | 选择最佳可用项：hosted Vercel 上的 Vercel Sandbox → Docker → microsandbox → just-bash。   |

配置 pinned factory 会无条件使用该 backend。`docker()` 始终要求可访问的 Docker daemon，`vercel()` 始终创建 hosted sandboxes（包括在 local dev 中使用 Vercel credentials 时）。

省略 `backend` 时，eve 使用 `defaultBackend()`，它会在首次使用时按优先级解析：

1. **Vercel Sandbox**：部署在 Vercel 上时（设置了 `process.env.VERCEL`），因为 local container/VM runtimes 无法在那里运行。
2. **Docker**：可通过 Docker-compatible `docker` CLI 访问 daemon 时（Docker Desktop、OrbStack、Colima、通过 docker-compatible CLI 的 Podman；可用 `EVE_DOCKER_PATH` 覆盖 binary）。
3. **microsandbox**：host 支持时，即 Apple Silicon 上的 macOS，或启用了 KVM 的 glibc Linux。
4. **just-bash**：作为 dependency-free fallback。

`defaultBackend()` 也接受 keyed bag，让每个 inner backend 获得自己的 typed create options：

```ts
import { defaultBackend, defineSandbox } from "eve/sandbox";

export default defineSandbox({
  backend: defaultBackend({
    vercel: { networkPolicy: "deny-all", resources: { vcpus: 4 } },
    docker: { image: "ghcr.io/vercel/eve:latest" },
    microsandbox: { memoryMiB: 2048 },
  }),
});
```

### Docker

`docker()` 直接驱动 Docker CLI。默认 base image 是 `ghcr.io/vercel/eve:latest`，即 eve 发布的 sandbox runtime image。在 authored bootstrap code 运行前，eve 会在 framework setup 期间创建 `/workspace` 并验证 Bash。通过 `docker({ image, env, pullPolicy, networkPolicy })` 配置它，并在 sandbox bootstrap 中安装 authored runtime tools，或通过 custom image 提供它们。当 sandbox source、seed files、`revalidationKey` 和 Docker backend options 仍匹配时，templates 会作为 local Docker images commit 并跨 sessions 复用。Sessions 作为 long-lived containers 运行，其 filesystems 会为同一个 durable session 跨 turns 保留 `/workspace` changes。`eve dev` 会在后台 prune stale template images。

### microsandbox

`microsandbox()` 会在轻量 local VM 中运行每个 sandbox，带有 snapshot-backed templates、`vercel-sandbox` user，以及支持 domain-level network policies 和 credential brokering 的 firewall。它是与 hosted Vercel Sandbox 最接近的本地匹配项。默认 base image 是 `ghcr.io/vercel/eve:latest`，即 eve 发布的 sandbox runtime image。在 authored bootstrap code 运行前，eve 会在 framework setup 期间验证 Bash，并创建 `/workspace` 和 sandbox user。请在 sandbox bootstrap 中安装 authored runtime tools，或通过 custom image 提供它们。支持的 hosts 是 Apple Silicon 上的 macOS，或带 KVM 的 Linux（glibc）。`microsandbox` npm package 及其 VM runtime 不随 eve 捆绑，因此缺失时 `eve dev` 会自动安装二者（可用 `setup: { autoInstall: false }` 禁用）；production processes 则会失败并给出 actionable install errors。

### just-bash

`justbash()` 不需要 daemon 或 VM，但 commands 会在 simulated bash 中运行，virtual filesystem 位于 `.eve/sandbox-cache/` 下，没有真实 binaries（`git`、`node`、package managers），也没有 network isolation。`just-bash` package 是 optional peer dependency，因此缺失时 `eve dev` 会自动把它安装到你的 application 中（可用 `autoInstall: false` 禁用）；production processes 则会失败并给出 actionable install error。

你也可以编写自己的 backend。`SandboxBackend` 是一个 adapter object，包含 `name`、`create` 和可选的 `prewarm`。它可以指向你自己的 container runner、VM pool、internal sandbox service 或其他 isolation layer，只要它返回 eve 需要的 `SandboxSession` operations 即可。见 `eve/sandbox` 上的 `SandboxBackend*` types。

## Lifecycle

有两个 hooks，作用域不同：

- **`bootstrap({ use })`** 是 template-scoped 的，会在 template 构建时运行一次。把每个后续 session 都会继承的 reusable setup 放在这里，例如 clone baseline repo、安装 dependencies 或 seeding files。调用 `use()` 获取 `SandboxSession`。只有 template filesystem state 和受支持的 backend metadata 会进入后续 sessions；network policy 这类 config 不会。如果 external inputs 会影响 bootstrap 的产物，请设置 `revalidationKey: () => string`，让 eve 知道何时 rebuild template（authored sandbox source 和 seed contents 已经会为你 tracking）。
- **`onSession({ use, ctx })`** 是 durable-session-scoped 的，每个 session 运行一次。把 per-session setup 放在这里，包括 network policy、resources、timeout、per-user credentials 和 one-time markers。由于它运行在 active runtime context 内，因此可以读取 `ctx.session` 并派生当前 principal，而不会把 credentials bake 到 template 中。调用 `use(opts?)` 获取 `SandboxSession`；`opts` 会在 create 后流向 backend 的 update path。

如果每个 session 都需要 network policy 或其他配置，请在 backend factory 或 `onSession` 中配置；不要依赖 bootstrap-only configuration。

```ts
import { defineSandbox } from "eve/sandbox";
import { vercel } from "eve/sandbox/vercel";

export default defineSandbox({
  backend: vercel(),
  async onSession({ use, ctx }) {
    const sandbox = await use({ networkPolicy: "deny-all" });
    const user = ctx.session.auth.current;
    if (user === null) return;
    await sandbox.writeTextFile({ path: "SESSION_USER.txt", content: `${user.principalId}\n` });
  },
});
```

Sessions 是 persistent 的，底层 runtime 如何 idle out 取决于 backend。在 Vercel backend 上，VM 会在一段不活跃时间后 timeout（默认 30 分钟）；eve 会保留 filesystem，并在下一条 message 到来时恢复 sandbox，就像什么都没发生过一样，即使已经过去数天。Docker backend 为每个 durable session 保留 long-lived container，并在没有该 timeout 的情况下跨 turns 持久化 `/workspace`；just-bash backend 则把 virtual filesystem 存储在 `.eve/sandbox-cache/` 下。无论哪种情况，同一个 session 的 `/workspace` 都会在 turns 之间保留。

## Network policy

Egress rules 放在 backend factory 上，或放在 `onSession` 的 `use()` 中。有三种形式：

```ts
networkPolicy: "allow-all"; // default
networkPolicy: "deny-all";  // block all egress, including DNS

networkPolicy: {
  allow: ["ai-gateway.vercel.sh", "*.github.com"],
  subnets: { deny: ["10.0.0.0/8"] },
};
```

默认 egress 是 `allow-all`。对于非公开、敏感、受监管或 production workloads，在运行 untrusted tools 或处理 sensitive data 前，请配置 `deny-all` 或显式 allow-list。

把它设置在 factory 上（`vercel({ networkPolicy: "deny-all" })`），它会在 authored `bootstrap` code 运行前生效；framework-owned base setup 可能会短暂保持 egress open 以安装必需 packages。把它设置在 `onSession` 的 `use()` 中可以 per-session 覆盖。常见模式会结合两者：让 factory 保持 open，以便 `bootstrap` 可以 `git clone`，然后在 `onSession` 中锁定。若要在 mid-turn 改变 policy，请在 live handle 上调用 `sandbox.setNetworkPolicy(...)`。

`vercel()` 和 `microsandbox()` 支持 domain-level allow-lists 和 credential brokering。Docker backend 只遵守 `"allow-all"` 和 `"deny-all"`（在 creation 时以及通过 `setNetworkPolicy`）；just-bash backend 会完全拒绝 `setNetworkPolicy`。

## Credential brokering

Secrets 永远不会进入 sandbox。相反，network policy 的 per-domain `transform` 会在 firewall 处注入 credentials，因此 header 可以 authenticate 到 host 的 egress，同时 secret 完全留在 sandbox process 之外：

```ts
async onSession({ use }) {
  await use({
    networkPolicy: {
      allow: {
        "github.com": [{ transform: [{ headers: { authorization: "Basic your_base64_credentials_here" } }] }],
        "*": [],
      },
    },
  });
}
```

`"*": []` catch-all 会保持 general egress open，同时 `transform` 只应用于 `github.com`。对于 mid-turn brokering，请用相同 shape 调用 `setNetworkPolicy`。brokering 机制本身见 [Vercel Sandbox docs](https://vercel.com/docs/sandbox)。

## 接下来阅读

- [Subagents](./subagents)：每个 subagent 都获得自己的 sandbox，独立于 parent。
- [Tools](./tools)：authored tools 在 app runtime 中运行（完整 `process.env`）；只有 sandbox tools 在 sandbox 中运行。
- [Security model](./concepts/security-model)：完整 app-runtime/sandbox trust boundary。
- [Vercel Sandbox](https://vercel.com/docs/sandbox)：platform docs，包括 credential brokering 和 persistence limits。
