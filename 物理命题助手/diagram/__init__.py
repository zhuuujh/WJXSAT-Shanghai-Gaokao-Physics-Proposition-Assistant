# -*- coding: utf-8 -*-
"""
diagram —— 物理示意图生成接入包。

包装《绘图脚本/generate_physics_diagram.py》的 matplotlib 出图能力：
- generator.py 懒加载（避免 matplotlib 拖慢 Streamlit 启动）

依赖方向：本包不依赖 streamlit；matplotlib 为可选依赖（函数内懒 import）。
"""

__version__ = "1.0.0"
