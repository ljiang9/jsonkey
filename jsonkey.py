#!/usr/bin/env python3
"""jsonkey — 从 JSON 里按点分路径提取、挑选、重命名键。

路径语法（自定义，不是 JSONPath）：
  a.b.c        逐层取键
  users.0.name 数组下标
  users.*.name 通配：数组全部元素 / 对象全部键

退出码：0 成功；1 路径不存在 / 文件问题；2 JSON 非法 / 命令行用法错误。
"""

import argparse
import json
import re
import sys

VERSION = "0.1.0"


class JsonKeyError(Exception):
    pass


def parse_path(path):
    """'a.b.0.c' -> ['a', 'b', 0, 'c']；'*' 保持为通配标记。"""
    if not path:
        raise JsonKeyError("路径不能为空")
    segs = []
    for part in path.split("."):
        if part == "*":
            segs.append(("*",))
        elif re.fullmatch(r"-?\d+", part or ""):
            segs.append(int(part))
        elif part == "":
            raise JsonKeyError(f"路径 {path!r} 里有空的段")
        else:
            segs.append(part)
    return segs


def resolve(doc, segs):
    """返回 [(路径字符串, 值)]；通配展开为多个匹配。无匹配返回空列表。"""
    results = [("", doc)]
    for seg in segs:
        nxt = []
        for p, node in results:
            if seg == ("*",):
                if isinstance(node, dict):
                    items = node.items()
                elif isinstance(node, list):
                    items = enumerate(node)
                else:
                    continue
                for k, v in items:
                    nxt.append((f"{p}.{k}" if p else str(k), v))
            elif isinstance(seg, int):
                if isinstance(node, list) and -len(node) <= seg < len(node):
                    nxt.append((f"{p}.{seg}" if p else str(seg), node[seg]))
            else:
                if isinstance(node, dict) and seg in node:
                    nxt.append((f"{p}.{seg}" if p else seg, node[seg]))
        results = nxt
        if not results:
            break
    return results


def leaf_paths(node, prefix="", depth=None, cur=0):
    """列出所有叶子路径（标量值所在路径）。"""
    if depth is not None and cur >= depth:
        # 到达深度上限：把子树整体当作一个值
        return [prefix] if prefix else []
    if isinstance(node, dict):
        out = []
        for k, v in node.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.extend(leaf_paths(v, p, depth, cur + 1))
        return out or ([prefix] if prefix else [])
    if isinstance(node, list):
        out = []
        for i, v in enumerate(node):
            p = f"{prefix}.{i}" if prefix else str(i)
            out.extend(leaf_paths(v, p, depth, cur + 1))
        return out or ([prefix] if prefix else [])
    return [prefix] if prefix else []


def load_input(args):
    if args.stdin or args.file == "-":
        raw = sys.stdin.read()
        src = "<stdin>"
    else:
        try:
            with open(args.file, encoding="utf-8") as f:
                raw = f.read()
        except FileNotFoundError:
            print(f"error: 文件不存在：{args.file}", file=sys.stderr)
            sys.exit(1)
        except OSError as e:
            print(f"error: 无法读取文件 {args.file}：{e}", file=sys.stderr)
            sys.exit(1)
        src = args.file
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"error: {src} 不是合法 JSON（第 {e.lineno} 行：{e.msg}）", file=sys.stderr)
        sys.exit(2)


def dump(value, compact):
    if compact:
        print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2))


def cmd_extract(doc, path, compact):
    try:
        segs = parse_path(path)
    except JsonKeyError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    matches = resolve(doc, segs)
    if not matches:
        print(f"error: 路径不存在：{path}", file=sys.stderr)
        sys.exit(1)
    if len(matches) == 1 and ("*",) not in segs:
        dump(matches[0][1], compact)
    else:
        dump([v for _, v in matches], compact)


def cmd_pick(doc, spec, compact):
    out = {}
    for raw_path in spec.split(","):
        raw_path = raw_path.strip()
        if not raw_path:
            continue
        try:
            segs = parse_path(raw_path)
        except JsonKeyError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(2)
        matches = resolve(doc, segs)
        if not matches:
            print(f"error: 路径不存在：{raw_path}", file=sys.stderr)
            sys.exit(1)
        for p, v in matches:
            # 键名取路径最后一段；冲突时用完整路径
            key = p.split(".")[-1]
            if key in out:
                key = p
            out[key] = v
    dump(out, compact)


def cmd_rename(doc, spec, compact):
    # 只支持同一父级内的重命名：a.b:新名
    if ":" not in spec:
        print("error: --rename 格式应为 旧路径:新键名，例如 a.b:c", file=sys.stderr)
        sys.exit(2)
    old_path, new_key = spec.split(":", 1)
    new_key = new_key.strip()
    if not new_key or "." in new_key:
        print("error: 新键名不能为空且不能包含点号", file=sys.stderr)
        sys.exit(2)
    try:
        segs = parse_path(old_path.strip())
    except JsonKeyError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    if not segs or segs == [("*",)] or ("*",) in segs or isinstance(segs[-1], int):
        print("error: --rename 只支持确切的对象键路径（不支持通配符和数组下标）", file=sys.stderr)
        sys.exit(2)
    parent_segs, old_key = segs[:-1], segs[-1]
    parent = doc
    for s in parent_segs:
        if isinstance(parent, dict) and s in parent:
            parent = parent[s]
        elif isinstance(parent, list) and isinstance(s, int) and -len(parent) <= s < len(parent):
            parent = parent[s]
        else:
            parent = None
            break
    if not isinstance(parent, dict) or old_key not in parent:
        print(f"error: 路径不存在：{old_path}", file=sys.stderr)
        sys.exit(1)
    if new_key in parent and new_key != old_key:
        print(f"error: 目标键名已存在：{new_key}", file=sys.stderr)
        sys.exit(1)
    # 保持原键顺序：重建有序 dict
    new_parent = {new_key if k == old_key else k: v for k, v in parent.items()}
    parent.clear()
    parent.update(new_parent)
    dump(doc, compact)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="jsonkey",
        description="从 JSON 里按点分路径提取、挑选、重命名键（纯本地）。",
    )
    ap.add_argument("file", nargs="?", help="JSON 文件（--stdin 时可省略）")
    ap.add_argument("path", nargs="?", help="要点分路径，如 a.b.c / users.0.name / users.*.name")
    ap.add_argument("--pick", metavar="P1,P2", help="按多个路径拼一个新对象")
    ap.add_argument("--rename", metavar="旧路径:新键名", help="重命名一个键（确切路径）")
    ap.add_argument("--keys", action="store_true", help="列出所有叶子路径（发现模式）")
    ap.add_argument("--depth", type=int, default=None, help="--keys 的最大深度")
    ap.add_argument("--stdin", action="store_true", help="从标准输入读 JSON")
    ap.add_argument("--compact", action="store_true", help="输出压缩单行 JSON")
    ap.add_argument("--version", action="version", version=f"jsonkey {VERSION}")
    args = ap.parse_args(argv)

    # --stdin 时第一个位置参数其实是路径（文件位置参数被 --stdin 取代）
    if args.stdin and args.file and args.path is None:
        args.path, args.file = args.file, None

    if not args.stdin and not args.file:
        ap.error("需要指定 JSON 文件，或使用 --stdin")

    doc = load_input(args)

    modes = [bool(args.path), bool(args.pick), bool(args.rename), args.keys]
    if sum(modes) > 1:
        ap.error("path / --pick / --rename / --keys 一次只能用一个")
    if sum(modes) == 0:
        ap.error("需要指定一个操作：路径、--pick、--rename 或 --keys")

    if args.keys:
        if args.depth is not None and args.depth < 1:
            ap.error("--depth 必须 >= 1")
        for p in leaf_paths(doc, depth=args.depth):
            print(p)
    elif args.pick:
        cmd_pick(doc, args.pick, args.compact)
    elif args.rename:
        cmd_rename(doc, args.rename, args.compact)
    else:
        cmd_extract(doc, args.path, args.compact)


if __name__ == "__main__":
    main()
