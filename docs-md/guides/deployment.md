---
title: "Deployment"
description: "将 eve agent 发布到 Vercel 或你自己的 host 的生产 checklist，涵盖 build output、env 和 secrets、sandbox backend、auth、deploy 和 verify。"
---

eve 在本地、Vercel 和长期运行的 Node host 上运行方式相同，所以把 agent 从 `eve dev` 带到生产环境主要是机械流程。按顺序完成这份 checklist。

## 1. Build

`eve build` 会编译 agent 并写入 host output：

```bash
eve build
```

设置 `VERCEL` 时（每个 hosted Vercel build 都会设置），`eve build` 会把 [Vercel Build Output](https://vercel.com/docs/build-output-api) bundle 写到 `.vercel/output` 下。普通本地 `eve build` 会跳过这个 bundle。无论哪种方式，你都会在 `.eve/` 下得到 eve 的 compiled framework artifacts，包括 discovery manifest、compiled manifest、diagnostics 和 module map。打开它们可以看到 deployment 会加载哪个 authored surface。artifact guide 以及 `eve build` 失败时的处理方式见 [Observability](./instrumentation)。

### Portability 如何工作

Nitro 是 HTTP host layer。它给 eve 一个 build artifact，用来在 dev server 之外服务 health、session、stream、channel、callback 和 schedule routes。Workflow execution 和 sandbox execution 是独立的 runtime adapters；它们不是藏在 Nitro 里的 Vercel dependencies。

在 Vercel 上，eve 会发出 Vercel Build Output，Workflow SDK 运行在 Vercel Workflow 上，`defaultBackend()` 选择 Vercel Sandbox。在 Vercel 之外，`eve start` 服务标准 Nitro Node output，Workflow SDK 默认使用它的 local world，`defaultBackend()` 按可用性顺序选择 local sandbox backend。这个 local workflow world 会把 run state 持久化到磁盘，并且不直接耦合 Vercel；latest-deployment routing 和 dashboard run attributes 等 Vercel-only 行为只是增量能力。

eve 目前没有把 Workflow world selection 作为 public app API 暴露。未来版本会允许高级 deployments 提供不同的 Workflow world，也就是 workflow state、queues、auth 和 streaming 的 SDK abstraction；底层概念见 [Workflow Worlds](https://workflow-sdk.dev/worlds)。

## 2. Environment variables 和 secrets

在你的 deployment environment 或 secret manager 中设置这些值，绝不要放在 source 或 compiled artifacts 中：

- **一个 model credential。** 设置最少的 Vercel 选项是 Vercel AI Gateway。链接一个 Vercel project 后，像 `anthropic/claude-opus-4.8` 这样的 gateway model ids 会通过 Vercel OIDC 认证，不需要管理 provider keys。在 Vercel 之外，要么为 gateway-routed models 设置 `AI_GATEWAY_API_KEY`，要么用 [AI SDK provider package](https://ai-sdk.dev/docs/foundations/providers-and-models) 配置 direct provider model，并设置该 provider 的 key，例如 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`。
- **Route-auth secrets**，例如 `ROUTE_AUTH_BASIC_PASSWORD`，以及你的 channel `auth` 引用的任何 JWT/OIDC signing keys（见 [Auth and route protection](./auth-and-route-protection)）。

Route-auth secrets 永远不会序列化进 compiled discovery 或 module-map artifacts。runtime 会从 authored channel definition 中重新 materialize 它们。如果你的 deployment 位于 Vercel preview protection 后面，并且想用 `eve dev` 驱动它，请在启动前本地设置 `VERCEL_AUTOMATION_BYPASS_SECRET`。

## 3. Model routing

`agent/agent.ts` 中 `model` 的形状决定 eve 是调用 Vercel AI Gateway，还是直接调用 provider endpoint。

字符串 model id 会走 gateway routing：

```ts title="agent/agent.ts"
import { defineAgent } from "eve";

export default defineAgent({
  model: "anthropic/claude-opus-4.8",
});
```

这在 Vercel 上可以通过 project OIDC 工作，在其他地方可以通过 `AI_GATEWAY_API_KEY` 工作。通过 `modelOptions.providerOptions.gateway.byok` 传 provider key 也仍然会通过 Gateway 发送请求；它只改变 Gateway 使用哪个 upstream key。

如果要完全避开 Gateway，请安装你想调用的 provider 对应的 [AI SDK package](https://ai-sdk.dev/docs/foundations/providers-and-models)，传入该 provider 的 model object，并设置该 provider 的常规 environment variable：

```bash
npm install @ai-sdk/anthropic
```

```ts title="agent/agent.ts"
import { anthropic } from "@ai-sdk/anthropic";
import { defineAgent } from "eve";

export default defineAgent({
  model: anthropic("claude-opus-4.8"),
});
```

使用这种形状时，model call 会直接发往 Anthropic，runtime 会读取 `ANTHROPIC_API_KEY`。安装 `@ai-sdk/openai`、使用 `openai("...")` 并设置 `OPENAI_API_KEY` 后，OpenAI 也使用同样模式。当你 self-deploy 且不想依赖任何 Vercel-managed services 时，这通常是首选。

## 4. Sandbox backend

在 Vercel 上，[sandbox](../sandbox) 运行在 hosted [Vercel Sandbox](https://vercel.com/docs/sandbox) infrastructure 上。在 sandbox definition 上附加 backend：

```ts title="agent/sandbox/sandbox.ts"
import { defineSandbox } from "eve/sandbox";
import { vercel } from "eve/sandbox/vercel";

export default defineSandbox({
  backend: vercel(),
});
```

不写 `backend` 时，eve 会回退到 `defaultBackend()`，它在 hosted builds 上选择 Vercel backend，在其他地方选择 local backend。一个 definition，同用两种环境。

对于 self-deployed process，保留 `defaultBackend()`，或选择显式的 non-Vercel backend，例如 Docker 或 microsandbox。如果这些都不匹配你的 infrastructure，请编写 custom `SandboxBackend` adapter，在你自己的 container、VM 或 isolation service 中创建 sessions。不要 pin `vercel()`，除非该 process 本来就应该创建 hosted Vercel sandboxes。

## 5. Build-time sandbox prewarm

在 hosted builds 期间，eve 会预热可复用的 Vercel sandbox templates，避免第一个 session 承担 cold-start 成本：

- 只有同时存在 `VERCEL` 和 `VERCEL_DEPLOYMENT_ID` 时才会运行 prewarm。
- 没有 `bootstrap()` 且没有 workspace seed files 的 sandbox 会被跳过。
- Seed-only templates 按 skills 和 workspace file contents 建 key，所以 unchanged seeds 可以跨 deploys 复用 template。
- 带 `bootstrap()` 的 templates 会按可选的 resolved `revalidationKey()`、authored sandbox source 和 seed contents 建 key，所以输入匹配时可以跨 deploys 复用 template。
- 每个 template 都会在 build log 中显示为 `reused cached` 或 `built`。
- Prewarming 只覆盖 template construction。`onSession()` 仍然在 runtime 按每个 session 运行一次。
- **如果 build-time prewarm 失败，build 也会失败。**

如果设置了 `VERCEL` 但缺少 `VERCEL_DEPLOYMENT_ID`，eve 会警告已跳过 prewarming。不要用 `vercel deploy --prebuilt` 部署该 build；它的 output 可能引用从未 provision 的 sandbox templates。请改用 `vercel deploy`，让 Vercel 在 hosted build environment 中构建 source。

## 6. Auth

在第一个 production browser request 到达 app 之前，把所有 scaffolded `placeholderAuth()` 换成你的真实 policy。framework default 和 placeholder 都会拒绝 production browser traffic，因此未配置的 app 会 fail closed，而不是开放 routes。production policy 可以是内置 helper（`httpBasic()`、`jwtHmac()`、`jwtEcdsa()`、`oidc()`、`vercelOidc()`），也可以是 custom `AuthFn`，用于验证你自己的 sessions、API keys 或 identity provider。ordered auth walk 和 fail-closed guarantee 见 [Auth and route protection](./auth-and-route-protection)。

如果你在 Vercel 之外 self-deploy，不要把 `vercelOidc()` 作为唯一 production authenticator。请使用你自己的 route policy，例如 Basic auth、面向你的 identity provider 的 JWT/OIDC verification，或 custom verifier。

## 7. Deploy on Vercel

用 [Vercel CLI](https://vercel.com/docs/cli) 部署，或推送到 Git-connected project：

```bash
vercel deploy
```

部署后的 app 会服务与你本地一直调用的同一组稳定 health、session 和 stream routes。

## 8. Deploy without Vercel

eve 也可以作为普通 Node service 运行在你自己的 process manager、container platform 或 reverse proxy 后面：

```bash
eve build
PORT=3000 eve start --host 0.0.0.0
```

eve 会把标准 Nitro output 写到 `.output/` 下，而不是 Vercel Build Output。`eve start` 会服务该 built app，并遵守 `PORT` 或 `--port` flag。像对待任何其他 Node HTTP service 一样，在这个 process 外围放置 TLS、routing、autoscaling 和 log collection。

Self-deployed agents 应该把 Vercel-specific choices 显式化：

- 让 Workflow SDK 使用默认 local world，它会把 workflow state 存在 `.workflow-data` 下；或者配置你的 host，让该目录位于 persistent storage 上。
- 安装你的 provider 对应的 AI SDK package，然后在不想依赖 Gateway 时使用 direct provider model object 和 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`。
- 如果你仍想从 non-Vercel host 使用 Gateway routing，请使用 `AI_GATEWAY_API_KEY`。
- 用你的 host 能验证的 auth 替换 `vercelOidc()`。
- 使用 `defaultBackend()`、pin 一个 non-Vercel sandbox backend（例如 Docker 或 microsandbox），或使用你自己的 `SandboxBackend` adapter。
- 如果 agent 定义了 schedules，默认 `eve build && eve start` 路径会启动 Nitro 的 schedule runner，Vercel 则会自动把 schedules 连接到 Vercel Cron。如果你把 output 适配到 custom HTTP-only host 或 preset，请确认它也会运行 Nitro scheduled tasks，或从你自己的 scheduler 触发同样的工作。
- 将 Vercel Cron、Vercel Sandbox prewarm、Vercel Deployment Protection bypass 和 Agent Runs dashboard 视为 Vercel-only conveniences。

HTTP contract 不变：health、session creation、streaming、channels、tools 和 subagents 使用同样的 routes。任何能访问并认证到这些 routes 的 client 都可以和 agent 通信。

## 9. Verify the deployment

Smoke-test live routes。先检查 health：

```bash
curl https://<your-app>/eve/v1/health
```

然后执行一个真实 turn：

```bash
curl -X POST https://<your-app>/eve/v1/session \
  -H 'content-type: application/json' \
  -d '{"message":"Hello from production"}'
```

POST 会返回 JSON body，其中 `sessionId` 标识新 session。用它 attach 到该 session 的 stream：

```bash
curl https://<your-app>/eve/v1/session/<sessionId>/stream
```

或者用 dev TUI 交互式驱动 deployment，这很适合 preview 和 production smoke tests：

```bash
eve dev https://<your-app>
```

（如果 deployment 使用 preview protection，请先在本地设置 `VERCEL_AUTOMATION_BYPASS_SECRET`。）

## View runs in the dashboard

agent 部署后，platform 会自动检测 `eve` framework，并在 Vercel dashboard 中你项目的 **Observability** view 下展示 **Agent Runs** tab。你可以在那里浏览 sessions，并深入查看每段 conversation 的 trace。

> Agent Runs tab 目前是 gated 功能。你的 Vercel team 需要启用该功能后才会显示。如果你看不到它，请联系你的 Vercel contact 为 team 启用。

Agent Runs 独立于 [Observability](./instrumentation) 中配置的 OpenTelemetry exporters。后者仍然可用，并且当你希望 spans 进入 Braintrust、Datadog 或其他 third-party backend 时是推荐路径。

## eve 如何位于 host framework 后面

你可以单独部署 eve app，也可以把它挂载到拥有站点其余部分的 host web framework 中（marketing pages、dashboard、其他 API routes）。host 保留自己的 routing，并通过 framework integration 服务 eve routes。无论哪种方式，agent surface 和 HTTP contract 都相同。关于在 Next.js 中挂载 eve（`withEve`）以及其他支持的 frameworks，见 [Frontend](./frontend/nextjs)。

## Checklist

- [ ] `eve build` 成功，并在设置 `VERCEL` 时写入 `.vercel/output`。
- [ ] Provider keys 和 route-auth secrets 已设置在 deployment environment 中。
- [ ] sandbox backend 匹配环境（`vercel()` 或 `defaultBackend()`）。
- [ ] 在 Vercel 上，build-time prewarm 已复用或构建 templates，且没有失败。
- [ ] `placeholderAuth()` 已替换为你的真实 policy。
- [ ] `vercel deploy` 成功，或你的 self-hosted process 已用 `eve start` 启动。
- [ ] health、session 和 stream routes 会在 deployment URL 上响应。

## 接下来阅读

- [Auth and route protection](./auth-and-route-protection)：保护你部署的 routes
- [Observability](./instrumentation)：tracing、run tags 和常见 failures
- [Sandbox](../sandbox)：backends、lifecycle 和 credential brokering
