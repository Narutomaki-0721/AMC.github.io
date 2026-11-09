# 用 Python 核对舞蹈竞赛数据

[2026 C 题](../problems/历年/2026#problem-c)要求从评委打分和淘汰结果推断观众投票。先做一个 15 分钟的数据核查，看看哪些量能直接读出，哪些需要估计。

## 读入官方附件

下载 [COMAP 原始 CSV](https://www.contest.comap.com/undergraduate/contests/mcm/contests/2026/problems/2026_MCM_Problem_C_Data.csv)，保留原文件名，将下面的脚本放在同一目录运行。只需 Python 标准库。

```python
import csv
from pathlib import Path

path = Path(__file__).with_name("2026_MCM_Problem_C_Data.csv")
with path.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

first = [row for row in rows if row["season"] == "1"]
print(len(rows), len(first))
for row in first:
    print(row["celebrity_name"], row["week1_judge1_score"])
```

首行应输出 `421 6`，分别是全部参赛记录数和第一季的参赛记录数。一行对应选手在一季的记录，同一行里有多周评分。检查某一周时，先看题面如何区分缺席评委、未举行比赛和选手已淘汰，再决定怎样处理空值与零。

## 交给队友的问题

挑一场发生淘汰的周次，按当季计分规则固定评委给分。写出两组不同的观众投票份额，使两组都能解释同一淘汰结果。每组份额之和应为 1。交换记录，让队友只看规则、份额和评委分，独立算出淘汰者。若两组都成立，报告里应如何表达真实票数的不确定性？
