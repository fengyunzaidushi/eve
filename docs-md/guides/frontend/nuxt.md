---
title: "Nuxt"
description: "使用 eve/nuxt module 将 eve agent 和 Nuxt app 作为一个项目运行。"
---

`eve/nuxt` module 会把 Nuxt frontend 和 eve agent 作为单个项目运行，共用一个 dev server 和一个 Vercel deploy。auto-imported [`useEveAgent`](./use-eve-agent-vue) composable 会自行找到已挂载 routes，因此无需配置 CORS，也不需要同步 URL env vars。

## 前置条件

- 项目中已安装 `eve` package（`npm install eve@latest`）。
- 已有 eve agent directory。如果没有，请从 [Getting started](../../getting-started) 开始。
- 用于 mount agent 的 Nuxt app。

## 注册 module

```ts title="nuxt.config.ts"
export default defineNuxtConfig({
  modules: ["eve/nuxt"],
});
```

module 会在 Nuxt project root 中查找 `agent/` 文件夹。当 agent 位于其他位置时，请传入 `eveRoot`：

```ts
export default defineNuxtConfig({
  modules: ["eve/nuxt"],
  eve: {
    eveRoot: "../my-agent",
  },
});
```

`eve` key 只接受两个 options：`eveRoot` 和 `eveBuildCommand`。

## 调用 composable

`useEveAgent`（`eve/vue`）会自动导入，因此 component 调用它时无需显式 import，也无需指定 host：

```vue
<script setup lang="ts">
const { status, send } = useEveAgent();

const isBusy = computed(() => status.value === "submitted" || status.value === "streaming");

const message = ref("");

async function handleSubmit() {
  const text = message.value.trim();
  if (!text || isBusy.value) return;
  message.value = "";
  await send({ message: text });
}
</script>

<template>
  <form @submit.prevent="handleSubmit">
    <input v-model="message" :disabled="isBusy" />
    <button type="submit" :disabled="isBusy">Send</button>
  </form>
</template>
```

default eve channel 是 fail-closed 的。如果没有编写 `agent/channels/eve.ts`，eve 会注册 `eveChannel({ auth: [localDev(), vercelOidc()] })`：`localDev()` 在 localhost 上打开 routes，`vercelOidc()` 在 production 中允许 Vercel OIDC callers，其他所有请求都会得到 `401`。若要运行你自己的 auth policy，请添加 `agent/channels/eve.ts`：

```ts title="agent/channels/eve.ts"
import { eveChannel } from "eve/channels/eve";
import { localDev, vercelOidc } from "eve/channels/auth";

export default eveChannel({ auth: [localDev(), vercelOidc()] });
```

对于 public demo，可使用 `none()`（也来自 `eve/channels/auth`）跳过 authentication。见 [Channels](../../channels/overview) 和 [Auth & route protection](../auth-and-route-protection)。

## Dev vs deploy topology

- **Local dev.** `npm run dev` 会在 `nuxt dev` 旁启动 eve dev server，并通过它 proxy eve routes。对浏览器来说，所有内容都来自 Nuxt origin。
- **Vercel.** 单个 Vercel project 同时承载 Nuxt app 和 eve runtime。web app 保持 public；runtime 位于同一 origin 上、处在它后面。当 agent 需要自己的 build step 时，请设置 `eveBuildCommand`：

  ```ts
  export default defineNuxtConfig({
    modules: ["eve/nuxt"],
    eve: {
      eveBuildCommand: "npm run build:eve",
    },
  });
  ```

- **Non-Vercel hosts.** 使用 `EVE_NUXT_PRODUCTION_ORIGIN` 将 Nuxt 指向 separate eve origin。若要覆盖 local port（默认 `4274`），请使用 `EVE_NUXT_PRODUCTION_PORT`：

  ```bash
  EVE_NUXT_PRODUCTION_ORIGIN=https://agent.example.com npm run build
  EVE_NUXT_PRODUCTION_PORT=5000 npm run build && npm run preview
  ```

## 接下来阅读

- [`useEveAgent` (Vue)](./use-eve-agent-vue)：composable API
- [Auth & route protection](../auth-and-route-protection)
- [Deployment](../deployment)
