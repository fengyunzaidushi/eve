---
title: "CLI"
description: "eve CLI 每个 command 的 reference：init、info、build、start、dev、link、deploy、eval 和 channels。"
---

`eve` binary（`bin: eve`）从你的 app root 运行，每个 command 都会先从该 root 加载 `.env`/`.env.local`。不带 command 运行 `eve` 会执行 `eve dev`。

## Commands

| Command                   | Description                                                                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `eve init [target]`       | scaffold 一个新 agent，或把 agent 添加到已有 project directory                                                                        |
| `eve info`                | 打印解析后的 application，包括已发现的 tools、skills、subagents、schedules、channels、routes、artifact paths 和 discovery diagnostics |
| `eve build`               | 编译 `.eve/` artifacts 并构建 host output；打印 output directory                                                                      |
| `eve start`               | 服务 built `.output/` app；打印 listening URL                                                                                         |
| `eve dev`                 | 启动 local dev server 并打开 terminal UI                                                                                              |
| `eve dev <url>`           | 将 UI 连接到已有 server URL（例如 remote deployment），而不是启动 local server                                                        |
| `eve link`                | 将目录链接到 Vercel project 并拉取 AI Gateway credentials                                                                             |
| `eve deploy`              | 将 agent 部署到 Vercel production（需要时会先 link）                                                                                  |
| `eve eval`                | 针对 local app 或 remote target 运行 evals                                                                                            |
| `eve channels add [kind]` | 交互式 scaffold channel，或按 kind（`slack` \| `web`）scaffold                                                                        |
| `eve channels list`       | 列出 user-authored channels                                                                                                           |

当 `eve build` 因 discovery errors 失败时，它会打印完整 diagnostics report（severity、message、source path）和 diagnostics artifact path。

## `eve init`

```bash
eve init [target] [--channel-web-nextjs]
```

可选 `target` 决定 mode：

- 名称（`eve init my-agent`）会在新的 `my-agent/` directory 中 scaffold fresh project。
- 已有目录，包括当前目录 `.`（`eve init .`），会把 agent 添加到该 project。project 需要有 `package.json`，`agent/` files 必须尚不存在，缺失的 `eve`、`ai` 和 `zod` dependencies 会在不触碰其他内容的情况下添加。
- 省略 target 会 scaffold 或更新当前目录，等同于 `eve init .`。

两种 mode 都会安装 dependencies、初始化 Git，并通过检测到的 project package manager 运行 `eve dev`。fresh projects 会在存在 parent workspace manager 时继承它；否则使用启动 `eve init` 的 manager。

| Flag                   | Type | Default | Description                                                                                                      |
| ---------------------- | ---- | ------- | ---------------------------------------------------------------------------------------------------------------- |
| `--channel-web-nextjs` | flag | off     | 添加 Web Chat application（Next.js app）。添加到已有 project 时会被拒绝；之后在那里运行 `eve channels add web`。 |

## `eve info`

```bash
eve info [--json]
```

| Flag     | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `--json` | flag | off     | 输出为 JSON |

当行为异常时先运行它。它能确认某个文件是否被发现、列出 active surface，并展示 discovery diagnostics，比启动 dev server 更快。

## `eve build`

```bash
eve build
```

没有 flags。编译到 `.eve/` 并构建 host output，然后打印 built output path。

`.eve/` 下写入的有用 artifacts（即使 partial failure 也会保留）：

| Artifact                                       | Description                                       |
| ---------------------------------------------- | ------------------------------------------------- |
| `.eve/discovery/agent-discovery-manifest.json` | eve 在磁盘上发现了什么                            |
| `.eve/discovery/diagnostics.json`              | authored-shape errors 和 warnings                 |
| `.eve/compile/compiled-agent-manifest.json`    | eve 在 runtime 加载的 serialized authored surface |
| `.eve/compile/compile-metadata.json`           | build-time metadata 和 paths                      |
| `.eve/compile/module-map.mjs`                  | eve 在 runtime 导入的 compiled module entrypoints |

## `eve start`

```bash
eve start [--host <host>] [--port <port>]
```

| Flag            | Type   | Default            | Description             |
| --------------- | ------ | ------------------ | ----------------------- |
| `--host <host>` | string | all interfaces     | 要绑定的 host interface |
| `--port <port>` | number | `$PORT`，然后 3000 | 监听端口                |

服务之前 build 出的 output。打印 listening URL。

## `eve dev`

```bash
eve dev [options]
eve dev https://your-app.vercel.app
```

把裸 URL 作为唯一参数传入时，UI 会连接到那个 server，而不是启动本地 server（等同于 `--url`），这让你可以 smoke-test preview 或 production deployment。非 TTY terminal 中会关闭 interactive UI。

| Flag                                | Type   | Default            | Description                                                                               |
| ----------------------------------- | ------ | ------------------ | ----------------------------------------------------------------------------------------- |
| `--host <host>`                     | string | all interfaces     | 要绑定的 host interface                                                                   |
| `--port <port>`                     | number | `$PORT`，然后 3000 | 监听端口                                                                                  |
| `-u, --url <url>`                   | string | none               | 连接到已有 server URL，而不是启动一个                                                     |
| `--no-ui`                           | flag   | UI on              | 启动 server，但不打开 interactive UI                                                      |
| `--name <name>`                     | string | app folder name    | terminal UI 中显示的 title                                                                |
| `--input <text>`                    | string | none               | 启动 UI 后预填 prompt input（可编辑，不自动提交）                                         |
| `--tools <mode>`                    | enum   | `auto-collapsed`   | Tool-call rendering：`full` \| `collapsed` \| `auto-collapsed` \| `hidden`                |
| `--reasoning <mode>`                | enum   | `full`             | Reasoning rendering：`full` \| `collapsed` \| `auto-collapsed` \| `hidden`                |
| `--subagents <mode>`                | enum   | `auto-collapsed`   | Subagent-section rendering：`full` \| `collapsed` \| `auto-collapsed` \| `hidden`         |
| `--connection-auth <mode>`          | enum   | `full`             | Connection-authorization rendering：`full` \| `collapsed` \| `auto-collapsed` \| `hidden` |
| `--assistant-response-stats <mode>` | enum   | `tokensPerSecond`  | Assistant header statistic：`tokens` \| `tokensPerSecond`                                 |
| `--context-size <tokens>`           | number | none               | Model context window size，显示为 usage percentage                                        |
| `--logs <mode>`                     | enum   | `stderr`           | 要显示的 server/agent logs：`all` \| `stderr` \| `sandbox` \| `none`                      |

Local dev 会把 active server process ID 写入 `.eve/dev-process.pid`。如果同一 agent 的另一个 `eve dev` 在该 process 仍运行时启动，eve 会退出，并给出包含停止现有 server 的 command 的消息。

Local dev 会在 `.eve/dev-runtime/snapshots/` 下保存 immutable runtime source snapshots，让 in-flight sessions 持有一致的 code revision，同时新 prompts 能接收 rebuilds。启动时，`eve dev` 会在后台清理 stale runtime snapshots 和旧 local sandbox templates。手动清理时，停止 `eve dev` 后删除 `.eve/dev-runtime/snapshots/` 或 `.eve/sandbox-cache/local/templates/`。

## `eve link`

```bash
eve link
```

将当前目录链接到已有 Vercel project。你会选择 team，再选择 project；eve 会拉取 project environment，让 AI Gateway credential（`VERCEL_OIDC_TOKEN` 或 `AI_GATEWAY_API_KEY`）进入 `.env.local`，然后验证确实拿到了一个 credential。再次运行会 re-link：pickers 总会运行，新选择会生效。该 command 仅支持交互式；在 CI 中，请改用 `vercel link --project <name> --yes`。运行中的 `eve dev` 会自动 reload env files，因此 pull 后不需要重启。

## `eve deploy`

```bash
eve deploy
```

将 agent 部署到 Vercel production（`vercel deploy --prod`），会先安装 dependencies 并在之后拉取 environment variables。已经 link 的 project 无论是否有 TTY 都能 deploy（non-interactive runs 会传递 non-interactive `vercel` flags）。未 link 的目录在有 terminal 时会走 `eve link` pickers，否则退出并给出 guidance。

## `eve eval`

```bash
eve eval [evalId...] [--url <url>] [options]
```

未给 eval ids 时运行所有发现的 evals；ids 会 exact match 或按 directory prefix 匹配（`eve eval weather` 运行 `evals/weather/` 下的所有内容）。当所有 eval 都通过 checks 时退出 `0`；任何 eval 失败时（failed check、execution error 或 `--strict` threshold miss）退出 `1`；configuration errors 退出 `2`。

| Flag                    | Type   | Default | Description                                    |
| ----------------------- | ------ | ------- | ---------------------------------------------- |
| `--url <url>`           | string | none    | Remote agent URL（跳过 local host startup）    |
| `--tag <tag...>`        | string | none    | 只运行带某个 tag 的 evals                      |
| `--strict`              | flag   | off     | 低于 threshold 的 scores 也会让 exit code 失败 |
| `--list`                | flag   | off     | 打印发现的 evals，但不运行                     |
| `--timeout <ms>`        | number | none    | 每个 eval 的 timeout，单位 milliseconds        |
| `--max-concurrency <n>` | number | 8       | 最大 concurrent eval executions                |
| `--json`                | flag   | off     | 以 JSON 输出 results                           |
| `--junit <path>`        | string | none    | 将 JUnit XML results 写入文件                  |
| `--skip-report`         | flag   | off     | 跳过 eval-defined reporters（例如 Braintrust） |
| `--verbose`             | flag   | off     | 将每个 eval 的 `t.log` lines stream 到 stdout  |

编写 evals 见 [Evals](../evals/overview)。

## `eve channels add`

```bash
eve channels add [kind] [-f] [-y]
```

将 channel scaffold 到 `agent/channels/`。不带 `kind` 时交互式提示；传入 `kind`（`slack` \| `web`）时直接 scaffold。

| Flag          | Type | Default | Description                                |
| ------------- | ---- | ------- | ------------------------------------------ |
| `-f, --force` | flag | off     | 覆盖已有 channel files                     |
| `-y, --yes`   | flag | off     | confirmation 默认 yes；要求显式传入 `kind` |

## `eve channels list`

```bash
eve channels list [--json]
```

列出当前 project 中的 user-authored channels。

| Flag     | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `--json` | flag | off     | 输出为 JSON |

## 推荐 loop

1. 编辑 `agent/` 下的 files。
2. 运行 `eve info` 确认 discovery，或读取 diagnostics。
3. 本地迭代时运行 `eve dev`。
4. 发布前运行 `eve build`。
5. 运行 `eve start`，本地 smoke-test built output。

相关：[Project layout](./project-layout) · [instrumentation.ts](../guides/instrumentation)。

## 接下来阅读

- [Project layout](./project-layout)：`eve info` 会发现什么
- [instrumentation.ts](../guides/instrumentation)：tracing 和 error catalog
- [Deployment](../guides/deployment)：production 中的 `eve build` 和 `eve start`
