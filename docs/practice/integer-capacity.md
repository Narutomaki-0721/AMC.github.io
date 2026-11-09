# 单题练习 · 增加半单位资源有用吗？

沿用[整数规划入门](../resources/integer-programming.md)的两变量模型。把第一条约束右侧的资源上限从 17.5 逐步增加，其他条件保持不变。先猜一猜：资源要增加到多少，目标值才第一次超过 23？

## 可复现的枚举

下面的程序只用 Python 标准语法。所有数值都是教学模型的参数，可以在本地直接运行。

```python
for capacity in [17.5, 18, 20, 21]:
    feasible = [
        (x + 10 * y, x, y)
        for x in range(4)
        for y in range(int(capacity // 7) + 1)
        if x + 7 * y <= capacity
    ]
    value, x, y = max(feasible)
    print(capacity, x, y, value)
```

| 资源上限 | 最优方案 (x, y) | 最优目标值 |
| --- | --- | --- |
| 17.5 | (3, 2) | 23 |
| 18 | (3, 2) | 23 |
| 20 | (3, 2) | 23 |
| 21 | (0, 3) | 30 |

前三档的整数决策相同。当上限达到 21，首次可以选择三个单位的 `y`。复盘时再写一句：如果预算只能从 17.5 增加到 18，这项追加投入对当前目标有没有价值？

这是基于官方示例设计的参数练习。[Google OR-Tools 示例](https://developers.google.com/optimization/mip/mip_example)
