# RepoPilot Evaluation Report

Questions: **104**
Retrieval Recall@5: **0.792**
Retrieval Recall@10: **0.819**
Citation correctness: **0.512**
Agent task success: **1.0**
Latency p50 / p95: **9.1 ms / 22.3 ms**

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
| arch_01 | architecture | ✅ | 1.0 | 576.7 |
| arch_02 | architecture | ✅ | None | 8.4 |
| arch_03 | architecture | ✅ | 0.0 | 8.7 |
| arch_04 | architecture | ✅ | 0.0 | 8.2 |
| arch_05 | architecture | ✅ | None | 8.3 |
| arch_06 | architecture | ✅ | 1.0 | 11.9 |
| arch_07 | architecture | ✅ | None | 8.2 |
| arch_08 | architecture | ✅ | 1.0 | 8.0 |
| arch_09 | architecture | ✅ | None | 7.9 |
| arch_10 | architecture | ✅ | None | 7.9 |
| arch_11 | architecture | ✅ | None | 8.9 |
| arch_12 | architecture | ✅ | 0.0 | 8.1 |
| arch_13 | architecture | ✅ | None | 8.2 |
| arch_14 | architecture | ✅ | None | 8.2 |
| arch_15 | architecture | ✅ | None | 8.0 |
| arch_16 | architecture | ✅ | None | 8.5 |
| arch_17 | architecture | ✅ | None | 8.0 |
| arch_18 | architecture | ✅ | 1.0 | 8.1 |
| arch_19 | architecture | ✅ | 0.0 | 7.9 |
| arch_20 | architecture | ✅ | None | 7.8 |
| cs_01 | code_search | ✅ | 0.5 | 9.8 |
| cs_02 | code_search | ✅ | 1.0 | 8.7 |
| cs_03 | code_search | ✅ | 1.0 | 8.5 |
| cs_04 | code_search | ✅ | 1.0 | 9.0 |
| cs_05 | code_search | ✅ | 1.0 | 9.9 |
| cs_06 | code_search | ✅ | 1.0 | 12.7 |
| cs_07 | code_search | ✅ | 1.0 | 12.2 |
| cs_08 | code_search | ✅ | 1.0 | 9.5 |
| cs_09 | code_search | ✅ | 1.0 | 9.8 |
| cs_10 | code_search | ✅ | 1.0 | 8.9 |
| cs_11 | code_search | ✅ | 1.0 | 8.8 |
| cs_12 | code_search | ✅ | 1.0 | 9.0 |
| cs_13 | code_search | ✅ | 1.0 | 8.7 |
| cs_14 | code_search | ✅ | 1.0 | 12.7 |
| cs_15 | code_search | ✅ | 1.0 | 12.3 |
| cs_16 | code_search | ✅ | 1.0 | 9.0 |
| cs_17 | code_search | ✅ | 1.0 | 9.6 |
| cs_18 | code_search | ✅ | 1.0 | 14.5 |
| cs_19 | code_search | ✅ | 1.0 | 10.4 |
| cs_20 | code_search | ✅ | 1.0 | 9.2 |
| dep_01 | dependency_tracing | ✅ | 0.5 | 9.2 |
| dep_02 | dependency_tracing | ✅ | 0.6666666666666666 | 9.2 |
| dep_03 | dependency_tracing | ✅ | 1.0 | 8.8 |
| dep_04 | dependency_tracing | ✅ | 0.6666666666666666 | 8.9 |
| dep_05 | dependency_tracing | ✅ | 1.0 | 8.6 |
| dep_06 | dependency_tracing | ✅ | 1.0 | 8.9 |
| dep_07 | dependency_tracing | ✅ | 0.5 | 9.5 |
| dep_08 | dependency_tracing | ✅ | 1.0 | 9.0 |
| dep_09 | dependency_tracing | ✅ | 1.0 | 9.6 |
| dep_10 | dependency_tracing | ✅ | 0.3333333333333333 | 9.8 |
| dep_11 | dependency_tracing | ✅ | 0.6666666666666666 | 9.9 |
| dep_12 | dependency_tracing | ✅ | 1.0 | 9.2 |
| dep_13 | dependency_tracing | ✅ | 0.5 | 10.0 |
| dep_14 | dependency_tracing | ✅ | 1.0 | 9.7 |
| dep_15 | dependency_tracing | ✅ | 1.0 | 9.1 |
| dep_16 | dependency_tracing | ✅ | 1.0 | 9.8 |
| dep_17 | dependency_tracing | ✅ | 0.5 | 9.8 |
| dep_18 | dependency_tracing | ✅ | 1.0 | 9.0 |
| dep_19 | dependency_tracing | ✅ | 0.0 | 10.1 |
| dep_20 | dependency_tracing | ✅ | 1.0 | 9.8 |
| bug_01 | bug_investigation | ✅ | 1.0 | 22.3 |
| bug_02 | bug_investigation | ✅ | 1.0 | 12.5 |
| bug_03 | bug_investigation | ✅ | 1.0 | 11.5 |
| bug_04 | bug_investigation | ✅ | 0.5 | 12.6 |
| bug_05 | bug_investigation | ✅ | 1.0 | 12.0 |
| bug_06 | bug_investigation | ✅ | 1.0 | 12.8 |
| bug_07 | bug_investigation | ✅ | 1.0 | 11.3 |
| bug_08 | bug_investigation | ✅ | 1.0 | 14.5 |
| bug_09 | bug_investigation | ✅ | 0.5 | 11.6 |
| bug_10 | bug_investigation | ✅ | 1.0 | 10.7 |
| bug_11 | bug_investigation | ✅ | 1.0 | 11.9 |
| bug_12 | bug_investigation | ✅ | 1.0 | 12.3 |
| bug_13 | bug_investigation | ✅ | 1.0 | 12.7 |
| bug_14 | bug_investigation | ✅ | 1.0 | 13.2 |
| bug_15 | bug_investigation | ✅ | 1.0 | 11.7 |
| bug_16 | bug_investigation | ✅ | 1.0 | 12.0 |
| bug_17 | bug_investigation | ✅ | 1.0 | 12.2 |
| bug_18 | bug_investigation | ✅ | 1.0 | 9.2 |
| bug_19 | bug_investigation | ✅ | 1.0 | 12.8 |
| bug_20 | bug_investigation | ✅ | 1.0 | 12.3 |
| rev_01 | pr_review | ✅ | 1.0 | 8.5 |
| rev_02 | pr_review | ✅ | 1.0 | 8.0 |
| rev_03 | pr_review | ✅ | 0.0 | 8.1 |
| rev_04 | pr_review | ✅ | 0.0 | 8.4 |
| rev_05 | pr_review | ✅ | 0.0 | 8.2 |
| rev_06 | pr_review | ✅ | 1.0 | 8.2 |
| rev_07 | pr_review | ✅ | 1.0 | 8.5 |
| rev_08 | pr_review | ✅ | 1.0 | 8.3 |
| rev_09 | pr_review | ✅ | 0.0 | 8.0 |
| rev_10 | pr_review | ✅ | 1.0 | 8.2 |
| rev_11 | pr_review | ✅ | 0.0 | 8.4 |
| rev_12 | pr_review | ✅ | 1.0 | 8.2 |
| rev_13 | pr_review | ✅ | 0.0 | 8.0 |
| rev_14 | pr_review | ✅ | 0.0 | 8.0 |
| rev_15 | pr_review | ✅ | 1.0 | 8.7 |
| rev_16 | pr_review | ✅ | 0.0 | 8.1 |
| rev_17 | pr_review | ✅ | 0.0 | 8.0 |
| rev_18 | pr_review | ✅ | 1.0 | 8.7 |
| rev_19 | pr_review | ✅ | 1.0 | 8.4 |
| rev_20 | pr_review | ✅ | 1.0 | 8.6 |
| test_01 | test_generation | ✅ | 1.0 | 3272.4 |
| test_02 | test_generation | ✅ | 1.0 | 1977.6 |
| test_03 | test_generation | ✅ | 1.0 | 1893.2 |
| test_04 | test_generation | ✅ | 1.0 | 1462.6 |
