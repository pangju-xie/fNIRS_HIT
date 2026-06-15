import math
import os
import sys
import logging

from PyQt5.QtWidgets import QWidget, QMenu, QAction, QApplication
from PyQt5.QtCore import Qt, QPointF, QRectF, QPoint
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient, QPolygonF

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from core.widget_manager.bmap_manager import BrainMapManager

logger = logging.getLogger(__name__)


class BrainLocatorView(QWidget):
    def __init__(self, model: BrainMapManager, parent=None, quality_view_mode=False):
        super().__init__(parent)
        self.model = model
        self.quality_view_mode = quality_view_mode
        self.model.signal_selection_changed.connect(self.update)

        self.color_idle = QColor("#bcc3ca")
        self.color_source = QColor("#e74c3c")
        self.color_detector = QColor("#3498db")
        self.color_eeg = QColor("#2ecc71")
        self.color_ref = QColor("#f39c12")
        self.color_gnd = QColor("#8e44ad")
        self.color_fnirs_channel = QColor("#7b3ff2")
        self.color_text = QColor("#6d7278")
        self.color_outline = QColor("#707070")

        self.dynamic_line_colors = {}
        self.dynamic_node_colors = {}
        self.is_editable = True

        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom_factor = 1.0
        self.min_zoom_factor = 0.6
        self.max_zoom_factor = 3.0
        self.pan_offset = QPointF(0.0, 0.0)
        self._right_press_pos = None
        self._pan_anchor = None
        self._right_dragging = False

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: white; border: 1px solid #dbe3eb; border-radius: 6px;")

    def _with_alpha(self, color, alpha):
        qcolor = QColor(color)
        qcolor.setAlpha(alpha)
        return qcolor

    def set_line_color(self, node1: str, node2: str, hex_color: str):
        self.dynamic_line_colors[tuple(sorted([node1, node2]))] = hex_color

    def set_node_color(self, node_name: str, hex_color: str):
        self.dynamic_node_colors[node_name] = hex_color

    def clear_colors(self):
        self.dynamic_line_colors.clear()
        self.dynamic_node_colors.clear()
        self.update()

    def paintEvent(self, event):  # type: ignore
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        margin = 0.08
        usable_size = min(w * (1 - 2 * margin), h * (1 - 2 * margin))
        self.scale = (usable_size / 2.0) * self.zoom_factor
        self.offset_x = w / 2.0 + self.pan_offset.x()
        self.offset_y = h / 2.0 + self.pan_offset.y()

        def to_pixel(norm_pos):
            return QPointF(self.offset_x + norm_pos[0] * self.scale, self.offset_y + norm_pos[1] * self.scale)

        self._draw_head_and_features(painter)
        self._draw_guide_shapes(painter, to_pixel)
        self._draw_fnirs_channels(painter, to_pixel)
        self._draw_nodes(painter, to_pixel)

    def _draw_head_and_features(self, painter):
        center = QPointF(self.offset_x, self.offset_y)
        head_radius = self.scale * 0.98
        painter.setPen(QPen(self.color_outline, 1.4, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        nose_top = QPointF(center.x(), center.y() - head_radius - self.scale * 0.18)
        nose_left = QPointF(center.x() - head_radius * 0.13, center.y() - head_radius * 0.99)
        nose_right = QPointF(center.x() + head_radius * 0.13, center.y() - head_radius * 0.99)
        painter.drawPolyline(QPolygonF([nose_left, nose_top, nose_right]))

        ear_w = self.scale * 0.14
        ear_h = self.scale * 0.42
        painter.drawEllipse(QRectF(center.x() - head_radius - ear_w * 0.6, center.y() - ear_h / 2.0, ear_w, ear_h))
        painter.drawEllipse(QRectF(center.x() + head_radius - ear_w * 0.4, center.y() - ear_h / 2.0, ear_w, ear_h))

    def _draw_guide_shapes(self, painter, to_pixel):
        for shape in self.model.guide_shapes:
            style = Qt.PenStyle.DashLine if shape["style"] == "dashed" else Qt.PenStyle.SolidLine
            painter.setPen(QPen(QColor(shape["color"]), shape["width"], style, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            if shape["type"] == "circle":
                center = to_pixel(shape["center"])
                radius = self.scale * shape["radius"]
                painter.drawEllipse(center, radius, radius)
                continue

            points = [to_pixel(point) for point in shape["points"]]
            if not points:
                continue
            polygon = QPolygonF(points)
            if shape["closed"]:
                painter.drawPolygon(polygon)
            else:
                painter.drawPolyline(polygon)

    def _draw_fnirs_channels(self, painter, to_pixel):
        for src_name, det_name in self.model.valid_channels:
            p1 = to_pixel(self.model.all_nodes[src_name])
            p2 = to_pixel(self.model.all_nodes[det_name])
            pair_key = tuple(sorted([src_name, det_name]))
            color = self.dynamic_line_colors.get(pair_key)
            if color:
                pen = QPen(QColor(color), 4.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            else:
                pen = QPen(QColor(self.color_fnirs_channel), 4.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(p1, p2)

    def _draw_centered_text(self, painter, pixel_pos, text, font, color):
        painter.setFont(font)
        painter.setPen(color)
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(text) if hasattr(metrics, "horizontalAdvance") else metrics.width(text)
        height = metrics.capHeight() if hasattr(metrics, "capHeight") else metrics.ascent()
        painter.drawText(QPointF(pixel_pos.x() - width / 2.0, pixel_pos.y() + height / 2.0), text)

    def _alias_number(self, node_name):
        alias = self.model.node_aliases.get(node_name, "")
        digits = "".join(ch for ch in alias if ch.isdigit())
        return digits

    def _state_label(self, state):
        labels = {
            "Source": "设为光源 (S)",
            "Detector": "设为探测器 (D)",
            "EEG": "设为脑电 (E)",
            "Ref": "设为参考 (REF)",
            "GND": "设为接地 (GND)",
            "None": "取消选择",
        }
        return labels.get(state, state)

    def _draw_nodes(self, painter, to_pixel):
        unselected = []
        selected = []
        for name, norm_pos in self.model.all_nodes.items():
            state = self.model.selected_states.get(name, "None")
            if state == "None":
                unselected.append((name, norm_pos))
            else:
                selected.append((name, norm_pos, state))

        unselected.sort(key=lambda item: self.model.node_meta[item[0]]["display_priority"])
        selected.sort(key=lambda item: self.model.node_meta[item[0]]["display_priority"])

        for name, norm_pos in unselected:
            meta = self.model.node_meta[name]
            pixel_pos = to_pixel(norm_pos)
            radius = self.scale * meta["radius"]
            painter.setPen(QPen(self.color_idle, 1.35 if meta["kind"] == "named" else 1.0, Qt.PenStyle.SolidLine))
            painter.setBrush(QColor("white"))
            painter.drawEllipse(pixel_pos, radius, radius)
            if meta["label"]:
                font = QFont("Segoe UI", max(7, int(radius * 0.62)), QFont.Weight.Normal)
                self._draw_centered_text(painter, pixel_pos, meta["label"], font, self.color_text)

        for name, norm_pos, state in selected:
            meta = self.model.node_meta[name]
            pixel_pos = to_pixel(norm_pos)
            radius = self.scale * meta.get("selected_radius", meta["radius"])
            if state == "Source":
                color = self._with_alpha(self.color_source, 165) if self.quality_view_mode else self.color_source
            elif state == "Detector":
                color = self._with_alpha(self.color_detector, 165) if self.quality_view_mode else self.color_detector
            elif state == "Ref":
                color = self.color_ref
            elif state == "GND":
                color = self.color_gnd
            elif name in self.dynamic_node_colors:
                color = QColor(self.dynamic_node_colors[name])
            else:
                color = self.color_eeg
            painter.setPen(QPen(QColor("white"), 1.5))
            painter.setBrush(color)
            painter.drawEllipse(pixel_pos, radius, radius)
            if state == "Ref":
                display_name = "REF"
            elif state == "GND":
                display_name = "GND"
            else:
                display_name = self.model.node_meta.get(name, {}).get("standard_name") or self.model.node_meta.get(name, {}).get("label", name)
            if display_name:
                title_font = QFont("Segoe UI", max(5, int(radius * (0.58 if len(display_name) <= 3 else 0.34))), QFont.Weight.Bold)
                title_pos = QPointF(pixel_pos.x(), pixel_pos.y() - radius * 0.12)
                self._draw_centered_text(painter, title_pos, display_name, title_font, QColor("white"))

                number_text = self._alias_number(name)
                if number_text and state not in {"Ref", "GND"}:
                    hint_font = QFont("Segoe UI", max(4, int(radius * 0.38)), QFont.Weight.Bold)
                    hint_pos = QPointF(pixel_pos.x(), pixel_pos.y() + radius * 0.62)
                    self._draw_centered_text(painter, hint_pos, number_text, hint_font, QColor("white"))

    def mousePressEvent(self, event):  # type: ignore
        if not self.is_editable:
            return

        if event.button() == Qt.MouseButton.RightButton:
            self._right_press_pos = QPoint(event.pos())
            self._pan_anchor = QPointF(self.pan_offset)
            self._right_dragging = False
            event.accept()
            return

        norm_x = (event.pos().x() - self.offset_x) / self.scale
        norm_y = (event.pos().y() - self.offset_y) / self.scale
        clicked_node = None
        best_distance = None
        for name, node_pos in self.model.all_nodes.items():
            radius = self.model.node_meta.get(name, {}).get("radius", 0.03)
            selected_radius = self.model.node_meta.get(name, {}).get("selected_radius", radius)
            tolerance = max(selected_radius * 1.35, 0.018)
            distance = math.hypot(norm_x - node_pos[0], norm_y - node_pos[1])
            if distance <= tolerance and (best_distance is None or distance < best_distance):
                clicked_node = name
                best_distance = distance
        if not clicked_node:
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self.model.cycle_node_state(clicked_node)
            return

        if event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            menu.setStyleSheet("QMenu { background-color: white; border: 1px solid #ccc; font-size: 14px; }")
            capabilities = self.model.node_meta.get(clicked_node, {}).get("state_capabilities", ["Source", "Detector", "EEG"])
            state_labels = {
                "Source": "设为光源 (S)",
                "Detector": "设为探测器 (D)",
                "EEG": "设为脑电 (E)",
                "Ref": "设为参考 (REF)",
                "GND": "设为接地 (GND)",
                "None": "取消选择",
            }
            for state in capabilities + ["None"]:
                action = QAction(self._state_label(state), self)
                action.triggered.connect(lambda checked, s=state: self.model.set_node_state(clicked_node, s))
                menu.addAction(action)

            current_state = self.model.selected_states.get(clicked_node)
            if current_state in ["Source", "Detector"]:
                menu.addSeparator()
                my_alias = self.model.node_aliases.get(clicked_node)
                target_state = "Detector" if current_state == "Source" else "Source"
                targets = [name for name, state in self.model.selected_states.items() if state == target_state]
                for target in targets:
                    target_alias = self.model.node_aliases[target]
                    p1 = self.model.all_nodes[clicked_node]
                    p2 = self.model.all_nodes[target]
                    if math.hypot(p1[0] - p2[0], p1[1] - p2[1]) > self.model.channel_distance_threshold:
                        continue
                    is_blacklisted = (
                        (my_alias, target_alias) in self.model.blacklisted_channels
                        or (target_alias, my_alias) in self.model.blacklisted_channels
                    )
                    if is_blacklisted:
                        action = QAction(f"恢复与 {target_alias} 的连线", self)
                        action.triggered.connect(lambda checked, a1=my_alias, a2=target_alias: self.model.toggle_channel_blacklist(a1, a2, False))
                    else:
                        action = QAction(f"断开与 {target_alias} 的连线", self)
                        action.triggered.connect(lambda checked, a1=my_alias, a2=target_alias: self.model.toggle_channel_blacklist(a1, a2, True))
                    menu.addAction(action)

            menu.exec_(event.globalPos())

    def mouseMoveEvent(self, event):  # type: ignore
        if self._right_press_pos is not None and (event.buttons() & Qt.MouseButton.RightButton):
            delta = event.pos() - self._right_press_pos
            if self._pan_anchor is not None:
                if not self._right_dragging and (abs(delta.x()) > 3 or abs(delta.y()) > 3):
                    self._right_dragging = True
                self.pan_offset = QPointF(self._pan_anchor.x() + delta.x(), self._pan_anchor.y() + delta.y())
                self.update()
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # type: ignore
        if event.button() == Qt.MouseButton.RightButton and self._right_press_pos is not None:
            was_dragging = self._right_dragging
            self._right_press_pos = None
            self._pan_anchor = None
            self._right_dragging = False
            if was_dragging:
                event.accept()
                return
            self._open_context_menu(event)
            return
        super().mouseReleaseEvent(event)

    def _open_context_menu(self, event):
        norm_x = (event.pos().x() - self.offset_x) / self.scale
        norm_y = (event.pos().y() - self.offset_y) / self.scale

        clicked_node = None
        best_distance = None
        for name, node_pos in self.model.all_nodes.items():
            radius = self.model.node_meta.get(name, {}).get("radius", 0.03)
            selected_radius = self.model.node_meta.get(name, {}).get("selected_radius", radius)
            tolerance = max(selected_radius * 1.35, 0.018)
            distance = math.hypot(norm_x - node_pos[0], norm_y - node_pos[1])
            if distance <= tolerance and (best_distance is None or distance < best_distance):
                clicked_node = name
                best_distance = distance
        if not clicked_node:
            return

        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: white; border: 1px solid #ccc; font-size: 14px; }")
        capabilities = self.model.node_meta.get(clicked_node, {}).get("state_capabilities", ["Source", "Detector", "EEG"])
        state_labels = {
            "Source": "设为光源 (S)",
            "Detector": "设为探测器 (D)",
            "EEG": "设为脑电 (E)",
            "Ref": "设为参考 (REF)",
            "GND": "设为接地 (GND)",
            "None": "取消选择",
        }
        for state in capabilities + ["None"]:
            action = QAction(self._state_label(state), self)
            action.triggered.connect(lambda checked, s=state: self.model.set_node_state(clicked_node, s))
            menu.addAction(action)

        current_state = self.model.selected_states.get(clicked_node)
        if current_state in ["Source", "Detector"]:
            menu.addSeparator()
            my_alias = self.model.node_aliases.get(clicked_node)
            target_state = "Detector" if current_state == "Source" else "Source"
            targets = [name for name, state in self.model.selected_states.items() if state == target_state]
            for target in targets:
                target_alias = self.model.node_aliases[target]
                p1 = self.model.all_nodes[clicked_node]
                p2 = self.model.all_nodes[target]
                if math.hypot(p1[0] - p2[0], p1[1] - p2[1]) > self.model.channel_distance_threshold:
                    continue
                is_blacklisted = (
                    (my_alias, target_alias) in self.model.blacklisted_channels
                    or (target_alias, my_alias) in self.model.blacklisted_channels
                )
                if is_blacklisted:
                    action = QAction(f"恢复与 {target_alias} 的连线", self)
                    action.triggered.connect(lambda checked, a1=my_alias, a2=target_alias: self.model.toggle_channel_blacklist(a1, a2, False))
                else:
                    action = QAction(f"断开与 {target_alias} 的连线", self)
                    action.triggered.connect(lambda checked, a1=my_alias, a2=target_alias: self.model.toggle_channel_blacklist(a1, a2, True))
                menu.addAction(action)

        menu.exec_(event.globalPos())

    def wheelEvent(self, event):  # type: ignore
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return

        zoom_step = 1.12 if delta > 0 else (1.0 / 1.12)
        new_zoom = self.zoom_factor * zoom_step
        self.zoom_factor = max(self.min_zoom_factor, min(self.max_zoom_factor, new_zoom))
        self.update()
        event.accept()


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QLabel

    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("NeuroSync - 脑图布局预览")
            self.resize(1000, 800)
            self.setStyleSheet("background-color: #f7f9fc;")
            self.brain_model = BrainMapManager()
            self.brain_view = BrainLocatorView(self.brain_model)

            title = QLabel("脑图布局预览")
            title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")

            central = QWidget()
            layout = QVBoxLayout(central)
            layout.addWidget(title)
            layout.addWidget(self.brain_view, stretch=1)
            self.setCentralWidget(central)

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    win = TestWindow()
    win.show()
    sys.exit(app.exec_())
