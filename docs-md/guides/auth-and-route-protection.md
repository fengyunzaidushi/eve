---
title: "Auth & Route Protection"
description: "用有序 auth walk、verifier helpers 和通过 Vercel Connect 的 connection OAuth 保护 agent 的 HTTP routes。"
---

eve 有两个独立的 auth systems：

- **Route auth**（inbound）决定谁能访问 agent 的 HTTP routes。它运行在 channel layer，在任何 model work 运行前 gate request。
- **Tool and connection auth**（outbound）是 agent 登录其调用的外部服务的方式，例如 OAuth MCP server。它发生得更晚：当 tool 或 connection 真正向外请求时才运行。

先从 route auth 开始。

## Route auth

route-auth policy 位于 HTTP channel factory（`agent/channels/eve.ts`）上，并保护三条 routes：

- `POST /eve/v1/session`
- `POST /eve/v1/session/:sessionId`
- `GET /eve/v1/session/:sessionId/stream`

这些 routes 受 channel 的 auth policy 保护。eve 默认 fail closed：production browser traffic 会被拒绝，除非你配置了接受它的 authenticator；anonymous access 需要显式 `none()`。

`GET /eve/v1/health` 始终公开，并完全跳过 walk，因此 load balancers 和 uptime monitors 可以不带 credentials 探测它。

```ts title="agent/channels/eve.ts"
import { eveChannel } from "eve/channels/eve";
import { localDev, vercelOidc } from "eve/channels/auth";

export default eveChannel({
  auth: [localDev(), vercelOidc()],
});
```

`vercelOidc()` 是 Vercel-hosted agents 和 Vercel-to-Vercel callers 的便利工具，不是必需条件。如果你的 app 已经有 users、sessions、API keys 或 identity provider，请把那个 authenticator 放进 `auth` walk。Custom `AuthFn` entries 是 first-class，可以完全替代 Vercel OIDC。

## 有序 auth walk

`auth` 接受单个 `AuthFn` 或一个数组，eve 会按顺序 walk。每个 entry 有三种可能结果：

- 返回 `SessionAuthContext`：接受 request 并停止 walk
- 返回 `null` / `undefined`：跳到下一个 entry
- **throw**：用特定 status 拒绝

如果每个 entry 都跳过，request 会得到 `401`。空数组 `auth: []` 会拒绝所有请求。

```ts
import { type AuthFn, localDev, vercelOidc } from "eve/channels/auth";
import { eveChannel } from "eve/channels/eve";
import { getSession } from "@/lib/auth";

function appSession(): AuthFn<Request> {
  return async (request) => {
    const session = await getSession(request);
    if (!session) return null; // skip; fall through to the next entry
    return {
      attributes: { providerId: session.providerId },
      authenticator: "app",
      principalId: session.userId,
      principalType: "user",
    };
  };
}

export default eveChannel({
  auth: [appSession(), localDev(), vercelOidc()],
});
```

把你自己的 providers 放在 catch-all helpers 前面。任何不识别 caller 的 entry 都返回 `null`，walk 会继续。在 non-Vercel hosts 上，除非你明确想接受 Vercel-issued tokens，否则省略 `vercelOidc()`。

如果要用精确 status 拒绝而不是跳过，请 throw：

```ts
import { ForbiddenError, UnauthenticatedError } from "eve/channels/auth";

throw new UnauthenticatedError({
  code: "authentication_required",
  message: "Sign in to continue.",
}); // 401
throw new ForbiddenError({ message: "Not allowed on this workspace." }); // 403
```

其他 thrown error 会走普通 channel failure path。构建基于 `defineChannel` 的 custom channel 时，从 `eve/channels/auth` 调用 `routeAuth(request, auth)`，即可复用相同 walk semantics。

## Verifier helpers

`eve/channels/auth` 提供这些 channel-auth helpers：

| Helper           | 适用场景                                                     |
| ---------------- | ------------------------------------------------------------ |
| `localDev()`     | Local development。接受发往 loopback hostname 的 requests。  |
| `vercelOidc()`   | 常见 Vercel deployment path。验证 Vercel OIDC bearer JWT。   |
| `none()`         | 你明确想接受 anonymous traffic（作为最后一个 entry）。       |
| `httpBasic(...)` | 通过共享 username/password 提供 operator 或 service access。 |
| `jwtHmac(...)`   | 你控制 shared-secret JWT signer。                            |
| `jwtEcdsa(...)`  | 你验证另一个系统签发的 asymmetric JWTs。                     |
| `oidc(...)`      | 你希望 eve 验证任意 issuer 签发的 OIDC tokens。              |

如果 agent 会处理非公开、敏感、受监管或生产数据，除非你已经实现其他 access controls，否则请谨慎使用。

### `localDev()`

认证一个合成的 `local-dev` principal，但只在 inbound request 发往 loopback hostname（`localhost`、`*.localhost`、`127.0.0.0/8` 或 `::1`）时生效。检查依据是 request URL 的 hostname，而不是裸 `process.env.VERCEL` flag，这是有意的：Vercel 之外的 deployment 会让 `VERCEL` 未设置，所以只嗅探那个 flag 会放行所有 public traffic。有一个 process-level exception：由 `VERCEL=1` 和 `VERCEL_ENV=development` 同时检测出的 `vercel dev`，即使通过 non-loopback host 服务，也会打开 local dev server。其他所有 non-loopback request 都返回 `null` 并 fall through。

`localDev()` 信任 advertised hostname，因此如果 attacker 能注入 `Host` header（origin 前没有 normalizing proxy），就可以 spoof 它。始终叠加真实 authenticator；不要只依赖 `localDev()` 运行。

### `vercelOidc()`

根据 [Vercel OIDC issuer](https://vercel.com/docs/oidc) 验证 bearer JWT。为当前 `VERCEL_PROJECT_ID` 签发的 tokens 始终会被接受，这也是 internal subagent 和 runtime callers 可零配置认证的原因。带 `external_sub` 的 tokens 会作为 user callers 认证，但只有当它们的 `project_id` 匹配 `VERCEL_PROJECT_ID` 且 environment 匹配 `VERCEL_TARGET_ENV` / `VERCEL_ENV` 时才接受。在这种情况下，`external_sub` 会成为 session subject，profile claims（`name`、`picture`、`email`）会出现在 `ctx.session.auth.current.attributes` 中。如果要准入其他 Vercel projects 签发的 tokens，请传入 `subjects: [...]`（AWS IAM-style `*` wildcards）。

Auth fail closed：routes 默认拒绝 unauthenticated traffic，OIDC user branch 会根据 `VERCEL_PROJECT_ID` 和 deployment environment 验证 `external_sub`，任一未设置时返回 `false`。external-subject token 不能在未 pin project 的 deployment 上认证。

#### `subjects` patterns 和 `vercelSubject(...)`

每个 `subjects` entry 都会与 token 的 `sub` claim 匹配；Vercel 将它塑造成 `owner:<team>:project:<name>:environment:<env>`。手写这个字符串容易出错：typo 会静默拒绝所有 callers，过宽的 `*` wildcard 又会静默放入无关 callers。请改用 `vercelSubject(...)` 构建 pattern。它会在 construction time 拒绝 malformed input，并且当你省略 `environment` 时默认使用 `"production"`，因此未指定 environment 不会静默接受 preview 或 development tokens：

```ts
import { vercelOidc, vercelSubject } from "eve/channels/auth";

vercelOidc({
  subjects: [
    vercelSubject({ teamSlug: "partner", projectName: "data" }), // environment defaults to "production"
    vercelSubject({ teamSlug: "acme", projectName: "agent", environment: "*" }),
  ],
});
```

`teamSlug` 和 `projectName` 是 Vercel 嵌入 `sub` 的 human-readable slugs（不是稳定的 `team_…` / `prj_…` IDs），所以不能包含 `:` 或 `*`。`environment` 是 `"production" | "preview" | "development" | "*"`。只有当你确实想用 wildcard 跨 teams 匹配时，才手写 subject string。

### Custom verifiers

当内置 helpers 都不合适时，请编写自己的 `AuthFn`（见上面的数组示例），或直接调用 low-level verifiers。每个 verifier 都是匹配 strategy helper 背后的 pure function，返回 `{ ok: true, sessionAuth }` 或 `{ ok: false }`：

| Verifier                               | Behind         | Input                            |
| -------------------------------------- | -------------- | -------------------------------- |
| `verifyHttpBasic(header, credentials)` | `httpBasic()`  | raw `Authorization` header value |
| `verifyJwtHmac(token, config)`         | `jwtHmac()`    | bearer token (HMAC-signed JWT)   |
| `verifyJwtEcdsa(token, config)`        | `jwtEcdsa()`   | bearer token (ECDSA-signed JWT)  |
| `verifyOidc(token, config)`            | `oidc()`       | bearer token (OIDC, any issuer)  |
| `verifyVercelOidc(token, opts)`        | `vercelOidc()` | bearer token (Vercel OIDC)       |

把 token 交给 JWT/OIDC verifiers 之前，先用 `extractBearerToken(request.headers.get("authorization"))` 提取它。configs（`VerifyJwtHmacConfig`、`VerifyJwtEcdsaConfig`、`VerifyOidcConfig`）接受 `issuer`、`audiences`、signing material（`secret` / `publicKey` / `discoveryUrl`），以及可选 `subjects` / `claims` matchers。

```ts
import { extractBearerToken, verifyJwtHmac, type AuthFn } from "eve/channels/auth";

function hmacAuth(): AuthFn<Request> {
  return async (request) => {
    const token = extractBearerToken(request.headers.get("authorization"));
    const result = await verifyJwtHmac(token, {
      algorithm: "HS256",
      issuer: "https://auth.example.com",
      audiences: ["agent"],
      secret: process.env.JWT_SECRET!,
    });
    return result.ok ? result.sessionAuth : null;
  };
}
```

### custom `defineChannel` routes 中的 failure responses

如果 `defineChannel` route handler 自行执行 checks，而不是使用 `routeAuth`，它仍然可以用 `createUnauthorizedResponse(...)` 发出 framework-shaped failure。你会得到一个 `Response`，其中包含 `cache-control: no-store`、`{ ok: false, code, error }` JSON body，以及每个 challenge 对应的一个 `www-authenticate` header：

```ts title="agent/channels/intake.ts"
import { defineChannel, POST } from "eve/channels";
import { createUnauthorizedResponse } from "eve/channels/auth";

export default defineChannel({
  routes: [
    POST("/message", async (req, { send }) => {
      if (!isAllowed(req)) {
        return createUnauthorizedResponse({
          status: 403, // defaults to 401; code defaults to "forbidden" / "unauthorized"
          message: "Not allowed on this workspace.",
          challenges: [{ scheme: "Bearer" }],
        });
      }
      // authenticated: handle the request
    }),
  ],
});
```

`UnauthenticatedError` 和 `ForbiddenError` 会包装这个 builder（status `401` / `403`）。从 `routeAuth` walk 的 `AuthFn` 中 throw 它们。只有当你从 hand-rolled route 返回 `Response` 时，才直接调用 `createUnauthorizedResponse`。

## Network policy

`eve/channels/auth` 导出 `createIpAllowList(...)` 和 `isIpAllowed(...)`，用于在任何 model work 开始前切断 requests。未通过 network policy 的 request 会在 auth 和 runtime execution 之前被 drop。

## 生产前替换 `placeholderAuth`

`eve init` 会用 `placeholderAuth()` guardrail scaffold `agent/channels/eve.ts`：

```ts
import { eveChannel } from "eve/channels/eve";
import { localDev, placeholderAuth, vercelOidc } from "eve/channels/auth";

export default eveChannel({
  auth: [localDev(), vercelOidc(), placeholderAuth()],
});
```

在 production 中，`placeholderAuth()` 会返回结构化 `401`，让生成的 web chat app 可以提示“auth 还没有配置”，而不是抛出 internal error。请在 browser caller 提交 production request 前替换它：换成你的 app 的 `AuthFn` 或某个内置 helper。完全删除 authored channel file 后，eve 会回退到 framework default `[localDev(), vercelOidc()]`，它也会拒绝 production browser traffic。

最终 policy 不一定要保留 `vercelOidc()`。对于 self-hosted app、嵌入 app 的 frontend，或任何使用 non-Vercel identity system 的 deployment，请使用 `httpBasic()`、`jwtHmac()`、`jwtEcdsa()`、generic `oidc()`，或 custom `AuthFn`，把你已验证的 user/session/API key 映射到 `SessionAuthContext`。

将 secret values（`ROUTE_AUTH_BASIC_PASSWORD`、signing keys）保存在 environment variables 中。Route-auth secrets 永远不会进入 compiled artifacts。runtime 会在 boot 时从 authored channel definition 中重新 materialize 它们。

## 到达 `ctx.session.auth` 的内容

在 runtime code 中，`ctx.session.auth` 会把 channel route auth（上面的 walk）的结果作为 caller snapshot 向前携带：

- `auth.current`：active inbound turn 上的 caller。
- `auth.initiator`：启动 durable session 的 caller。
- follow-up message 会更新 `auth.current`，但不会改变 `auth.initiator`。当另一个 caller 在同一 session 上 follow up 时，`auth.current` 会跟踪该 turn 的新 caller，而 `auth.initiator` 保持为最初启动它的人。
- 只有在 internal runtime paths（例如 subagents）没有经过 authored route 时，二者才都为 `null`。HTTP traffic 始终会填充 `auth.current`，因为 walk 要么接受并给出 `SessionAuthContext`，要么返回 `401`。

使用 `auth.current`（或 `auth.initiator`）上的 principal 来 scope tools、按 principal 解析 [dynamic capabilities](./dynamic-capabilities)，或执行 tenant boundaries。route auth 之上没有第二层 per-session ownership ACL。访问权在 HTTP boundary 决定，durable session 会把 caller snapshot 带入你的 runtime code。

Route auth 不会强制执行 session ownership。如果多个 users 或 tenants 能访问同一 route，你必须实现应用所需的 per-user、per-tenant 或 per-session authorization。

## Tool and connection auth

Tool and connection auth 是 agent 访问需要交互式 sign-in 的外部服务的方式，例如 OAuth MCP server。connection 和单个 tool 都可以声明 `auth` strategy；eve 会驱动 sign-in，按 step 缓存 token，并在 caller 授权后重新运行 call。

### 在 connection 上

把来自 `@vercel/connect/eve` 的 `connect()` 附加到 connection：

```ts title="agent/connections/linear.ts"
import { connect } from "@vercel/connect/eve";
import { defineMcpClientConnection } from "eve/connections";
import { once } from "eve/tools/approval";

export default defineMcpClientConnection({
  url: "https://mcp.linear.app/mcp",
  description: "Linear: project management, issue tracking, and team workflows.",
  auth: connect("oauth/linear"),
  approval: once(),
});
```

第一次需要该 connection 的 call 会启动 OAuth sign-in，并以 authorization challenge 的形式呈现（caller 访问的 URL）。[Vercel Connect](https://vercel.com/docs/connect) 会代理该 flow 并持有 credentials；这些 credentials 会按 workflow step 解析并缓存，永远不会序列化进 history，也不会展示给 model。对于非交互式 connections，请传入 static token 来代替 `connect()`。[Connections](../connections) 覆盖两种形状。

### 在单个 tool 上

当某个 tool 调用 OAuth 后面的服务时，可以声明自己的 `auth`，跳过单独 connection。`auth` 接受同样形状：用于 Vercel Connect-backed OAuth 的 `connect("...")`、custom interactive definition，或用于 static credentials 的普通 `{ getToken }`。

```ts title="agent/tools/list_okta_groups.ts"
import { defineTool } from "eve/tools";
import { connect } from "@vercel/connect/eve";
import { z } from "zod";

export default defineTool({
  description: "List the caller's Okta groups.",
  inputSchema: z.object({}),
  auth: connect("okta"),
  async execute(_input, ctx) {
    const { token } = await ctx.getToken();
    const res = await fetch("https://api.okta-proxy.internal/groups", {
      headers: { authorization: `Bearer ${token}` },
    });
    return res.json();
  },
});
```

声明 `auth` 会给 tool 的 `ctx` 增加两个 accessors：

- `ctx.getToken()` 为声明的 strategy 解析 bearer，优先检查 per-step token cache。使用 interactive strategy 时，cache miss 会把 turn 暂停在 framework-owned callback URL 上，展示 “Sign in” affordance，并在 OAuth callback 完成后重新运行 tool。
- `ctx.requireAuth()` 会 throw `ConnectionAuthorizationRequiredError`，在任何 token 解析前要求授权该 tool。runtime 会把它转成同样的 consent prompt。

在 `execute` 的任何位置 throw `ConnectionAuthorizationRequiredError`（直接 throw、通过 `requireAuth()`，或由 `getToken()` 隐式触发）都会按 tool name 触发 consent flow。在未声明 `auth` 的 tool 上调用任一 accessor 都会 throw。

默认情况下，sign-in affordance 会把 tool 的 path-derived name 转成 title case，因此名为 `sfdc_lookup.ts` 的 tool file 会渲染成 “Sign in with Sfdc_lookup”。在 `auth` definition 上设置 `displayName` 可以控制用户看到的内容，例如 `auth: { ...connect("sfdc"), displayName: "Salesforce" }`。它只影响 presentation。tool name 仍然用于 authorization scope、token cache 和 callback URL，并且 definition-level `displayName` 优先于 strategy 写入 challenge 的 displayName。

## 接下来阅读

- [Security model](../concepts/security-model)：trust boundaries 和 pre-production checklist
- [Connections](../connections)：connection auth shapes（`connect()` vs static token）
- [Deployment](./deployment)：route-auth secrets 在 production 中的位置
