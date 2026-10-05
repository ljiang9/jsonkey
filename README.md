# jsonkey

从 JSON 里按点分路径**提取、挑选、重命名键**的小工具。纯标准库、纯本地运行。

## 安装

```bash
python3 -m jsonkey --version
```

## 快速开始

```bash
# 点分路径提取
python3 -m jsonkey examples/data.json owner.email
# => "wangfang@example.com"

# 数组下标
python3 -m jsonkey examples/data.json users.0.name
# => "阿强"

# 通配符：取出数组里每个元素的某字段
python3 -m jsonkey examples/data.json users.*.email
# => ["qiang@example.com", "hong@example.com", "wang@example.com"]

# --pick：按多个路径拼一个新对象
python3 -m jsonkey examples/data.json --pick "app,owner.name,users.*.name"

# --rename：重命名一个键（确切路径，同一父级内）
python3 -m jsonkey examples/data.json --rename "limits.disk:storage"

# --keys：列出所有叶子路径（先看结构再动手）
python3 -m jsonkey examples/data.json --keys
python3 -m jsonkey examples/data.json --keys --depth 2

# 从管道读
cat examples/data.json | python3 -m jsonkey --stdin users.1.roles

# 压缩输出
python3 -m jsonkey examples/data.json --pick "app,version" --compact
```

## 路径语法

| 写法 | 含义 |
|---|---|
| `a.b.c` | 逐层取对象键 |
| `users.0.name` | 数组下标（支持负数） |
| `users.*.name` | 通配：数组全部元素 / 对象全部键 |

注意：这是 jsonkey 自定义的迷你语法，**不是 JSONPath**（不支持过滤表达式、递归下降等）。键名本身含点号时无法表达，这是已知取舍。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 路径不存在 / 文件读不到（中文报错，无 traceback） |
| 2 | JSON 非法 / 命令行用法错误 |

## 诚实说明

- `--rename` 只支持确切的对象键路径，不支持通配符和数组下标；重命名保持原键顺序。
- `--pick` 的结果键名默认取路径最后一段，冲突时退化为完整路径。
- 提取到单个值时直接打印该值；通配展开多个值时打印 JSON 数组。
