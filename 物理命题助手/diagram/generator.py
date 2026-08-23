# -*- coding: utf-8 -*-
"""
diagram.generator —— 程序化物理示意图懒加载包装。

复用 `绘图脚本/generate_physics_diagram.py` 的 10 个 draw_*_diagram()。
matplotlib 只在真正出图时才 import（避免拖慢 streamlit 启动）。

用法：
    generator.list_diagrams()            # ['受力图','抛体运动',...]
    generator.generate('受力图', 'out.png')   # 返回输出路径
"""

# 中文名 → generate_physics_diagram.py 中的函数名
_DIAGRAM_FUNCS = {
    "受力分析": "draw_force_diagram",
    "抛体运动": "draw_projectile_diagram",
    "机械波": "draw_wave_diagram",
    "光学成像": "draw_optics_diagram",
    "电场磁场": "draw_field_diagram",
    "图像题": "draw_graph_diagram",
    "电路": "draw_circuit_diagram",
    "LC振荡": "draw_lc_circuit",
    "弹簧振子": "draw_spring_oscillator",
    "带电粒子": "draw_charged_particle",
}

# 脚本路径（相对项目根目录）
_SCRIPT_REL = ("绘图脚本", "generate_physics_diagram.py")

import importlib.util
import sys
from pathlib import Path


def list_diagrams():
    """可用的示意图中文名列表。"""
    return list(_DIAGRAM_FUNCS.keys())


def _load_script():
    """按需加载绘图脚本模块（幂等）。"""
    root = Path(__file__).resolve().parent.parent
    script_path = root.joinpath(*_SCRIPT_REL)
    if not script_path.exists():
        raise FileNotFoundError(f"未找到绘图脚本：{script_path}")
    module_name = "_generate_physics_diagram"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[module_name] = module
    return module


def generate(diagram_name, output_path):
    """生成指定示意图到 output_path，返回输出路径。

    diagram_name 为 list_diagrams() 中的中文名；失败抛 ValueError。
    matplotlib 相关 import 仅在首次调用时执行。
    """
    func_name = _DIAGRAM_FUNCS.get(diagram_name)
    if func_name is None:
        raise ValueError(f"未知示意图：{diagram_name}，可选 {list_diagrams()}")

    module = _load_script()
    draw = getattr(module, func_name, None)
    if draw is None:
        raise ValueError(f"绘图脚本缺少函数 {func_name}")

    output = str(output_path)
    draw(output)  # 函数内部自含 setup_plot + save
    return output


def generate_all(output_dir, prefix="diagram"):
    """批量生成全部示意图到目录，返回 {名称: 输出路径}。"""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for i, name in enumerate(list_diagrams(), start=1):
        output = out_dir / f"{prefix}_{i:02d}_{name}.png"
        results[name] = generate(name, output)
    return results
