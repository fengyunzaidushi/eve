---
title: "Next.js"
description: "使用 withEve 将 eve agent 和 Next.js app 作为一个项目运行。"
---

`eve/next` 会把 Next.js frontend 和 eve agent 作为单个项目提供。用 `withEve()` 包装你的 config，即可从一个 dev server 和一个 Vercel deploy 运行二者。[`useEveAgent`](./overview) 会自行找到已挂载 routes，因此无需配置 CORS，也不需要同步 URL env vars。

## 前置条件

- 项目中已安装 `eve` package（`npm install eve@latest`）。
- 已有 eve agent directory。如果没有，请从 [Getting started](../../getting-started) 开始。
- 用于 mount agent 的 Next.js app。

## 包装 Next.js config

```ts title="next.config.ts"
import type { NextConfig } from "next";
import { withEve } from "eve/next";

const nextConfig: NextConfig = {};

export default withEve(nextConfig);
```

默认情况下，`withEve()` 会在 Next.js project root 内查找 `agent/` 文件夹。如果 agent 位于其他位置，请用 `eveRoot` 指向它：

```ts
export default withEve(nextConfig, {
  eveRoot: "../my-agent",
});
```

### `withEve` options

所有字段都是可选的。

| Option               | Type     | Default                | Purpose                                                                                                                        |
| -------------------- | -------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `eveRoot`            | `string` | Next.js app root       | eve app root 的路径；除非是 absolute，否则相对于 `process.cwd()`。当 agent 位于 Next.js project 外部时设置。                   |
| `eveBuildCommand`    | `string` | `"eve build"`          | generated eve Vercel service 的 build command。当 eve service 需要 project-specific prework，且不想改变 Next.js build 时使用。 |
| `servicePrefix`      | `string` | `"/_eve_internal/eve"` | eve service 的 private Vercel route namespace。手动设置时，必须匹配 Vercel Build Output config 中 eve service 的 mount。       |
| `devServerTimeoutMs` | `number` | `180000`               | 等待 eve development server 可用的最长时间。                                                                                   |

对于较慢的 cold starts，请增加 development timeout：

```ts
export default withEve(nextConfig, {
  devServerTimeoutMs: 300_000,
});
```

## 调用 hook

在 `next.config.ts` 中使用 `withEve()` 后，eve routes 是 same-origin 的，因此 client code 可以调用 [`useEveAgent`](./overview)，无需指定 host。Cookie-based auth（Auth.js 或任何 session cookie）不需要额外 wiring，因为浏览器已经会在每个 eve request 上发送这些 cookies。对于 non-cookie schemes，请自行附加 credentials：

```tsx
const agent = useEveAgent({
  headers: async () => ({
    authorization: `Bearer ${await getAccessToken()}`,
  }),
});
```

default eve channel 是 fail-closed 的。如果没有编写 `agent/channels/eve.ts`，eve 会注册 `eveChannel({ auth: [localDev(), vercelOidc()] })`：`localDev()` 在 localhost 上打开 routes，`vercelOidc()` 在 production 中允许 Vercel OIDC callers，其他所有请求都会得到 `401`。若要运行你 app 自己的 auth policy，请添加 `agent/channels/eve.ts`：

```ts title="agent/channels/eve.ts"
import { eveChannel } from "eve/channels/eve";
import { localDev, vercelOidc } from "eve/channels/auth";

export default eveChannel({ auth: [localDev(), vercelOidc()] });
```

对于 public demo，可使用 `none()`（也来自 `eve/channels/auth`）跳过 authentication。见 [Channels](../../channels/overview) 和 [Auth & route protection](../auth-and-route-protection)。

## Dev vs deploy topology

- **Local dev.** `npm run dev` 会在 `next dev` 旁启动 eve dev server，并把 eve routes rewrite 到它。浏览器始终只与 Next.js origin 通信。
- **Vercel.** web app 和 eve runtime 会作为单个项目部署。web app 保持 public；eve runtime 位于同一 site origin 上、处在它后面。当 agent 需要自己的 build step 时，请设置 `eveBuildCommand`：

  ```ts
  export default withEve(nextConfig, {
    eveBuildCommand: "npm run build:eve",
  });
  ```

- **Local production build.** `next build && next start` 会在稳定本地 port（`4274`）上从已构建的 `.output/server/index.mjs` 提供 eve runtime，并把 eve routes proxy 到它。请先运行 `eve build`，确保 output 存在。用 `EVE_NEXT_PRODUCTION_PORT` 改变 port：

  ```bash
  EVE_NEXT_PRODUCTION_PORT=5000 npm run build && npm start
  ```

- **Non-Vercel hosts.** 当 eve service 位于 separate origin 时，用 `EVE_NEXT_PRODUCTION_ORIGIN` 告诉 Next.js 在哪里找到它：

  ```bash
  EVE_NEXT_PRODUCTION_ORIGIN=https://agent.example.com npm run build
  ```

## 接下来阅读

- [Frontend overview](./overview)：`useEveAgent` API
- [Auth & route protection](../auth-and-route-protection)
- [Deployment](../deployment)
