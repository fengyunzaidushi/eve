---
title: "Project Layout"
description: "agent/ 下的 authored slots，以及从 path 派生命名的规则。"
---

eve 通过遍历 `agent/` 下的 filesystem 构建 agent。每个 directory 都是一个 authored slot，文件落入哪个 slot 决定 eve 如何加载它。

## Naming rule

identity 来自 path。你永远不需要在 `define*` call 上写 `name` 或 `id` 字段。

| Path                                  | Resolves to           |
| ------------------------------------- | --------------------- |
| `agent/tools/get_weather.ts`          | tool `get_weather`    |
| `agent/connections/linear.ts`         | connection `linear`   |
| `agent/skills/summarize.md`           | skill `summarize`     |
| `agent/subagents/researcher/agent.ts` | subagent `researcher` |

root agent 的 name 来自外层 `package.json` 的 `name`；当 `package.json` 没有 `name` 时，回退到 app-root directory name。subagent 的 name 来自它的 directory。

## 推荐 layout

```text
my-agent/
├── package.json
├── tsconfig.json
├── agent/
│   ├── agent.ts
│   ├── instructions.md
│   ├── instrumentation.ts
│   ├── channels/
│   ├── connections/
│   ├── hooks/
│   ├── skills/
│   ├── lib/
│   ├── sandbox/
│   ├── tools/
│   ├── schedules/
│   └── subagents/
└── evals/
```

Evals 位于 app root 下的 `evals/`，和 `agent/` 同级，不在其中。见 [Evals](../evals/overview)。

## Slot table

Subagents 列说明 local subagent（`subagents/<id>/`）能否 author 该 slot。声明的 subagent 不会从 root 继承任何内容；它会发现自己的 slots。见 [Subagents](../subagents)。

| Path                                                    | Description                                 | Subagents | Notes                                                                                                                                                                                            |
| ------------------------------------------------------- | ------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `agent.ts`                                              | Runtime config                              | Yes       | Model、modelOptions、compaction、build、experimental。见 [Agent config](../agent-config)。                                                                                                       |
| `instructions.md` / `instructions.ts` / `instructions/` | Base system prompt                          | Optional  | flat file，或包含 `.md` 和 `.ts` files 的 directory。Static sources 在 build time compose。Dynamic sources（`defineDynamic` + `defineInstructions`）在 runtime 解析。root 必需，subagents 可选。 |
| `instrumentation.ts`                                    | Telemetry config                            | No        | OTel exporter 和 AI SDK span settings，会自动发现并在 agent code 前运行。Root-only。                                                                                                             |
| `channels/`                                             | HTTP / messaging entrypoints                | No        | Root-only。                                                                                                                                                                                      |
| `connections/`                                          | External service connections (MCP, OpenAPI) | Yes       | 每个文件一个 connection；name 从 filename 派生。                                                                                                                                                 |
| `hooks/`                                                | Lifecycle 和 stream-event subscribers       | Yes       | 仅 module-backed。支持 recursive directories。                                                                                                                                                   |
| `skills/`                                               | On-demand procedures 和 capability packs    | Yes       | flat markdown、module-backed skills 或 packaged skills。会 seed 到 `/workspace/skills/...`。                                                                                                     |
| `lib/`                                                  | Shared authored helper code                 | Yes       | 仅用于 import；不会 mount 到 workspace。                                                                                                                                                         |
| `sandbox.ts` or `sandbox/sandbox.ts`                    | agent 的单个 sandbox                        | Yes       | 使用 top-level `sandbox.ts` 仅覆盖 definition；使用 `sandbox/sandbox.ts` + `sandbox/workspace/**` 还可以 seed files。两者都未 author 时使用 framework default。                                  |
| `sandbox/workspace/**`                                  | seed 到 sandbox 的 files                    | Yes       | session bootstrap 时镜像到 `/workspace/...`。                                                                                                                                                    |
| `tools/`                                                | Typed executable integrations               | Yes       | 仅 module-backed。                                                                                                                                                                               |
| `schedules/`                                            | Recurring jobs                              | No        | 每个 schedule 是 `<name>.ts`（default-exported `defineSchedule`）或 `<name>.md`（frontmatter `cron:` + prompt body）。支持 recursive nesting。Root-only。                                        |
| `subagents/`                                            | Specialist child agents                     | Yes       | 每个 child 都是 `subagents/<id>/` 下自己的 local package。支持 nested subagents。                                                                                                                |

## 到达 runtime workspace 的内容

eve 不会 mount 整棵 tree。只有两个来源会进入 sandbox workspace：

- `skills/` files → `/workspace/skills/...`
- `agent/sandbox/workspace/**` → session bootstrap 时进入 `/workspace/...`

`lib/` 中的一切都保持为 import-only source code，永远不会进入 workspace。

## Local subagent layout

local subagent 位于 `subagents/<id>/` 下，并使用和 root 相同的 `agent.ts` shape。

```text
agent/subagents/researcher/
├── agent.ts
├── instructions.md
├── connections/
├── hooks/
├── skills/
├── lib/
├── sandbox/
├── tools/
└── subagents/
```

规则：

- `agent.ts` 是必需的，并且必须声明 `description`。parent 会在 lowered subagent tool 上读取它，用来决定何时 delegate。
- `instructions.md` / `instructions.ts` 是可选的（root agent 则必需）。
- `connections/`、`hooks/`、`skills/`、`lib/`、`sandbox/` 和 `tools/` 都受支持，并从 subagent 自己的 directory 发现。
- local subagents 内不支持 `channels/` 和 `schedules/`。
- 支持 nested subagents。

## Flat layout

当 app root 同时也是 agent root 时支持：

```text
my-agent/
├── package.json
├── agent.ts
├── instructions.md
├── tools/
└── skills/
```

优先使用 nested layout。它会把 app root 和 authored surface 分开。

## 为什么 eve 没有发现我的文件？

运行 `eve info`。它会列出 discovered surface 并打印 discovery diagnostics。然后检查文件是否位于正确 authored slot（按上面的 slot table），以及 root-vs-subagent boundary 是否有效。eve 也会在 `.eve/` 下写入可检查 artifacts。见 [instrumentation.ts](../guides/instrumentation) 中的 debugging artifacts，以及 [CLI](./cli) reference。

## 接下来阅读

- [`agent.ts`](../agent-config)：root 上的 runtime config
- [Tools](../tools)：最常用的 authored slot
- [TypeScript API](./typescript-api)：define\* helpers 以及从哪里 import
