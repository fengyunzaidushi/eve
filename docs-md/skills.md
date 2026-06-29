---
title: "Skills"
description: "编写 model 可通过 load_skill 拉入 context 的 load-on-demand procedures。"
---

skill 是遵循 `SKILL.md` 约定、可由 model 加载的 procedure。它是一个 markdown 文档，也可以是一个带有 supporting files 的 packaged directory；model 会按需把它拉入 context，而不是每个 turn 都携带它。eve 会向 model 暴露每个 skill 的 description，只有当某个 turn 需要时，model 才会加载完整正文。这就是 progressive disclosure，与更广泛的 Agent Skills 标准采用同一模型，因此按该标准编写的 skill 可以原样迁移过来。

## 加载方式

eve 会扫描 `agent/skills/` 下的文件，并把每个文件的 description 连同 framework-owned `load_skill` tool 一起暴露给 model。当请求匹配某个 skill 的 description（或你直接点名该 skill）时，model 会调用 `load_skill`，eve 会把该 skill 的 markdown 追加到当前 active turn 的 context 中。

description 是 routing hint，而不是 label。请把它写成应该触发激活的任务：

```md
Use when the user needs a release checklist or changelog workflow.
```

加载 skill 只会添加 instructions，不会添加新的 execution surface。无论 skill 是否加载，tools 都保持可见。如果需要类型化 runtime 行为，请改用 [tool](./tools)。

## Markdown vs `defineSkill`

最小的 skill 是一个扁平 markdown 文件。内容就是 procedure，名称来自路径。

```md title="agent/skills/forecast.md"
Use the weather tool before answering forecast or temperature questions.
```

扁平 markdown skill 可以省略 `description` frontmatter。省略时，eve 会暴露正文中第一行非空、非 code fence 的内容，并去掉开头的 `#`、`>`、`*` 或 `-` 标记。如果正文没有这样的行，eve 会回退到字面量 `Instructions for the <name> skill.`。这是一个较弱的 routing hint，因此当你希望 model 按 intent 路由时，请添加 `description`。

packaged skill 是一个目录，包含 `SKILL.md` 以及 `references/`、`assets/`、`scripts/` 等 sibling files。packaged `SKILL.md` 必须带有 `description` frontmatter；它没有可回退的 filename slug。

```md title="agent/skills/research/SKILL.md"
---
description: Research unfamiliar topics before answering with confidence.
---

When the task is novel or ambiguous, gather evidence first, then answer with the
key facts and the remaining uncertainty.
```

当 markdown 无法表达你的需求（typed values、generated content 或 inline sibling files）时，可以使用来自 `eve/skills` 的 `defineSkill` 在 TypeScript 中编写 skill：

```ts title="agent/skills/research.ts"
import { defineSkill } from "eve/skills";

export default defineSkill({
  description: "Research unfamiliar topics before answering with confidence.",
  markdown:
    "When the task is novel or ambiguous, gather evidence first, then answer with the key facts and the remaining uncertainty.",
  files: {
    "references/checklist.md": "# Checklist\n\n- Find primary sources.\n",
  },
});
```

eve 会根据 `markdown` 生成 `SKILL.md`，每个 `files` 条目会成为 package-relative sibling。先从 plain markdown 开始，只有在遇到限制时再迁移到 `defineSkill`。

## Skills 按 agent 作用域隔离

Skills 的作用域限定在声明它们的 agent 内。[subagent](./subagents) 的 `skills/` 对 root agent 不可见，反过来也一样。没有 shared-skill 机制，因此请把共享的 executable helpers 放在 `lib/` 中。

## 在 runtime 读取 skill 文件

加载 skill 会把它的 `SKILL.md` 添加到 context。若要在 tool 或 hook 内访问 packaged skill 的 sibling files（references、assets、scripts），请使用 `ctx.getSkill(id)`：

```ts
const research = ctx.getSkill("research");
const checklist = await research.file("references/checklist.md").text();
```

该 handle 会暴露 skill 的 `name` 和 `file(relativePath)`；文件内容会从 active sandbox 中惰性读取。

## Dynamic skills

如果要按 principal、tenant 或 channel 提供不同 skill（例如调用者自己的 team playbook），请把 `defineSkill` 包装在基于 `ctx.session.auth` 的 `defineDynamic` resolver 中。见 [Dynamic capabilities](./guides/dynamic-capabilities)。

## 接下来阅读

- [Connections](./connections)：添加来自外部 MCP 和 OpenAPI servers 的 tools
- [Dynamic capabilities](./guides/dynamic-capabilities)：使用 `defineDynamic` 按 caller 解析 skills
- [Context control](./concepts/context-control)：skills 如何融入完整 context model
