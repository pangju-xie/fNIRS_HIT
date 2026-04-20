import math
import os
import sys
import logging
from PyQt5.QtWidgets import QWidget, QMenu, QAction, QApplication
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient, QPolygonF


# 动态将项目根目录加入环境变量，方便独立运行测试
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# 导入底层数据管家
from core.widget_manager.bmap_manager import BrainMapManager

logger = logging.getLogger(__name__)

class BrainLocatorView(QWidget):
    """
    脑电定位响应式绘图组件 (View 层)
    """
    def __init__(self, model: BrainMapManager, parent=None):
        super().__init__(parent)
        self.model = model
        # 只要底层数据变化，立刻触发 paintEvent 重新渲染
        self.model.signal_selection_changed.connect(self.update)
        
        # --- 严谨的色标规范 ---
        self.color_idle = QColor("#bdc3c7")      # 未选中（浅灰）
        self.color_source = QColor("#e74c3c")    # 光源（红色）
        self.color_detector = QColor("#3498db")  # 探测器（蓝色）
        self.color_eeg = QColor("#2ecc71")       # EEG（绿色）
        self.color_text = QColor("#2c3e50")      # 文字颜色：深灰
        
        self.dynamic_line_colors = {} # {(node_A, node_B): "#FF0000"}
        self.dynamic_node_colors = {} # {"Cz": "#00FF00"}
        
        self.is_editable = True 
        
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: white; border: 1px solid #dbe3eb; border-radius: 6px;")

    # ==========================================
    # 对外暴露的上色接口
    # ==========================================
    def set_line_color(self, node1: str, node2: str, hex_color: str):
        """外部调用：设置 fNIRS 连线的颜色"""
        pair = tuple(sorted([node1, node2])) # 排序保证正反都能匹配
        self.dynamic_line_colors[pair] = hex_color

    def set_node_color(self, node_name: str, hex_color: str):
        """外部调用：设置 EEG 节点的颜色"""
        self.dynamic_node_colors[node_name] = hex_color
        
    def clear_colors(self):
        """清空动态颜色，恢复默认样式"""
        self.dynamic_line_colors.clear()
        self.dynamic_node_colors.clear()
        self.update()
    
    
    def _is_main_10_10_node(self, name):
        """精准的 10-10 主干点判断：如果名字里带 H 或者特定的三字母前缀，说明是 10-5 过渡点"""
        name_upper = name.upper()
        if 'H' in name_upper: return False
        for prefix in ['AFP', 'AFF', 'FFC', 'FCC', 'CCP', 'CPP', 'PPO', 'POO']:
            if name_upper.startswith(prefix): return False
        return True

    def paintEvent(self, event): # type: ignore
        """核心渲染循环：每次拉伸窗口都会触发，保证图形 100% 贴合窗口"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        margin = 0.08 
        usable_size = min(w * (1 - 2 * margin), h * (1 - 2 * margin))
        
        # 计算全局缩放比例 (基于可用高度/宽度的一半)
        self.scale = usable_size / 2.0 
        self.offset_x = w / 2.0
        self.offset_y = h / 2.0

        def to_pixel(norm_pos):
            """闭包函数：将 Manager 给的 (-1.0 -> 1.0) 归一化坐标映射为实际像素坐标"""
            return QPointF(self.offset_x + norm_pos[0] * self.scale, 
                           self.offset_y + norm_pos[1] * self.scale)

        # 控制绘制层级 (先画底部的，后画顶部的)
        self._draw_head_and_ears(painter, center=QPointF(self.offset_x, self.offset_y))
        self._draw_fnirs_channels(painter, to_pixel)
        self._draw_nodes(painter, to_pixel)

    def _draw_head_and_ears(self, painter, center):
        """绘制头部大圆、鼻子和耳朵"""
        head_radius = self.scale * 1.0 
        
        # 严格的 Qt 枚举：画笔和画刷
        pen = QPen(self.color_idle, 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # 画头壳圆
        painter.drawEllipse(center, head_radius, head_radius)
        
        # 画鼻子 (正上方三角形)
        nose_top = QPointF(center.x(), center.y() - head_radius - self.scale * 0.15)
        nose_left = QPointF(center.x() - head_radius * 0.12, center.y() - head_radius)
        nose_right = QPointF(center.x() + head_radius * 0.12, center.y() - head_radius)
        painter.drawPolyline(QPolygonF([nose_left, nose_top, nose_right]))
        
        # 画左右耳朵 (椭圆)
        ear_w = self.scale * 0.12
        ear_h = self.scale * 0.35
        left_ear_rect = QRectF(center.x() - head_radius - ear_w / 2.0, center.y() - ear_h / 2.0, ear_w, ear_h)
        painter.drawEllipse(left_ear_rect)
        right_ear_rect = QRectF(center.x() + head_radius - ear_w / 2.0, center.y() - ear_h / 2.0, ear_w, ear_h)
        painter.drawEllipse(right_ear_rect)

    def _draw_fnirs_channels(self, painter, to_pixel):
        """绘制红蓝之间渐变的近红外连线"""
        for src_name, det_name in self.model.valid_channels:
            p1 = to_pixel(self.model.all_nodes[src_name])
            p2 = to_pixel(self.model.all_nodes[det_name])
            
            pair_key = tuple(sorted([src_name, det_name]))
            if pair_key in self.dynamic_line_colors:
                # 处于测试状态：使用信号计算出的红/黄/绿纯色实线
                dyn_color = QColor(self.dynamic_line_colors[pair_key])
                pen = QPen(dyn_color, 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            else:
                # 处于待机状态：原版漂亮的浅红至浅蓝渐变色保留不变
                gradient = QLinearGradient(p1, p2)
                gradient.setColorAt(0.0, QColor("#ff9a9e")) 
                gradient.setColorAt(1.0, QColor("#fecfef")) 
                pen = QPen(QBrush(gradient), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            
            painter.setPen(pen)
            painter.drawLine(p1, p2)

    def _draw_centered_text(self, painter, pixel_pos, text, font, color):
        """纯数学绝对居中绘制文字引擎"""
        painter.setFont(font)
        painter.setPen(color)
        fm = painter.fontMetrics()
        
        # 获取文字的准确宽度和绝对高度(capHeight 避免下划线偏移)
        w = fm.horizontalAdvance(text) if hasattr(fm, 'horizontalAdvance') else fm.width(text)
        h = fm.capHeight() if hasattr(fm, 'capHeight') else fm.ascent()
        
        # 将绘制原点移动到文字的左下角基线
        draw_x = pixel_pos.x() - w / 2.0
        draw_y = pixel_pos.y() + h / 2.0 
        painter.drawText(QPointF(draw_x, draw_y), text)

    def _draw_nodes(self, painter, to_pixel):
        """分层绘制未选中(灰)和已选中(彩色)的电极点"""
        unselected, selected = [], []
        for name, norm_pos in self.model.all_nodes.items():
            state = self.model.selected_states.get(name, 'None')
            if state == 'None': unselected.append((name, norm_pos))
            else: selected.append((name, norm_pos, state))

        # 1. 画没选中的点 (作为背景底图)
        for name, norm_pos in unselected:
            pixel_pos = to_pixel(norm_pos)
            is_main_node = self._is_main_10_10_node(name)
            
            if is_main_node: 
                # 主干点 (大、实心、带浅字)
                radius = self.scale * 0.04
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self.color_idle)
                painter.drawEllipse(pixel_pos, radius, radius)
                
                font_size = max(5, int(radius * 0.55))
                font = QFont("Segoe UI", font_size, QFont.Bold)
                self._draw_centered_text(painter, pixel_pos, name, font, QColor("#7f8c8d"))
            else:
                # 过渡点 (小、虚线、空心、无字)
                radius = self.scale * 0.02
                painter.setPen(QPen(self.color_idle, 1, Qt.PenStyle.SolidLine))
                painter.setBrush(QColor("white"))
                painter.drawEllipse(pixel_pos, radius, radius)

        # 2. 画已选中的点 (彩色高亮，覆盖在最上面)
        for name, norm_pos, state in selected:
            pixel_pos = to_pixel(norm_pos)
            is_main_node = self._is_main_10_10_node(name)
            
            # 主节点生成的彩色圆圈略大，次要点略小，保持主次分明
            radius = self.scale * 0.045 if is_main_node else self.scale * 0.03
            
            if state == 'Source': color = self.color_source
            elif state == 'Detector': color = self.color_detector
            elif state == 'EEG': 
                if name in self.dynamic_node_colors:
                    color = QColor(self.dynamic_node_colors[name])
                else:
                    color = self.color_eeg
            else: color = self.color_idle
            
            painter.setBrush(color)
            painter.setPen(QPen(QColor("white"), 2))
            painter.drawEllipse(pixel_pos, radius, radius)
            
            # 获取引擎生成的别名并绘制
            display_name = self.model.node_aliases.get(name, name)
            font_size = max(6, int(radius * 0.6)) 
            font = QFont("Segoe UI", font_size, QFont.Bold)
            self._draw_centered_text(painter, pixel_pos, display_name, font, QColor("white"))

    def mousePressEvent(self, event): # type: ignore
        """鼠标响应事件：捕捉点击，转换为坐标，寻找目标"""
        if not self.is_editable: return
        pos = event.pos()
        
        # 将屏幕像素坐标反算回归一化坐标 (-1.0 -> 1.0)
        norm_x = (pos.x() - self.offset_x) / self.scale
        norm_y = (pos.y() - self.offset_y) / self.scale 
        
        # 检测是否点中了某个电极 (使用距离阈值，无需方框碰撞检测)
        clicked_node = None
        min_dist = 0.05 # 可容忍的误差距离
        for name, n_pos in self.model.all_nodes.items():
            dist = math.hypot(norm_x - n_pos[0], norm_y - n_pos[1])
            if dist < min_dist:
                clicked_node = name
                break
                
        if not clicked_node: return

        # 严格的 Qt 枚举：鼠标按键判定
        if event.button() == Qt.MouseButton.LeftButton:
            # 极速轮换：红 -> 蓝 -> 绿 -> 灰
            self.model.cycle_node_state(clicked_node)
            
        elif event.button() == Qt.MouseButton.RightButton:
            # 弹出精准操控菜单
            menu = QMenu(self)
            menu.setStyleSheet("QMenu { background-color: white; border: 1px solid #ccc; font-size: 14px; }")
            
            for text, state in [('设为光源 (S)', 'Source'), ('设为探测器 (D)', 'Detector'), 
                                ('设为脑电 (E)', 'EEG'), ('取消选择 (Clear)', 'None')]:
                action = QAction(text, self)
                action.triggered.connect(lambda checked, s=state: self.model.set_node_state(clicked_node, s))
                menu.addAction(action)
                
            # 附加功能：通道的断开与重连
            current_state = self.model.selected_states.get(clicked_node)
            if current_state in ['Source', 'Detector']:
                menu.addSeparator()
                my_alias = self.model.node_aliases.get(clicked_node)
                target_state = 'Detector' if current_state == 'Source' else 'Source'
                
                # 寻找周边可以连接的相反电极
                targets = [n for n, s in self.model.selected_states.items() if s == target_state]
                for t in targets:
                    t_alias = self.model.node_aliases[t]
                    if math.hypot(self.model.all_nodes[clicked_node][0]-self.model.all_nodes[t][0], 
                                  self.model.all_nodes[clicked_node][1]-self.model.all_nodes[t][1]) <= self.model.channel_distance_threshold:
                        
                        is_blacklisted = (my_alias, t_alias) in self.model.blacklisted_channels or \
                                         (t_alias, my_alias) in self.model.blacklisted_channels
                        
                        if not is_blacklisted:
                            action = QAction(f"❌ 断开与 {t_alias} 的连线", self)
                            action.triggered.connect(lambda checked, a1=my_alias, a2=t_alias: 
                                                     self.model.toggle_channel_blacklist(a1, a2, True)) # type: ignore
                        else:
                            action = QAction(f"🔗 恢复与 {t_alias} 的连线", self)
                            action.triggered.connect(lambda checked, a1=my_alias, a2=t_alias: 
                                                     self.model.toggle_channel_blacklist(a1, a2, False)) # type: ignore
                        menu.addAction(action)

            menu.exec_(event.globalPos())

# ==========================================
# 独立测试台 (右键直接运行该文件时生效)
# ==========================================
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QLabel
    
    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("NeuroSync - 纯平面二维脑电拓扑系统")
            self.resize(1000, 800)
            self.setStyleSheet("background-color: #f7f9fc;")
            self.brain_model = BrainMapManager()
            self.brain_view = BrainLocatorView(self.brain_model)
            
            title = QLabel("💡 极致完美版：彻底解决枚举报错，代码严格规范化，方圆算法极度平滑。")
            title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
            
            central = QWidget()
            layout = QVBoxLayout(central)
            layout.addWidget(title)
            layout.addWidget(self.brain_view, stretch=1)
            self.setCentralWidget(central)

    # 严格枚举：高分屏适配
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    win = TestWindow()
    win.show()
    sys.exit(app.exec_())