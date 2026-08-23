# -*- coding: utf-8 -*-
"""
scripts.count_loc —— 软著源代码行数统计。

统计范围：项目内所有 .py 与 .json 源文件（排除 __pycache__ / legacy / 生成的试卷 HTML）。
口径：去掉空行与纯注释行后的有效行数（软著常见统计口径）。
输出：按文件明细 + 业务代码/测试脚本分组小计 + 总计，供软著申请附用。

用法：
    python scripts/count_loc.py [--json]
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 不参与统计的目录/文件
EXCLUDE_DIRS = {"__pycache__", "legacy", ".git", "node_modules", "data"}
EXCLUDE_SUFFIXES = {".html", ".md", ".txt", ".db"}

# 分组：业务代码（软著核心）vs 配套（测试/脚本）
BIZ_DIRS = {"app.py", "engine", "question_bank", "knowledge", "diagram", "ui"}
AUX_DIRS = {"tests", "scripts"}


def is_blank_or_comment(line: str) -> bool:
    """判断行是否为 空行 / 纯注释（# 或 单行/多行 docstring 简化处理）。"""
    s = line.strip()
    if not s:
        return True
    if s.startswith("#"):
        return True
    # 简化：整行是 docstring 定界符或纯 docstring（多行注释）
    if s.startswith('"""') or s.startswith("'''"):
        return True
    return False


def count_file(path: Path) -> int:
    """单文件有效行数。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (UnicodeDecodeError, OSError):
        return 0
    # 用简单状态机跳过多行 docstring
    in_docstring = False
    count = 0
    for raw in lines:
        s = raw.strip()
        if not in_docstring:
            if s.startswith('"""') or s.startswith("'''"):
                # 可能单行 docstring 或跨多行
                if s.count('"""') >= 2 or s.count("'''") >= 2:
                    continue  # 单行 docstring
                in_docstring = True
                continue
            if s.startswith("#"):
                continue
            if s:
                count += 1
        else:
            if s.count('"""') >= 1 or s.count("'''") >= 1:
                in_docstring = False
            continue
    return count


def collect_files() -> list:
    """收集待统计文件（相对路径）。"""
    files = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        parts = rel.parts
        if any(part in EXCLUDE_DIRS for part in parts[:-1]):
            continue
        if p.suffix not in {".py", ".json"}:
            continue
        files.append(p)
    return files


def classify(parts) -> str:
    """按路径元组返回文件归属分组：业务 / 配套。"""
    if parts[0] in BIZ_DIRS:
        return "业务代码"
    if parts[0] in AUX_DIRS:
        return "配套"
    return "业务代码" if parts[0].endswith(".py") else "配套"


def main():
    parser = argparse.ArgumentParser(description="软著源代码行数统计")
    parser.add_argument("--json", action="store_true", help="输出 JSON 明细")
    args = parser.parse_args()

    files = collect_files()
    groups = {}
    total = 0
    detail = []

    for p in files:
        rel = p.relative_to(ROOT)
        group = classify(rel.parts)
        n = count_file(p)
        total += n
        detail.append((str(rel), group, n))
        groups[group] = groups.get(group, 0) + n

    if args.json:
        import json

        print(json.dumps({"files": [{"path": p, "group": g, "lines": n} for p, g, n in detail],
                          "groups": groups, "total": total}, ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print("  上海物理等级考命题助手 · 源代码行数统计（软著用）")
    print("=" * 60)
    print(f"{'文件':<48}{'分组':<8}{'行数':>6}")
    print("-" * 60)
    for path, group, n in sorted(detail, key=lambda x: (-x[2], x[0])):
        print(f"{path:<48}{group:<8}{n:>6}")
    print("-" * 60)
    for group in sorted(groups):
        print(f"{group:<55}{groups[group]:>6}")
    print(f"{'总计':<55}{total:>6}")
    print("=" * 60)
    print(f"业务代码 {groups.get('业务代码', 0)} 行 + 配套 {groups.get('配套', 0)} 行 = {total} 行")
    print(f"软著要求：前后各 30 页 ≈ 3000 行　→　{'✅ 达标' if total >= 3000 else '❌ 不足'}")

    return 0 if total >= 3000 else 1


if __name__ == "__main__":
    sys.exit(main())
