---
title: "SvelteKit"
description: "使用 eveSvelteKit Vite plugin 将 eve agent 和 SvelteKit app 作为一个项目运行。"
---

`eve/sveltekit` 会把 SvelteKit frontend 和 eve agent 作为一个项目运行，而不是两个 services。`eveSvelteKit()` Vite plugin 会把二者放在一个 dev server 和一个 Vercel deploy 上，[`useEveAgent`](./use-eve-agent-svelte) 会自行找到已挂载 routes。无需配置 CORS，也不需要同步 URL env vars。

## 前置条件

- 项目中已安装 `eve` package（`npm install eve@latest`）。
- 已有 eve agent directory。如果没有，请从 [Getting started](../../getting-started) 开始。
- 用于 mount agent 的 SvelteKit app。

## 注册 Vite plugin

在 `sveltekit()` 前添加 `eveSvelteKit()`：

```ts title="vite.config.ts"
import { sveltekit } from "@sveltejs/kit/vite";
import { eveSvelteKit } from "eve/sveltekit";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [eveSvelteKit(), sveltekit()],
});
```

plugin 会在 SvelteKit project root 中查找 `agent/` 文件夹。当 agent 位于其他位置时，请传入 `eveRoot`：

```ts
export default defineConfig({
  plugins: [
    eveSvelteKit({
      eveRoot: "../my-agent",
    }),
    sveltekit(),
  ],
});
```

plugin 只接受两个 options：`eveRoot` 和 `eveBuildCommand`。

## 调用 binding

在 `vite.config.ts` 中添加 plugin 后，components 可以从 `eve/svelte` 调用 [`useEveAgent`](./use-eve-agent-svelte)，且不需要传入 host：

```svelte
<script lang="ts">
  import { useEveAgent } from "eve/svelte";

  const agent = useEveAgent();
  let message = $state("");
  let isBusy = $derived(agent.status === "submitted" || agent.status === "streaming");

  async function handleSubmit() {
    const text = message.trim();
    if (!text || isBusy) return;
    message = "";
    await agent.send({ message: text });
  }
</script>

<form onsubmit={(event) => {
  event.preventDefault();
  void handleSubmit();
}}>
  <input bind:value={message} disabled={isBusy} />
  <button type="submit" disabled={isBusy}>Send</button>
</form>
```

default eve channel 是 fail-closed 的。如果没有编写 `agent/channels/eve.ts`，eve 会注册 `eveChannel({ auth: [localDev(), vercelOidc()] })`：`localDev()` 在 localhost 上打开 routes，`vercelOidc()` 在 production 中允许 Vercel OIDC callers，其他所有请求都会得到 `401`。若要设置你自己的 auth policy，请添加 `agent/channels/eve.ts`：

```ts title="agent/channels/eve.ts"
import { eveChannel } from "eve/channels/eve";
import { localDev, vercelOidc } from "eve/channels/auth";

export default eveChannel({ auth: [localDev(), vercelOidc()] });
```

对于 public demo，可使用 `none()`（也来自 `eve/channels/auth`）跳过 authentication。见 [Channels](../../channels/overview) 和 [Auth & route protection](../auth-and-route-protection)。

## Dev vs deploy topology

- **Local dev.** `npm run dev` 会在 SvelteKit 旁启动 eve dev server，并把 eve routes proxy 到它，因此浏览器始终只访问 SvelteKit origin。`npm run build && npm run preview` 的行为相同：preview server 会获得自己的 eve route proxy，并复用共享 eve server 或启动一个。
- **Vercel.** SvelteKit app 和 eve runtime 会作为单个项目部署。web app 是 public；eve runtime 位于同一 origin 上、处在它后面。使用 `eveBuildCommand` 进行 project-specific agent build：

  ```ts
  export default defineConfig({
    plugins: [
      eveSvelteKit({
        eveBuildCommand: "npm run build:eve",
      }),
      sveltekit(),
    ],
  });
  ```

- **Non-Vercel hosts.** 当 eve service 运行在 separate origin 上时，请直接向 `useEveAgent` 传入 `host`：

  ```ts
  const agent = useEveAgent({
    host: "https://agent.example.com",
  });
  ```

## 接下来阅读

- [`useEveAgent` (Svelte)](./use-eve-agent-svelte)：binding API
- [Auth & route protection](../auth-and-route-protection)
- [Deployment](../deployment)
