---
title: "Dev TUI"
description: "在交互式 terminal UI 中本地驱动 eve agent。Chat、stream、approve tools、回答问题、调整显示，并指向 deployment。"
---

`eve dev` 会启动 local runtime，并进入交互式 terminal UI。你可以和 agent 对话、观看它 stream、批准它的 tool calls，并回答它反问的问题。

```bash
eve dev
```

启动时，TUI 会打印一行带 agent name 的 brand line，再加一个轮换 tip（仅 local sessions）。

```text
 eve weather-agent
 Use /channels to add more ways to reach your agent.
```

如果 agent discovery 报告了问题，两行之间会显示 error 和 warning 数量。Instructions、tools、skills 和 subagents 都可以通过 `eve info` 查看，`/help` 会列出所有 command。TUI 还会运行 startup check。缺少 model-provider setup 时，会显示需要注意的行（`⚠ 1 setup issue: model provider not linked · /model`），这样第一次 message 失败前就能看到修复入口；每个 command 的结果会挂在它下面的 `⎿` connector 上。

## 阅读 transcript

conversation 会直接 stream 到 terminal 的普通 scrollback 中，因此你保留原生 scrolling、copy and paste，以及退出后仍然存在的 transcript。scrollback 会包含你的 prompts、agent replies、reasoning、tool calls、nested subagents、connection-authorization prompts，以及捕获的任何 `stdout`、`stderr` 或 sandbox lifecycle lines。

每个 turn 都不使用 boxes 渲染。彩色 gutter glyph 标记说话方，tool calls 会折叠成一行 summary（`✓ get_weather  city="SF" → 73°F`），subagent 的工作会缩进到它的 `◆` header 下。输入就绪时，prompt 保持简洁，直到你开始输入。当某个 turn 或 setup action 占用 terminal 时，只显示它的 live status。

prompt 或 status 下方有一条持久行，显示 model、session token flow（`↑ 394.4K ↓ 4.3K`）、已链接的 Vercel project 和 team（`▲ my-agent (acme)`），以及当本 session 新增 channel 后仍需 `/deploy` 时的黄色 `/deploy pending` marker。Vercel segment 在目录链接前会保持隐藏。

Errors 会以紧凑形式渲染，并突出 docs links。agent 自己代码中逸出的 code bug 会在 error headline 下方以 dim stack trace 显示。Dev-server rebuilds 会压缩成一行 in-place 更新的 status row（`tui/setup-panel.ts changed · rebuilding…`，随后 `· rebuilt`）；只显示最新 rebuild，paths 会缩短到最后两个 components。

## Slash commands

每个 command 会回显为 invocation line，通过一个替代 input area 的 bordered panel 提问（一次一个问题，和 chat transcript 分开），最后以一行 `⎿` result 结束。Loading states 会停留在 ephemeral status line 上，而不是堆进 transcript。

| Command     | 作用                                                                                                                     |
| ----------- | ------------------------------------------------------------------------------------------------------------------------ |
| `/model`    | 打开会循环到 Done（或 Esc）的 configure menu。见 [Configure the model and provider](#configure-the-model-and-provider)。 |
| `/channels` | 显示 agent 的 channel list，并添加你选择的 channel。见 [Add a channel](#add-a-channel)。                                 |
| `/deploy`   | 将 agent 发布到 Vercel production；如果目录尚未 link，会先 link。                                                        |
| `/loglevel` | 切换 transcript 显示哪些 logs。见 [Control what logs show](#control-what-logs-show)。                                    |
| `/new`      | 开始一个 fresh session。                                                                                                 |
| `/exit`     | 退出 TUI。                                                                                                               |
| `/help`     | 列出所有 command。                                                                                                       |

`/model`、`/channels` 和 `/deploy` 会管理 project；只有在 `eve dev` 本地运行 server 时可用，连接到 `--url` remote server 时不可用。

### Configure the model and provider

裸 `/model` 会打开 configure menu。“Change model” 会运行 setup 使用的同一个 searchable model picker（Vercel AI Gateway catalog，并预选 runtime 正在服务的 model）。model change 会写入你的 authored agent source，command 只有在 eve 确认新 id 后才报告成功。`/model <provider/model-id>` 会直接应用一个 model，跳过 menu。

provider row 会打开 provider questions：使用哪个 model provider，以及如何连接。选择 Vercel AI Gateway 之外的选项时，会显示你自己 provider 的 wiring instructions 并停在那里，保留任何现有 setup 不动。对于 Vercel AI Gateway，你可以粘贴自己的 `AI_GATEWAY_API_KEY`（直接保存到 `.env.local`），也可以通过 project 连接。通过 project 连接时，会询问 Vercel team，打开该 team 的 existing-project list（再次选择会 re-link），然后拉取 project environment，让 AI Gateway credential 进入 `.env.local`。dev server 会自动 reload env files，无需重启。

provider row 会要求注意（黄色粗体 “Configure provider” 和 “Required to enable the agent”），直到检测到 link 或 gateway credential；之后会显示连接名称（例如 “AI Gateway (Linked to my-project in my-team)”）。每个 action 的最新结果会显示在 menu 下方（例如 “✓ Model changed to openai/gpt-5.5”）。当 turn 因 AI Gateway authentication 缺失或过期而失败时，error 会直接指向 `/model`。

### Add a channel

`/channels` 会显示 agent 的 channel list。已注册 channels 会渲染成带 checked 状态、可 focus 的 rows，并带有 “Already installed” hint。选择一个 channel 会添加它（包括 Slack Connect provisioning），然后安装 scaffold 添加的 dependencies，使 dev server 能立即加载新 channels。每次添加后，list 会重绘并把该 channel 标为 checked，直到 Done（或 Esc）离开该 flow。

## Keyboard shortcuts

prompt input 的行为类似 shell line editor。

| Key                                            | Action                                                                                                  |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `Enter`                                        | 发送 message。                                                                                          |
| `Ctrl+C`                                       | 中断正在运行的 turn，或在 prompt 处退出。                                                               |
| `↑` / `↓`                                      | 在本 session 已发送的 messages 中循环。                                                                 |
| `←` / `→`, `Home` / `End`, `Ctrl+A` / `Ctrl+E` | 移动 caret。                                                                                            |
| `Ctrl+U` / `Ctrl+K` / `Ctrl+W`                 | 删除整行、行剩余部分或前一个 word。                                                                     |
| `Ctrl+L`                                       | 循环 log display mode（`none → all → stderr → sandbox → none`），并在 status line 中短暂显示当前 mode。 |
| `Ctrl+R`                                       | Redraw screen。                                                                                         |

如果 turn 发生 terminal failure（server session 死亡或 connection drop），TUI 会启动 fresh session 并 inline 说明，这样你可以继续。Server-side context 会随旧 session 重置。

## Inline 回答 agent

当 agent 需要你提供内容时，TUI 会 inline 提问。

- Tool approvals 是 `y` 或 `n`。
- Option questions 允许你用 `↑` / `↓` 和 `Enter` 选择，也可以输入 freeform answer。
- 如果 tool 需要授权的 [connection](../connections)，URL 会直接显示在 transcript 中；完成 flow 后 turn 会继续。

## 控制显示哪些 logs

默认情况下，`eve dev` 显示 `stderr`，并缓存但隐藏 stdout 和 sandbox lines。捕获的 server `stdout` 和 `stderr` 会以 dim、indented log runs 渲染在 `│` rule 后面（同一来源的连续 lines 共用一个 label），sandbox lifecycle lines 使用自己的 label。

- `/loglevel <all|stderr|sandbox|none>` 会 retroactively 切换 transcript 显示内容。裸 `/loglevel` 会报告当前 mode。
- `--logs <all|stderr|sandbox|none>` 设置启动时的初始 mode（默认 `stderr`）。
- idle prompt 下的 `Ctrl+L` 会循环 `none → all → stderr → sandbox → none`。

## Display flags

Density flags 控制每个 section 渲染多少内容。它们接受 `full`、`collapsed`、`auto-collapsed` 或 `hidden`。

```bash
eve dev --tools full --assistant-response-stats tokens --context-size 200000
```

| Flag                                | Values                                             | Effect                                               |
| ----------------------------------- | -------------------------------------------------- | ---------------------------------------------------- |
| `--tools <mode>`                    | `full` / `collapsed` / `auto-collapsed` / `hidden` | tool calls 如何渲染（默认 `auto-collapsed`）。       |
| `--reasoning <mode>`                | `full` / `collapsed` / `auto-collapsed` / `hidden` | reasoning 如何渲染（默认 `full`）。                  |
| `--subagents <mode>`                | `full` / `collapsed` / `auto-collapsed` / `hidden` | subagent sections 如何渲染。                         |
| `--connection-auth <mode>`          | `full` / `collapsed` / `auto-collapsed` / `hidden` | connection authorization 如何渲染。                  |
| `--assistant-response-stats <mode>` | `tokens` / `tokensPerSecond`                       | assistant header 显示哪项 statistic。                |
| `--context-size <tokens>`           | token count                                        | Model context window size，显示为 usage percentage。 |
| `--logs <mode>`                     | `all` / `stderr` / `sandbox` / `none`              | 显示哪些 server 和 agent logs（默认 `stderr`）。     |

Connection flags：`--host` 和 `--port` 绑定 local server，`--no-ui` 以 headless 方式运行（当 stdout 不是 TTY 时也是 automatic fallback）。完整 flag list 见 [CLI](../reference/cli)。

## Remote: `eve dev <url>`

传入 URL 后，TUI 会连接到一个正在运行的 deployment，而不是启动 local server；这很适合 Vercel preview 或你的 production app。

```bash
eve dev https://<your-app>
```

裸 URL 是 `--url` 的简写。对 remote target，`--host`、`--port` 和 `--no-ui` 会被忽略。如果 deployment 位于 Vercel preview protection 后面，请先在本地设置 `VERCEL_AUTOMATION_BYPASS_SECRET`。smoke-test flow 见 [Deployment](./deployment)。

## 接下来阅读

- [Observability](./instrumentation)：OpenTelemetry、run tags 和常见 failures。
- [CLI](../reference/cli)：每个 command 和 flag。
