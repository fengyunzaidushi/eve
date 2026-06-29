---
title: "负责任使用"
description: "在将 eve 用于敏感、受监管或生产数据之前，应审查的 deployer 责任和 safeguards。"
---

作为 deployer，你有责任确保你的 agent 符合适用法律。

你有责任为自己的 use case 配置适当的 approval policies、tool restrictions、connection scopes、route/session authorization、sandbox controls、telemetry exports 以及其他 safeguards。

在将 eve 用于非公开、敏感、受监管或生产数据之前，请审查 agent 可以访问哪些 default tools、custom tools、MCP tools、shell/file/web tools、connected services、subagents、schedules 和 external actions。

对于敏感、不可逆、受监管、金融、医疗、就业、住房、法律、影响安全、影响用户或会产生外部副作用的 actions，请要求 human approval 或其他 safeguards。

除非你配置了更严格的 controls，否则 eve agents 可能会以宽松设置运行，包括在省略 approval 时无需 human approval 即可执行 tool，以及并非 deny-all 的 sandbox network egress。不要只依赖 model 行为来阻止敏感或不可逆 actions。
