---
title: "运行 Evals"
description: "eve eval CLI：flags、filters、exit codes、artifacts，以及如何把 evals 接入 CI。"
---

`eve eval` 会发现 `evals/` 下的每个 `.eval.ts` 文件，启动 local dev server（或指向 remote server），并发运行 evals，并打印 per-eval summary。

```bash
eve eval                       # run all discovered evals locally
eve eval weather smoke         # run selected evals (an id, or a directory prefix)
eve eval --url https://<app>   # target a remote app instead of a local host
eve eval --tag fast            # only evals carrying a tag
eve eval --strict              # soft below-threshold assertions also fail the exit code
eve eval --timeout 60000       # per-eval timeout in milliseconds
eve eval --max-concurrency 4   # cap concurrent eval executions (default 8)
eve eval --junit .eve/junit.xml  # write JUnit XML
eve eval --list                # print discovered evals without running
eve eval --verbose             # stream per-eval t.log lines to stdout
eve eval --json                # machine-readable output
eve eval --skip-report         # skip config and eval-defined reporters (e.g. Braintrust)
```

位置参数 ids 会精确匹配或按 directory prefix 匹配：`eve eval weather` 会运行 `evals/weather.eval.ts`、`evals/weather/` 下的每个 eval，以及 array-exported `weather.eval.ts` 的每个 entry。

## Exit codes

| Code | 含义                                                                    |
| ---- | ----------------------------------------------------------------------- |
| `0`  | 每个 eval 都通过 gates（以及 `--strict` 下的 soft thresholds）          |
| `1`  | 任一 eval 失败（failed gate、execution error 或 strict threshold miss） |
| `2`  | Configuration error                                                     |

## Artifacts

每次 run 都会在 `.eve/evals/<timestamp>/` 下落下 artifacts：run `summary.json`、`results.jsonl` index，以及 `evals/` 下的 per-eval assertion results、verdicts、captured event streams 和 `t.log` lines。console output 有意保持简洁；当 eval 失败时，artifact 中有完整细节。

## CI

可靠的 CI invocation 应严格且 machine-reportable：

```bash
eve eval --strict --junit .eve/junit.xml
```

- `--strict` 会把 soft threshold misses 转成 failures，因此 score regressions 会阻塞 merge。
- `--junit` 会向 CI provider 提供 per-eval annotations；请把 `.eve/evals/` 目录作为 failure artifact 上传，以便查看完整 event streams。

Evals 会针对 live model 运行，因此 CI environment 必须提供 model-provider credentials。针对 deployed app 时，请添加 `--url`：

```bash
eve eval --strict --url "$DEPLOY_URL" --junit .eve/junit.xml
```

## 接下来阅读

- [Targets](./targets)：`--url` 交互的对象
- [Reporters](./reporters)：Braintrust 和 JUnit output
- [CLI reference](../reference/cli)：其余 `eve` CLI
