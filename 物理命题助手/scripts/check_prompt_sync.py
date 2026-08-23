# -*- coding: utf-8 -*-
"""
scripts.check_prompt_sync —— 校验 index.html 与 engine/prompts.py 的命题规范副本是否同步。

命题规范的唯一真源在 `engine/prompts.py`（PROMPT_VERSION 版本化）。
`index.html`（网页版）内嵌了一份 JS 模板字符串副本，二者一旦漂移，
本地版与网页版命题行为就会不一致。本脚本逐行 diff 两份文本。

用法：
    python scripts/check_prompt_sync.py        # 检查，有差异返回码 1
    python scripts/check_prompt_sync.py --fix  # 用 prompts.py 覆盖 index.html 副本

注意：--fix 是机械替换整个 命题规范 模板字符串，不触碰 index.html 其余部分。
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = ROOT / "index.html"

# 匹配 index.html 中的 命题规范 模板字符串
# 形如：  const 命题规范 = `
#          ...内容...
#          `;
# 组1=开始标记，组2=内容，组3=结束标记
_PROMPT_SPLIT_RE = re.compile(
    r"(const\s*命题规范\s*=\s*`)(.*?)(`\s*;)", re.S
)


def extract_index_prompt():
    """提取 index.html 内嵌的 命题规范 文本；未找到返回 None。"""
    if not INDEX_HTML.exists():
        return None
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = _PROMPT_SPLIT_RE.search(html)
    return m.group(2) if m else None


def import_python_prompt():
    """从 engine.prompts 导入真源文本。"""
    sys.path.insert(0, str(ROOT))
    from engine import prompts as prompts_mod

    return prompts_mod.命题规范


def normalize(text: str) -> list:
    """统一行结束符 + 去首尾空行 → 行列表。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return [ln for ln in text.strip("\n").split("\n")]


# JS 模板字符串转义映射（\x → 烹饪值）
_JS_COOK_MAP = {
    "\\": "\\", "/": "/", "n": "\n", "t": "\t", "r": "\r",
    "`": "`", "$": "$", "'": "'", '"': '"', "b": "\b", "f": "\f", "v": "\v",
}


def js_cook(s: str) -> str:
    """把 JS 模板字符串源文本解码为运行时字符串值。

    关键差异：index.html 里双反斜杠加左括号在 JS 运行时是 单反斜杠加左括号；
    而 Python 普通字符串里的 单反斜杠加左括号 就是原样。逐字对比源文本
    会产生误报，必须统一到"AI 实际收到的有效文本"这一层再比较。
    """
    out = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            c = s[i + 1]
            if c == "u" and i + 5 < len(s):
                try:
                    out.append(chr(int(s[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            out.append(_JS_COOK_MAP.get(c, c))  # 未识别转义按 JS 规则取字符本身
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def js_escape(s: str) -> str:
    """把文本转成 JS 模板字符串源码（保证烹饪后等于原文，且不破坏 HTML）。

    除常规转义（\\ → \\\\、` → \\`、$ → \\$）外，还必须把 `</script` 写成
    `</\\script`：index.html 中模板字符串位于 <script> 块内，若出现字面
    `</script>` 会提前闭合 script 元素导致整个页面 JS 失效。
    （\\/ 在 JS 烹饪后仍为 /，故运行时值不变。）
    """
    out = []
    i = 0
    while i < len(s):
        rest = s[i:]
        if rest.startswith("</script"):
            out.append("<\\/script")
            i += len("</script")
            continue
        ch = s[i]
        if ch == "\\":
            out.append("\\\\")
        elif ch == "`":
            out.append("\\`")
        elif ch == "$":
            out.append("\\$")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def compare(index_raw_text, python_text):
    """比较 python 运行时文本 与 index.html 烹饪后文本。"""
    import difflib

    a = normalize(python_text)
    b = normalize(js_cook(index_raw_text))
    if a == b:
        return True, []
    diff = []
    for line in difflib.unified_diff(a, b, fromfile="engine/prompts.py",
                                     tofile="index.html", lineterm=""):
        diff.append(line)
    return False, diff


def fix_index(python_text) -> bool:
    """用真源（JS 转义后）覆盖 index.html 的 命题规范 模板字符串内容。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = _PROMPT_SPLIT_RE.search(html)
    if not m:
        print("❌ index.html 中未找到 命题规范 模板字符串，无法 --fix")
        return False
    content = js_escape(python_text)
    new_html = html[: m.start()] + m.group(1) + "\n" + content + "\n" + m.group(3) + html[m.end():]
    INDEX_HTML.write_text(new_html, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description="命题规范双副本同步校验")
    parser.add_argument("--fix", action="store_true", help="用 prompts.py 覆盖 index.html 副本")
    args = parser.parse_args()

    python_text = import_python_prompt()
    index_text = extract_index_prompt()

    if index_text is None:
        print(f"❌ 未能在 {INDEX_HTML} 中找到 命题规范 模板字符串")
        return 2

    # --fix 是无条件重写命令（不因当前已同步而跳过），保证副本被真源重置
    if args.fix:
        if fix_index(python_text):
            print("✅ 已用 prompts.py 覆盖 index.html 中的 命题规范 副本")
            print("   请人工确认 index.html 其余部分未受影响")
            return 0
        return 1

    ok, diffs = compare(index_text, python_text)
    if ok:
        print("✅ 命题规范两副本完全一致（engine/prompts.py ⇄ index.html）")
        return 0

    print(f"⚠️  命题规范两副本不一致（{len(diffs)} 行差异），请运行 --fix 或人工同步：")
    for line in diffs:
        print("   " + line)
    print()
    print("提示：真源在 engine/prompts.py，index.html 仅作展示副本。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
