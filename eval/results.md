# RepoPilot Evaluation Report

Questions: **104**
Retrieval Recall@5: **0.792**
Retrieval Recall@10: **0.819**
Citation correctness: **0.512**
Agent task success: **1.0**
Latency p50 / p95: **9.4 ms / 15.5 ms**

| Category | Questions | Task success | Recall@5 |
|---|---|---|---|
| architecture | 20 | 1.0 | 0.5 |
| code_search | 20 | 1.0 | 0.975 |
| dependency_tracing | 20 | 1.0 | 0.767 |
| bug_investigation | 20 | 1.0 | 0.95 |
| pr_review | 20 | 1.0 | 0.55 |
| test_generation | 4 | 1.0 | 1.0 |

## Per-question results

| id | category | success | recall@5 | latency (ms) |
|---|---|---|---|---|
| arch_01 | architecture | ✅ | 1.0 | 722.8 |
| arch_02 | architecture | ✅ | None | 8.9 |
| arch_03 | architecture | ✅ | 0.0 | 8.9 |
| arch_04 | architecture | ✅ | 0.0 | 8.8 |
| arch_05 | architecture | ✅ | None | 8.7 |
| arch_06 | architecture | ✅ | 1.0 | 12.2 |
| arch_07 | architecture | ✅ | None | 8.9 |
| arch_08 | architecture | ✅ | 1.0 | 8.4 |
| arch_09 | architecture | ✅ | None | 8.5 |
| arch_10 | architecture | ✅ | None | 8.4 |
| arch_11 | architecture | ✅ | None | 9.1 |
| arch_12 | architecture | ✅ | 0.0 | 8.6 |
| arch_13 | architecture | ✅ | None | 8.6 |
| arch_14 | architecture | ✅ | None | 11.1 |
| arch_15 | architecture | ✅ | None | 8.8 |
| arch_16 | architecture | ✅ | None | 8.8 |
| arch_17 | architecture | ✅ | None | 10.9 |
| arch_18 | architecture | ✅ | 1.0 | 11.0 |
| arch_19 | architecture | ✅ | 0.0 | 9.2 |
| arch_20 | architecture | ✅ | None | 8.4 |
| cs_01 | code_search | ✅ | 0.5 | 9.8 |
| cs_02 | code_search | ✅ | 1.0 | 9.9 |
| cs_03 | code_search | ✅ | 1.0 | 9.1 |
| cs_04 | code_search | ✅ | 1.0 | 9.4 |
| cs_05 | code_search | ✅ | 1.0 | 9.2 |
| cs_06 | code_search | ✅ | 1.0 | 9.2 |
| cs_07 | code_search | ✅ | 1.0 | 10.0 |
| cs_08 | code_search | ✅ | 1.0 | 13.1 |
| cs_09 | code_search | ✅ | 1.0 | 9.8 |
| cs_10 | code_search | ✅ | 1.0 | 11.2 |
| cs_11 | code_search | ✅ | 1.0 | 9.1 |
| cs_12 | code_search | ✅ | 1.0 | 9.2 |
| cs_13 | code_search | ✅ | 1.0 | 8.9 |
| cs_14 | code_search | ✅ | 1.0 | 9.6 |
| cs_15 | code_search | ✅ | 1.0 | 10.1 |
| cs_16 | code_search | ✅ | 1.0 | 9.5 |
| cs_17 | code_search | ✅ | 1.0 | 9.1 |
| cs_18 | code_search | ✅ | 1.0 | 9.4 |
| cs_19 | code_search | ✅ | 1.0 | 9.4 |
| cs_20 | code_search | ✅ | 1.0 | 9.6 |
| dep_01 | dependency_tracing | ✅ | 0.5 | 9.7 |
| dep_02 | dependency_tracing | ✅ | 0.6666666666666666 | 9.7 |
| dep_03 | dependency_tracing | ✅ | 1.0 | 9.3 |
| dep_04 | dependency_tracing | ✅ | 0.6666666666666666 | 9.7 |
| dep_05 | dependency_tracing | ✅ | 1.0 | 9.3 |
| dep_06 | dependency_tracing | ✅ | 1.0 | 9.5 |
| dep_07 | dependency_tracing | ✅ | 0.5 | 9.0 |
| dep_08 | dependency_tracing | ✅ | 1.0 | 9.3 |
| dep_09 | dependency_tracing | ✅ | 1.0 | 9.6 |
| dep_10 | dependency_tracing | ✅ | 0.3333333333333333 | 9.3 |
| dep_11 | dependency_tracing | ✅ | 0.6666666666666666 | 9.4 |
| dep_12 | dependency_tracing | ✅ | 1.0 | 9.0 |
| dep_13 | dependency_tracing | ✅ | 0.5 | 9.4 |
| dep_14 | dependency_tracing | ✅ | 1.0 | 9.6 |
| dep_15 | dependency_tracing | ✅ | 1.0 | 9.4 |
| dep_16 | dependency_tracing | ✅ | 1.0 | 9.9 |
| dep_17 | dependency_tracing | ✅ | 0.5 | 10.2 |
| dep_18 | dependency_tracing | ✅ | 1.0 | 9.3 |
| dep_19 | dependency_tracing | ✅ | 0.0 | 10.0 |
| dep_20 | dependency_tracing | ✅ | 1.0 | 9.4 |
| bug_01 | bug_investigation | ✅ | 1.0 | 15.5 |
| bug_02 | bug_investigation | ✅ | 1.0 | 13.3 |
| bug_03 | bug_investigation | ✅ | 1.0 | 12.2 |
| bug_04 | bug_investigation | ✅ | 0.5 | 13.2 |
| bug_05 | bug_investigation | ✅ | 1.0 | 12.6 |
| bug_06 | bug_investigation | ✅ | 1.0 | 13.3 |
| bug_07 | bug_investigation | ✅ | 1.0 | 12.3 |
| bug_08 | bug_investigation | ✅ | 1.0 | 15.5 |
| bug_09 | bug_investigation | ✅ | 0.5 | 12.6 |
| bug_10 | bug_investigation | ✅ | 1.0 | 11.5 |
| bug_11 | bug_investigation | ✅ | 1.0 | 12.3 |
| bug_12 | bug_investigation | ✅ | 1.0 | 13.4 |
| bug_13 | bug_investigation | ✅ | 1.0 | 13.4 |
| bug_14 | bug_investigation | ✅ | 1.0 | 14.0 |
| bug_15 | bug_investigation | ✅ | 1.0 | 11.6 |
| bug_16 | bug_investigation | ✅ | 1.0 | 12.0 |
| bug_17 | bug_investigation | ✅ | 1.0 | 12.2 |
| bug_18 | bug_investigation | ✅ | 1.0 | 9.1 |
| bug_19 | bug_investigation | ✅ | 1.0 | 13.7 |
| bug_20 | bug_investigation | ✅ | 1.0 | 13.0 |
| rev_01 | pr_review | ✅ | 1.0 | 9.7 |
| rev_02 | pr_review | ✅ | 1.0 | 9.0 |
| rev_03 | pr_review | ✅ | 0.0 | 8.9 |
| rev_04 | pr_review | ✅ | 0.0 | 8.6 |
| rev_05 | pr_review | ✅ | 0.0 | 9.1 |
| rev_06 | pr_review | ✅ | 1.0 | 9.6 |
| rev_07 | pr_review | ✅ | 1.0 | 9.5 |
| rev_08 | pr_review | ✅ | 1.0 | 9.6 |
| rev_09 | pr_review | ✅ | 0.0 | 9.2 |
| rev_10 | pr_review | ✅ | 1.0 | 9.5 |
| rev_11 | pr_review | ✅ | 0.0 | 8.7 |
| rev_12 | pr_review | ✅ | 1.0 | 8.6 |
| rev_13 | pr_review | ✅ | 0.0 | 8.6 |
| rev_14 | pr_review | ✅ | 0.0 | 8.6 |
| rev_15 | pr_review | ✅ | 1.0 | 9.3 |
| rev_16 | pr_review | ✅ | 0.0 | 8.6 |
| rev_17 | pr_review | ✅ | 0.0 | 8.5 |
| rev_18 | pr_review | ✅ | 1.0 | 8.6 |
| rev_19 | pr_review | ✅ | 1.0 | 8.7 |
| rev_20 | pr_review | ✅ | 1.0 | 8.7 |
| test_01 | test_generation | ✅ | 1.0 | 2775.8 |
| test_02 | test_generation | ✅ | 1.0 | 1384.9 |
| test_03 | test_generation | ✅ | 1.0 | 1383.2 |
| test_04 | test_generation | ✅ | 1.0 | 1378.0 |
