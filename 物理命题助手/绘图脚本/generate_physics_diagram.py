#!/usr/bin/env python3
"""
上海物理等级考命题 - 物理示意图生成脚本
使用 matplotlib 生成常见的物理示意图，保存为PNG供LaTeX调用。

用法: python generate_physics_diagram.py <diagram_type> <output_path>
  diagram_type: force | projectile | wave | circuit | spring | optics | field | graph | custom
"""

import sys
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Circle, Rectangle
import warnings
warnings.filterwarnings('ignore')

def setup_plot():
    """设置统一的中文字体和样式"""
    # 查找可用的中文字体
    from matplotlib.font_manager import FontProperties
    import subprocess
    chinese_fonts = []
    try:
        result = subprocess.run(['fc-list', ':lang=zh'], capture_output=True, text=True, timeout=5)
        for line in result.stdout.split('\n'):
            if '.ttf' in line or '.ttc' in line:
                font_path = line.split(':')[0].strip()
                if font_path:
                    chinese_fonts.append(font_path)
    except:
        pass
    if not chinese_fonts:
        chinese_fonts = ['C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf',
                        'C:/Windows/Fonts/simsun.ttc', 'C:/Windows/Fonts/yahei.ttf']
    if chinese_fonts:
        for fp in chinese_fonts:
            if os.path.exists(fp):
                font_prop = FontProperties(fname=fp)
                plt.rcParams['font.family'] = font_prop.get_name()
                break
    plt.rcParams['axes.unicode_minus'] = False
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.set_aspect('equal')
    return fig, ax

def save_plot(fig, output_path):
    """保存图像"""
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Diagram saved to: {output_path}")

def draw_force_diagram(output_path):
    """受力分析图"""
    fig, ax = setup_plot()
    # 斜面受力
    # 斜面
    theta = np.radians(30)
    ax.plot([0, 4*np.cos(theta)], [0, 4*np.sin(theta)], 'k-', lw=2)
    ax.plot([0, 4], [0, 0], 'k--', alpha=0.3)

    # 物体（矩形）
    rect = Rectangle((1.5, 0.8), 1.2, 0.8, fill=True, facecolor='lightblue', edgecolor='blue', lw=2)
    ax.add_patch(rect)
    ax.text(2.1, 1.2, 'm', ha='center', va='center', fontsize=14)

    # 力的箭头
    # 重力 (竖直向下)
    ax.annotate('', xy=(2.1, 0.2), xytext=(2.1, 0.8),
                arrowprops=dict(arrowstyle='->', lw=2.5, color='red'))
    ax.text(2.1, 0.0, '$G=mg$', ha='center', fontsize=12, color='red')

    # 支持力 (垂直斜面向上)
    nx = 2.1 + 1.5*np.sin(theta)
    ny = 0.8 + 1.5*np.cos(theta)
    ax.annotate('', xy=(nx, ny), xytext=(2.1, 0.8),
                arrowprops=dict(arrowstyle='->', lw=2.5, color='blue'))
    ax.text(nx+0.2, ny, '$N$', fontsize=12, color='blue')

    # 摩擦力 (沿斜面向上)
    fx = 2.1 - 1.5*np.cos(theta)
    fy = 0.8 - 1.5*np.sin(theta)
    ax.annotate('', xy=(fx, fy), xytext=(2.1, 0.8),
                arrowprops=dict(arrowstyle='->', lw=2.5, color='green'))
    ax.text(fx-0.5, fy-0.2, '$f$', fontsize=12, color='green')

    # 角度标注
    ax.annotate('', xy=(3.5, 0), xytext=(3.5*np.cos(theta), 3.5*np.sin(theta)),
                arrowprops=dict(arrowstyle='<->', lw=1, color='gray'))
    ax.text(2.5, 0.4, '$\\theta$', fontsize=14)

    ax.set_xlim(-1, 5)
    ax.set_ylim(-0.5, 3.5)
    ax.axis('off')
    ax.set_title('受力分析图', fontsize=14)
    save_plot(fig, output_path)

def draw_projectile_diagram(output_path):
    """平抛运动图"""
    fig, ax = setup_plot()

    # 平抛轨迹
    x = np.linspace(0, 4, 100)
    y = -0.5 * 9.8 * (x/5)**2 + 3
    ax.plot(x, y, 'b-', lw=2)

    # 坐标轴
    ax.arrow(-0.3, 0, 5, 0, head_width=0.1, head_length=0.1, fc='k', ec='k')
    ax.arrow(0, -0.3, 0, 3.5, head_width=0.1, head_length=0.1, fc='k', ec='k')
    ax.text(4.8, -0.2, '$x$', fontsize=14)
    ax.text(-0.3, 3.5, '$y$', fontsize=14)

    # 起点
    ax.plot(0, 3, 'ro', markersize=6)
    ax.text(-0.2, 3.2, '$O$', fontsize=12)

    # 初速度
    ax.annotate('', xy=(1.2, 3), xytext=(0, 3),
                arrowprops=dict(arrowstyle='->', lw=2.5, color='red'))
    ax.text(0.4, 3.15, '$v_0$', fontsize=12, color='red')

    # 末速度
    ax.annotate('', xy=(4.2, 2.0), xytext=(4, 2.2),
                arrowprops=dict(arrowstyle='->', lw=2.5, color='red'))
    ax.text(4.3, 1.8, '$v$', fontsize=12, color='red')

    # 分速度
    vx = 0.5
    vy = -0.8
    ax.annotate('', xy=(4+vx, 2.2+vy), xytext=(4, 2.2),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='green', linestyle='dashed'))
    ax.text(4.2, 1.5, '$v_y$', fontsize=10, color='green')

    # 落点
    ax.plot(4, 2.2, 'ro', markersize=6)
    ax.text(4.1, 2.3, '$P$', fontsize=12)

    ax.set_xlim(-0.5, 5.5)
    ax.set_ylim(-0.5, 3.8)
    ax.axis('off')
    ax.set_title('平抛运动示意图', fontsize=14)
    save_plot(fig, output_path)

def draw_wave_diagram(output_path):
    """波形图"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 5))

    # 波形图
    x = np.linspace(0, 8, 400)
    y1 = 1.5 * np.sin(2*np.pi * x/4)
    y2 = 1.5 * np.sin(2*np.pi * x/4 - np.pi/4)

    ax1.plot(x, y1, 'b-', lw=2)
    ax1.plot(x, y2, 'r--', lw=1.5)
    ax1.axhline(y=0, color='gray', lw=0.5)
    ax1.set_ylabel('$y$', fontsize=12)
    ax1.set_xlabel('$x$', fontsize=12)
    ax1.set_title('机械波的图像', fontsize=14)
    ax1.legend(['$t_1$时刻', '$t_2$时刻'], fontsize=10)
    ax1.grid(True, alpha=0.3)

    # 振动图
    t = np.linspace(0, 4, 400)
    y = 1.5 * np.sin(2*np.pi * t/2)

    ax2.plot(t, y, 'g-', lw=2)
    ax2.axhline(y=0, color='gray', lw=0.5)
    ax2.set_ylabel('$y$', fontsize=12)
    ax2.set_xlabel('$t/s$', fontsize=12)
    ax2.set_title('质点的振动图像', fontsize=14)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    save_plot(fig, output_path)

def draw_optics_diagram(output_path):
    """光路图 - 折射与全反射"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    # 左图：光的折射
    ax1.set_xlim(-2, 2)
    ax1.set_ylim(-2, 2)

    # 界面
    ax1.plot([-2, 2], [0, 0], 'k-', lw=2)

    # 法线
    ax1.plot([0, 0], [-2, 2], 'k--', lw=1, alpha=0.5)

    # 入射光线
    theta1 = np.radians(60)
    ax1.annotate('', xy=(-1.5*np.sin(theta1), 1.5*np.cos(theta1)), xytext=(0, 0),
                arrowprops=dict(arrowstyle='->', lw=2, color='red'))
    ax1.text(-1.3, 1.3, '入射光', fontsize=9, color='red')

    # 折射光线
    theta2 = np.radians(35)
    ax1.annotate('', xy=(1.5*np.sin(theta2), -1.5*np.cos(theta2)), xytext=(0, 0),
                arrowprops=dict(arrowstyle='->', lw=2, color='blue'))
    ax1.text(1.0, -1.3, '折射光', fontsize=9, color='blue')

    # 角度标注
    ax1.text(0.3, 0.5, '$\\theta_1$', fontsize=12)
    ax1.text(0.3, -0.5, '$\\theta_2$', fontsize=12)

    ax1.text(-1.8, 1.5, '空气', fontsize=10)
    ax1.text(-1.8, -1.5, '玻璃', fontsize=10)
    ax1.axis('off')
    ax1.set_title('光的折射', fontsize=12)

    # 右图：全反射
    ax2.set_xlim(-2, 2)
    ax2.set_ylim(-2, 2)

    # 界面
    ax2.plot([-2, 2], [0, 0], 'k-', lw=2)

    # 法线
    ax2.plot([0, 0], [-2, 2], 'k--', lw=1, alpha=0.5)

    # 入射光线（达到临界角）
    theta_c = np.radians(42)
    ax2.annotate('', xy=(-1.5*np.sin(theta_c), 1.5*np.cos(theta_c)), xytext=(0, 0),
                arrowprops=dict(arrowstyle='->', lw=2, color='red'))

    # 反射光线
    ax2.annotate('', xy=(1.5*np.sin(theta_c), 1.5*np.cos(theta_c)), xytext=(0, 0),
                arrowprops=dict(arrowstyle='->', lw=2, color='orange'))
    ax2.text(1.0, 1.3, '反射光', fontsize=9, color='orange')

    # 无折射光
    ax2.text(0.5, -0.8, '无折射光', fontsize=9, color='gray', style='italic')

    ax2.text(0.3, 0.5, '$\\theta_c$', fontsize=12)
    ax2.text(-1.8, 1.5, '玻璃', fontsize=10)
    ax2.text(-1.8, -1.5, '空气', fontsize=10)
    ax2.axis('off')
    ax2.set_title('全反射', fontsize=12)

    plt.tight_layout()
    save_plot(fig, output_path)

def draw_field_diagram(output_path):
    """电场线/磁场线图"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    # 左图：正点电荷电场线
    x = np.linspace(-3, 3, 15)
    y = np.linspace(-3, 3, 15)
    X, Y = np.meshgrid(x, y)

    # 径向向外
    r = np.sqrt(X**2 + Y**2)
    mask = r < 0.5
    Ex = X / (r**2 + 0.01)
    Ey = Y / (r**2 + 0.01)
    Ex[mask] = 0
    Ey[mask] = 0

    ax1.streamplot(X, Y, Ex, Ey, color='red', linewidth=1, density=1.0)
    circle = Circle((0, 0), 0.3, fill=True, facecolor='red', edgecolor='darkred', lw=2)
    ax1.add_patch(circle)
    ax1.text(0, 0, '+', ha='center', va='center', fontsize=16, color='white')
    ax1.set_xlim(-3, 3)
    ax1.set_ylim(-3, 3)
    ax1.set_aspect('equal')
    ax1.axis('off')
    ax1.set_title('正点电荷电场线', fontsize=12)

    # 右图：匀强磁场
    bx = np.ones((10, 10))
    by = np.zeros((10, 10))
    x2 = np.linspace(-3, 3, 10)
    y2 = np.linspace(-3, 3, 10)
    X2, Y2 = np.meshgrid(x2, y2)

    ax2.quiver(X2, Y2, bx, by, color='blue', scale=20, width=0.03)
    # 画边界
    ax2.plot([-3, 3], [-3, -3], 'b-', lw=2)
    ax2.plot([-3, 3], [3, 3], 'b-', lw=2)
    ax2.text(0, -3.5, '匀强磁场区域', ha='center', fontsize=10, color='blue')
    ax2.set_xlim(-3.5, 3.5)
    ax2.set_ylim(-4, 4)
    ax2.set_aspect('equal')
    ax2.axis('off')
    ax2.set_title('匀强磁场 $B$', fontsize=12)

    plt.tight_layout()
    save_plot(fig, output_path)

def draw_graph_diagram(output_path):
    """数据图 - v-t图、U-I图等"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    # 左图：v-t图 (匀变速)
    t = np.linspace(0, 5, 100)
    v = 2 + 3*t

    ax1.plot(t, v, 'b-', lw=2)
    ax1.scatter([0, 5], [2, 17], color='red', s=50, zorder=5)
    ax1.set_xlabel('$t$/s', fontsize=12)
    ax1.set_ylabel('$v$/ (m·s$^{-1}$)', fontsize=12)
    ax1.set_title('$v-t$ 图像', fontsize=12)
    ax1.grid(True, alpha=0.3)

    # 右图：U-I图
    I = np.array([0, 0.5, 1.0, 1.5, 2.0])
    U = 3 - 0.75*I

    ax2.plot(I, U, 'ro-', lw=2, markersize=6)
    ax2.set_xlabel('$I$/A', fontsize=12)
    ax2.set_ylabel('$U$/V', fontsize=12)
    ax2.set_title('$U-I$ 图像', fontsize=12)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    save_plot(fig, output_path)

def draw_circuit_diagram(output_path):
    """电路示意图（简化版）"""
    fig, ax = setup_plot()
    ax.set_xlim(-2, 6)
    ax.set_ylim(-2, 4)

    # 简单串联电路
    # 电源
    ax.plot([0, 0], [1, 2], 'k-', lw=2)
    ax.plot([-0.3, 0.3], [1.5, 1.5], 'k-', lw=2)
    ax.plot([-0.3, 0.3], [2.5, 2.5], 'k-', lw=2)  # 更多电池极板
    ax.text(-0.8, 2, '$E$', fontsize=12)
    ax.plot([0, 0], [2.5, 3], 'k-', lw=2)
    ax.plot([0, 0], [0, 1], 'k-', lw=2)

    # 导线
    ax.plot([0, 4], [3, 3], 'k-', lw=2)
    ax.plot([0, 4], [0, 0], 'k-', lw=2)

    # 电阻
    ax.plot([4, 4.5], [3, 3], 'k-', lw=2)
    ax.plot([4.5, 5.5], [3, 2.5], 'k-', lw=2)
    ax.plot([5.5, 4.5], [2, 1.5], 'k-', lw=2)
    ax.plot([4.5, 5.5], [1, 0.5], 'k-', lw=2)
    ax.plot([5.5, 4.5], [0, -0.5], 'k-', lw=2)
    ax.plot([4.5, 4], [-0.5, 0], 'k-', lw=2)
    ax.text(5.8, 1.5, '$R$', fontsize=12)

    # 开关
    ax.plot([4, 4], [0, 1], 'k-', lw=2)
    ax.plot([4, 4.5], [1, 1.5], 'k-', lw=2)  # 开关断开

    ax.text(-1, 3.5, '电路图', fontsize=14)
    ax.axis('off')
    save_plot(fig, output_path)


def draw_lc_circuit(output_path):
    """LC振荡电路"""
    fig, ax = setup_plot()
    ax.set_xlim(-2, 6)
    ax.set_ylim(-2, 4)

    # L
    ax.plot([1, 1], [3, 2.5], 'k-', lw=2)
    ax.plot([0.7, 1.3], [2.5, 2.2], 'k-', lw=1.5)
    ax.plot([0.7, 1.3], [2.2, 1.9], 'k-', lw=1.5)
    ax.plot([0.7, 1.3], [1.9, 1.6], 'k-', lw=1.5)
    ax.plot([0.7, 1.3], [1.6, 1.3], 'k-', lw=1.5)
    ax.plot([1, 1], [1.3, 1], 'k-', lw=2)
    ax.text(1, 3.3, '$L$', fontsize=14)

    # C (two plates)
    ax.plot([4, 4], [3, 3.5], 'k-', lw=2)
    ax.plot([4, 4], [0, 1], 'k-', lw=2)
    ax.plot([3.5, 4.5], [3.5, 3.5], 'k-', lw=3)
    ax.plot([3.5, 4.5], [0, 0], 'k-', lw=3)
    ax.text(4, 4, '$C$', fontsize=14)

    # Wires
    ax.plot([1, 4], [3, 3], 'k-', lw=2)
    ax.plot([1, 4], [1, 1], 'k-', lw=2)

    # Current direction arrow
    ax.annotate('', xy=(3, 3), xytext=(2, 3),
                arrowprops=dict(arrowstyle='->', lw=2, color='red'))
    ax.text(2.5, 3.2, '$i$', fontsize=12, color='red')

    ax.set_title('LC振荡电路', fontsize=14)
    ax.axis('off')
    save_plot(fig, output_path)

def draw_spring_oscillator(output_path):
    """弹簧振子"""
    fig, ax = setup_plot()
    ax.set_xlim(-1, 8)
    ax.set_ylim(-1, 3)

    # 墙壁
    ax.fill_between([-0.5, 0], -0.5, 1.5, color='gray', alpha=0.5)
    ax.plot([-0.5, -0.5], [-0.5, 1.5], 'k-', lw=2)

    # 弹簧
    n_coils = 10
    spring_x = np.linspace(0, 4, n_coils*2+1)
    spring_y = np.zeros_like(spring_x)
    for i in range(1, n_coils*2):
        spring_y[i] = 0.3 * (1 if i % 2 == 1 else -1)

    ax.plot(spring_x, spring_y, 'k-', lw=2)

    # 物体
    rect = Rectangle((4, -0.5), 1.5, 1, fill=True, facecolor='lightgreen', edgecolor='green', lw=2)
    ax.add_patch(rect)
    ax.text(4.75, 0, '$m$', ha='center', va='center', fontsize=14)

    # 平衡位置虚线
    ax.plot([0, 7], [0, 0], 'r--', lw=1, alpha=0.7)
    ax.text(6.5, 0.2, '平衡位置', fontsize=10, color='red')

    # 位移箭头
    ax.annotate('', xy=(5.5, -0.8), xytext=(4.75, -0.8),
                arrowprops=dict(arrowstyle='<->', lw=1.5, color='blue'))
    ax.text(5.1, -1.2, '$x$', fontsize=12, color='blue')

    ax.set_title('弹簧振子', fontsize=14)
    ax.axis('off')
    save_plot(fig, output_path)

def draw_charged_particle(output_path):
    """带电粒子在磁场中的圆周运动"""
    fig, ax = setup_plot()

    # 磁场区域 (circle)
    circle = Circle((0, 0), 2.5, fill=True, facecolor='lightblue', alpha=0.2, edgecolor='blue', lw=2)
    ax.add_patch(circle)
    ax.text(-2.2, 2.3, '匀强磁场 $B$', fontsize=12, color='blue')

    # 粒子轨迹 (半圆)
    theta = np.linspace(0, np.pi, 100)
    r = 1.5
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    ax.plot(x, y, 'r-', lw=2.5)

    # 入射方向
    ax.annotate('', xy=(-r, 0), xytext=(-r-1.2, 0),
                arrowprops=dict(arrowstyle='->', lw=2.5, color='red'))
    ax.text(-r-1.5, -0.3, '$v$', fontsize=12, color='red')

    # 出射方向
    ax.annotate('', xy=(r+1.2, 0), xytext=(r, 0),
                arrowprops=dict(arrowstyle='->', lw=2.5, color='red'))
    ax.text(r+1, -0.3, '$v$', fontsize=12, color='red')

    # 圆心
    ax.plot(0, 0, 'k+', markersize=10)
    ax.text(0.1, -0.2, '$O$', fontsize=12)

    # 半径标注
    ax.annotate('', xy=(0, 0), xytext=(r*np.cos(np.pi/4), r*np.sin(np.pi/4)),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='purple', linestyle='dashed'))
    ax.text(0.8, 0.6, '$r$', fontsize=12, color='purple')

    ax.set_xlim(-4, 4)
    ax.set_ylim(-0.5, 3.5)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title('带电粒子在匀强磁场中的圆周运动', fontsize=12)
    save_plot(fig, output_path)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python generate_physics_diagram.py <type> <output_path>")
        print("Types: force, projectile, wave, optics, field, graph, circuit, lc, spring, particle")
        sys.exit(1)

    diagram_type = sys.argv[1]
    output_path = sys.argv[2]

    diagram_map = {
        'force': draw_force_diagram,
        'projectile': draw_projectile_diagram,
        'wave': draw_wave_diagram,
        'optics': draw_optics_diagram,
        'field': draw_field_diagram,
        'graph': draw_graph_diagram,
        'circuit': draw_circuit_diagram,
        'lc': draw_lc_circuit,
        'spring': draw_spring_oscillator,
        'particle': draw_charged_particle,
    }

    if diagram_type in diagram_map:
        diagram_map[diagram_type](output_path)
    else:
        print(f"Unknown diagram type: {diagram_type}")
        print(f"Available: {', '.join(diagram_map.keys())}")
        sys.exit(1)
