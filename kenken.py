#!/usr/bin/env python3
"""kenken - 贤者之谜(KenKen)生成器与求解器。

纯标准库。生成流程: 随机拉丁方阵 -> 随机划分笼子 -> 由笼内数字推算
目标与运算符。求解: 回溯 + 行列互异 + 笼约束剪枝。
"""
import argparse
import itertools
import random
import sys

OPS = ["+", "-", "x", "/"]


def cage_value(cells, values, op):
    vals = sorted(values[c] for c in cells)
    if op == "+":
        return sum(vals)
    if op == "x":
        p = 1
        for v in vals:
            p *= v
        return p
    if op == "-":
        return vals[-1] - vals[0] if len(vals) == 2 else None
    if op == "/":
        if len(vals) == 2 and vals[0] != 0 and vals[1] % vals[0] == 0:
            return vals[1] // vals[0]
        return None
    return None  # 单格笼: 目标即该值


def latin_square(n, rng):
    base = list(range(1, n + 1))
    rng.shuffle(base)
    rows = [[base[(i + j) % n] for j in range(n)] for i in range(n)]
    order = list(range(n))
    rng.shuffle(order)
    rows = [rows[i] for i in order]
    perm = list(range(n))
    rng.shuffle(perm)
    return [[row[perm[j]] for j in range(n)] for row in rows]


def partition_cages(n, rng, max_cage=4):
    cells = [(r, c) for r in range(n) for c in range(n)]
    rng.shuffle(cells)
    assigned = {}
    cages = []
    for cell in cells:
        if cell in assigned:
            continue
        cage = [cell]
        assigned[cell] = len(cages)
        target_size = rng.randint(1, max_cage)
        frontier = [cell]
        while len(cage) < target_size and frontier:
            r, c = frontier.pop(rng.randrange(len(frontier)))
            nbrs = [(r + dr, c + dc) for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            rng.shuffle(nbrs)
            grown = False
            for nb in nbrs:
                if 0 <= nb[0] < n and 0 <= nb[1] < n and nb not in assigned:
                    cage.append(nb)
                    assigned[nb] = len(cages)
                    frontier.append(nb)
                    grown = True
                    break
            if not grown:
                continue
        cages.append(cage)
    return cages


def make_puzzle(n, seed=None):
    rng = random.Random(seed)
    grid = latin_square(n, rng)
    values = {(r, c): grid[r][c] for r in range(n) for c in range(n)}
    cages = partition_cages(n, rng)
    puzzle = []
    for cage in cages:
        if len(cage) == 1:
            puzzle.append({"cells": cage, "op": "=", "target": values[cage[0]]})
            continue
        ops = [o for o in OPS if cage_value(cage, values, o) is not None]
        if not ops:
            # 退化为单格拆分(极罕见): 把笼拆成单格
            for cell in cage:
                puzzle.append({"cells": [cell], "op": "=", "target": values[cell]})
            continue
        op = rng.choice(ops)
        puzzle.append({"cells": cage, "op": op, "target": cage_value(cage, values, op)})
    return n, puzzle, grid


def cage_satisfied(cage, assign):
    """assign: dict cell->value(部分)。返回 True(满足)/False(违反)/None(未定)。"""
    cells = cage["cells"]
    vals = [assign.get(c) for c in cells]
    if any(v is None for v in vals):
        return None
    op, target = cage["op"], cage["target"]
    if op == "=":
        return vals[0] == target
    if op == "+":
        return sum(vals) == target
    if op == "x":
        p = 1
        for v in vals:
            p *= v
        return p == target
    if op == "-":
        a, b = vals
        return abs(a - b) == target
    if op == "/":
        a, b = vals
        return (a % b == 0 and a // b == target) or (b % a == 0 and b // a == target)
    return False


def solve(n, puzzle, limit=2000000):
    cells = [(r, c) for r in range(n) for c in range(n)]
    cage_of = {}
    for i, cage in enumerate(puzzle):
        for c in cage["cells"]:
            cage_of[c] = i
    row_used = [set() for _ in range(n)]
    col_used = [set() for _ in range(n)]
    assign = {}
    nodes = [0]

    # 启发式: 先填单格笼
    order = sorted(cells, key=lambda c: 0 if puzzle[cage_of[c]]["op"] == "=" else 1)

    def rec(idx):
        nodes[0] += 1
        if nodes[0] > limit:
            return None
        if idx == len(order):
            return dict(assign)
        r, c = order[idx]
        for v in range(1, n + 1):
            if v in row_used[r] or v in col_used[c]:
                continue
            assign[(r, c)] = v
            row_used[r].add(v)
            col_used[c].add(v)
            ok = True
            cage = puzzle[cage_of[(r, c)]]
            st = cage_satisfied(cage, assign)
            if st is False:
                ok = False
            if ok:
                res = rec(idx + 1)
                if res is not None:
                    return res
            del assign[(r, c)]
            row_used[r].discard(v)
            col_used[c].discard(v)
        return None

    sol = rec(0)
    return sol, nodes[0]


def check_solution(n, puzzle, sol):
    if sol is None:
        return False, "无解"
    for r in range(n):
        if sorted(sol[(r, c)] for c in range(n)) != list(range(1, n + 1)):
            return False, f"第 {r + 1} 行不是 1..{n}"
    for c in range(n):
        if sorted(sol[(r, c)] for r in range(n)) != list(range(1, n + 1)):
            return False, f"第 {c + 1} 列不是 1..{n}"
    for i, cage in enumerate(puzzle):
        if cage_satisfied(cage, sol) is not True:
            return False, f"笼 {i + 1} 不满足 {cage['target']}{cage['op']}"
    return True, "合法"


def render_puzzle(n, puzzle, sol=None):
    cid = {}
    for i, cage in enumerate(puzzle):
        for c in cage["cells"]:
            cid[c] = i
    lines = []
    for r in range(n):
        row = []
        for c in range(n):
            i = cid[(r, c)]
            cage = puzzle[i]
            tag = f"{cage['target']}{cage['op']}" if (r, c) == min(cage["cells"]) else "  "
            val = str(sol[(r, c)]) if sol else "·"
            row.append(f"{tag:>4}{val}")
        lines.append(" ".join(row))
    return "\n".join(lines)


def selftest():
    fails = 0
    # 1) 手工 4x4: 已知拉丁方阵, 笼子手工验算
    n = 4
    puzzle = [
        {"cells": [(0, 0), (0, 1)], "op": "+", "target": 3},   # 1+2
        {"cells": [(0, 2), (0, 3)], "op": "x", "target": 12},   # 3x4
        {"cells": [(1, 0), (2, 0)], "op": "-", "target": 1},    # |2-3|
        {"cells": [(1, 1)], "op": "=", "target": 3},
        {"cells": [(1, 2), (1, 3)], "op": "+", "target": 5},   # 4+1
        {"cells": [(2, 1), (3, 1)], "op": "x", "target": 4},    # 4x1
        {"cells": [(2, 2), (2, 3)], "op": "-", "target": 1},    # |2-1|
        {"cells": [(3, 0)], "op": "=", "target": 4},
        {"cells": [(3, 2), (3, 3)], "op": "+", "target": 5},   # 3+2
    ]
    sol, _ = solve(n, puzzle)
    ok, msg = check_solution(n, puzzle, sol)
    print(f"[{'通过' if ok else '失败'}] 手工 4x4 求解: {msg}")
    fails += 0 if ok else 1
    # 2) 20 个种子生成 -> 全部可解且合法
    bad = 0
    for seed in range(20):
        for size in (4, 5):
            nn, pz, _ = make_puzzle(size, seed=seed)
            s, _ = solve(nn, pz)
            okk, _ = check_solution(nn, pz, s)
            if not okk:
                bad += 1
                print(f"  种子 {seed} size {size} 求解失败")
    print(f"[{'通过' if bad == 0 else '失败'}] 20 种子 x 4x4/5x5 全部可解合法")
    fails += 0 if bad == 0 else 1
    # 3) 矛盾笼子 -> 无解 (同行两个 1)
    bad_pz = [{"cells": [(0, 0)], "op": "=", "target": 1},
              {"cells": [(0, 1)], "op": "=", "target": 1},
              {"cells": [(1, 0)], "op": "=", "target": 1},
              {"cells": [(1, 1)], "op": "=", "target": 2}]
    s, _ = solve(2, bad_pz)
    ok3 = s is None
    print(f"[{'通过' if ok3 else '失败'}] 矛盾笼子返回无解")
    fails += 0 if ok3 else 1
    print(f"自检结果: {3 - fails} 通过, {fails} 失败")
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kenken", description="KenKen 生成器与求解器")
    ap.add_argument("--size", type=int, choices=[4, 5], default=4, help="棋盘尺寸")
    ap.add_argument("--seed", type=int, default=None, help="随机种子")
    ap.add_argument("--solve", action="store_true", help="求解生成的谜题")
    ap.add_argument("--show-solution", action="store_true", help="显示生成时的答案")
    ap.add_argument("--selftest", action="store_true", help="运行内置自检")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    n, puzzle, answer = make_puzzle(args.size, seed=args.seed)
    print(f"KenKen {n}x{n}（种子={args.seed}）")
    print(render_puzzle(n, puzzle))
    print(f"\n共 {len(puzzle)} 个笼子。")
    if args.show_solution:
        print("\n生成答案:")
        print(render_puzzle(n, puzzle, {(r, c): answer[r][c] for r in range(n) for c in range(n)}))
    if args.solve:
        sol, nodes = solve(n, puzzle)
        ok, msg = check_solution(n, puzzle, sol)
        print(f"\n求解: {msg}（搜索节点 {nodes}）")
        if sol:
            print(render_puzzle(n, puzzle, sol))
    return 0


if __name__ == "__main__":
    sys.exit(main())
