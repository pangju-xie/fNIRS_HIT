import math
import logging

import mne
from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class BrainMapManager(QObject):
    signal_selection_changed = pyqtSignal()
    signal_warning = pyqtSignal(str)

    OUTER_RADIUS = 150.0
    INNER_RADIUS = 120.0
    BIG_NODE_RADIUS = 6.0
    SMALL_NODE_RADIUS = 1.5
    SELECTED_NODE_RADIUS = 7.0
    AUX_MERGE_DISTANCE = 4.0

    def __init__(self):
        super().__init__()
        self.all_nodes = {}
        self.node_meta = {}
        self.guide_nodes = {}
        self.guide_shapes = []
        self.arc_meta = {}
        self.standard_positions_3d = {}
        self.standard_channel_names = []
        self.legacy_name_map = {}
        self.selected_states = {}
        self.node_aliases = {}
        self.valid_channels = []
        self.blacklisted_channels = set()
        self.channel_distance_threshold = 0.24
        self.limits = {"EEG": 32, "Source": 16, "Detector": 16, "EMG": 16}
        self._load_standard_1005_metadata()
        self._build_reference_layout()

    # -------------------------------------------------------------
    # Standard metadata
    # -------------------------------------------------------------
    def _load_standard_1005_metadata(self):
        montage = mne.channels.make_standard_montage("standard_1005")
        self.standard_channel_names = list(montage.ch_names)
        positions = montage.get_positions()
        self.standard_positions_3d = {
            name: tuple(float(value) for value in coord)
            for name, coord in positions["ch_pos"].items()
        }
        self.standard_positions_3d["Nasion"] = tuple(float(value) for value in positions["nasion"])
        self.standard_positions_3d["LPA"] = tuple(float(value) for value in positions["lpa"])
        self.standard_positions_3d["RPA"] = tuple(float(value) for value in positions["rpa"])
        self.legacy_name_map = {
            "Nz": "Nasion",
            "FP1": "Fp1",
            "FP2": "Fp2",
            "FPz": "Fpz",
        }

    def resolve_node_name(self, node_name: str) -> str:
        return self.legacy_name_map.get(node_name, node_name)

    def _state_capabilities_for_node(self, standard_name: str):
        if standard_name in {"Nasion", "LPA", "RPA"}:
            return ["Ref"]
        if standard_name.endswith("z"):
            return ["Source", "Detector", "EEG", "Ref", "GND"]
        return ["Source", "Detector", "EEG"]

    # -------------------------------------------------------------
    # Layout generation
    # -------------------------------------------------------------
    def _build_reference_layout(self):
        self.all_nodes.clear()
        self.node_meta.clear()
        self.guide_nodes.clear()
        self.guide_shapes.clear()
        self.arc_meta.clear()

        raw_nodes = {}
        outer_sequence = [
            "Nasion", "RS1", "AF9", "F9", "FT9", "LPA", "TP9", "P9", "PO9", "I1",
            "Iz", "I2", "PO10", "P10", "TP10", "RPA", "FT10", "F10", "AF10", "RS2",
        ]
        inner_sequence = [
            "Fpz", "Fp1", "AF7", "F7", "FT7", "T7", "TP7", "P7", "PO7", "O1",
            "Oz", "O2", "PO8", "P8", "TP8", "T8", "FT8", "F8", "AF8", "Fp2",
        ]

        raw_nodes.update(self._equidistant_circle_points((0.0, 0.0), self.OUTER_RADIUS, outer_sequence, 90.0))
        raw_nodes.update(self._equidistant_circle_points((0.0, 0.0), self.INNER_RADIUS, inner_sequence, 90.0))

        x_axis_nodes = ["LPA", "T7", "C5", "C3", "C1", "Cz", "C2", "C4", "C6", "T8", "RPA"]
        for index, name in enumerate(x_axis_nodes):
            raw_nodes[name] = (-self.OUTER_RADIUS + index * 30.0, 0.0)

        y_axis_nodes = ["Nasion", "Fpz", "AFz", "Fz", "FCz", "Cz", "CPz", "Pz", "POz", "Oz", "Iz"]
        for index, name in enumerate(y_axis_nodes):
            raw_nodes[name] = (0.0, -self.OUTER_RADIUS + index * 30.0)

        row_specs = [
            ("arc_af", ["AF7", "AF5", "AF3", "AF1", "AFz", "AF2", "AF4", "AF6", "AF8"], "AF7", "AFz", "AF8"),
            ("arc_f", ["F7", "F5", "F3", "F1", "Fz", "F2", "F4", "F6", "F8"], "F7", "Fz", "F8"),
            ("arc_fc", ["FT7", "FC5", "FC3", "FC1", "FCz", "FC2", "FC4", "FC6", "FT8"], "FT7", "FCz", "FT8"),
            ("arc_cp", ["TP7", "CP5", "CP3", "CP1", "CPz", "CP2", "CP4", "CP6", "TP8"], "TP7", "CPz", "TP8"),
            ("arc_p", ["P7", "P5", "P3", "P1", "Pz", "P2", "P4", "P6", "P8"], "P7", "Pz", "P8"),
            ("arc_po", ["PO7", "PO5", "PO3", "PO1", "POz", "PO2", "PO4", "PO6", "PO8"], "PO7", "POz", "PO8"),
        ]
        for arc_id, names, left, middle, right in row_specs:
            points = self._points_on_arc(raw_nodes[left], raw_nodes[middle], raw_nodes[right], len(names))
            for name, point in zip(names, points):
                raw_nodes[name] = point
            self._register_arc(arc_id, names, raw_nodes, left, middle, right)

        self._register_arc("arc_outer_top", ["AF9", "Nasion", "AF10"], raw_nodes, "AF9", "Nasion", "AF10")
        self._register_arc("arc_fp", ["Fp1", "Fpz", "Fp2"], raw_nodes, "Fp1", "Fpz", "Fp2")
        self._register_arc("arc_inner_circle_top", ["AF7", "Fp1", "Fpz", "Fp2", "AF8"], raw_nodes, "AF7", "Fpz", "AF8")
        self._register_arc("arc_o", ["O1", "Oz", "O2"], raw_nodes, "O1", "Oz", "O2")
        self._register_circle("circle_outer", outer_sequence, raw_nodes, (0.0, 0.0), self.OUTER_RADIUS)
        self._register_circle("circle_inner", inner_sequence, raw_nodes, (0.0, 0.0), self.INNER_RADIUS)
        self._register_arc(
            "arc_outer_band",
            ["AF9", "F9", "FT9", "LPA", "TP9", "P9", "PO9", "I1", "Iz", "I2", "PO10", "P10", "TP10", "RPA", "FT10", "F10", "AF10"],
            raw_nodes,
            "AF9",
            "Iz",
            "AF10",
        )
        self._register_arc(
            "arc_inner_band",
            ["AF7", "F7", "FT7", "T7", "TP7", "P7", "PO7", "O1", "Oz", "O2", "PO8", "P8", "TP8", "T8", "FT8", "F8", "AF8"],
            raw_nodes,
            "AF7",
            "Oz",
            "AF8",
        )
        self._register_line("line_c", ["T7", "C5", "C3", "C1", "Cz", "C2", "C4", "C6", "T8"], raw_nodes)

        self._add_named_nodes(raw_nodes)
        self._build_guide_shapes(raw_nodes)
        self._add_auxiliary_nodes(raw_nodes)
        self._assign_aux_standard_names()

    def _add_named_nodes(self, raw_nodes):
        named_nodes = set(raw_nodes.keys()) - {"RS1", "RS2"}
        for name in sorted(named_nodes):
            self._register_node(name, raw_nodes[name], self.BIG_NODE_RADIUS, kind="named", label=name)

    def _build_guide_shapes(self, raw_nodes):
        dashed = {"color": "#b7bdc4", "style": "dashed", "width": 1.4}
        solid = {"color": "#707070", "style": "solid", "width": 1.8}

        self._add_guide_circle((0.0, 0.0), self.INNER_RADIUS, dashed)
        self._add_guide_shape("polyline", [raw_nodes["Nasion"], raw_nodes["Cz"], raw_nodes["Iz"]], dashed)
        self._add_guide_shape("polyline", [raw_nodes["LPA"], raw_nodes["Cz"], raw_nodes["RPA"]], dashed)
        for arc_id in ["arc_af", "arc_f", "arc_fc", "arc_cp", "arc_p", "arc_po"]:
            self._add_guide_shape("polyline", self._sample_arc_points(arc_id, 64), dashed)
        self._add_guide_circle((0.0, 0.0), self.OUTER_RADIUS, solid)

    def _add_auxiliary_nodes(self, raw_nodes):
        aux_points = []

        adjacent_arc_ids = ["arc_af", "arc_f", "arc_fc", "line_c", "arc_cp", "arc_p", "arc_po"]
        for arc_id in adjacent_arc_ids:
            node_names = self.arc_meta[arc_id]["node_names"]
            for index in range(len(node_names) - 1):
                aux_points.append((f"AUX_ARC_{arc_id.upper()}", self._arc_midpoint_by_names(node_names[index], node_names[index + 1], arc_id)))

        inner_names = self.arc_meta["circle_inner"]["node_names"]
        for index in range(len(inner_names)):
            aux_points.append(
                (
                    "AUX_CIRCLE_INNER",
                    self._arc_midpoint_by_names(inner_names[index], inner_names[(index + 1) % len(inner_names)], "circle_inner"),
                )
            )

        outer_names = self.arc_meta["circle_outer"]["node_names"]
        skipped_outer_segments = {
            frozenset(("Nasion", "RS1")),
            frozenset(("RS1", "AF9")),
            frozenset(("Nasion", "RS2")),
            frozenset(("RS2", "AF10")),
        }
        for index in range(len(outer_names)):
            left = outer_names[index]
            right = outer_names[(index + 1) % len(outer_names)]
            if frozenset((left, right)) in skipped_outer_segments:
                continue
            aux_points.append(("AUX_CIRCLE_OUTER", self._arc_midpoint_by_names(left, right, "circle_outer")))

        core_rows = [
            ["AF7", "AF5", "AF3", "AF1", "AFz", "AF2", "AF4", "AF6", "AF8"],
            ["F7", "F5", "F3", "F1", "Fz", "F2", "F4", "F6", "F8"],
            ["FT7", "FC5", "FC3", "FC1", "FCz", "FC2", "FC4", "FC6", "FT8"],
            ["T7", "C5", "C3", "C1", "Cz", "C2", "C4", "C6", "T8"],
            ["TP7", "CP5", "CP3", "CP1", "CPz", "CP2", "CP4", "CP6", "TP8"],
            ["P7", "P5", "P3", "P1", "Pz", "P2", "P4", "P6", "P8"],
            ["PO7", "PO5", "PO3", "PO1", "POz", "PO2", "PO4", "PO6", "PO8"],
        ]
        aux_points.extend(self._pairwise_midpoints(core_rows, raw_nodes, "AUX_GRID_MID"))
        aux_points.extend(self._quad_centers(core_rows, raw_nodes, "AUX_GRID_QUAD"))

        outer_band = self.arc_meta["arc_outer_band"]["node_names"]
        inner_band = self.arc_meta["arc_inner_band"]["node_names"]
        for outer_name, inner_name in zip(outer_band, inner_band):
            aux_points.append(("AUX_RING_MID", self._midpoint(raw_nodes[outer_name], raw_nodes[inner_name])))
        for index in range(len(outer_band) - 1):
            quad_names = (outer_band[index], outer_band[index + 1], inner_band[index + 1], inner_band[index])
            aux_points.append(("AUX_RING_QUAD", self._quad_center_from_names(quad_names, raw_nodes)))

        frontal_left = self._arc_midpoint_by_names("AF7", "Fp1", "arc_inner_circle_top")
        frontal_right = self._arc_midpoint_by_names("Fp2", "AF8", "arc_inner_circle_top")
        frontal_mid = self._midpoint(raw_nodes["AFz"], raw_nodes["Fpz"])
        for point in self._points_on_arc(frontal_left, frontal_mid, frontal_right, 7):
            aux_points.append(("AUX_FRONT_CAP", point))

        occipital_left = self._arc_midpoint_by_names("PO7", "O1", "arc_inner_band")
        occipital_right = self._arc_midpoint_by_names("O2", "PO8", "arc_inner_band")
        occipital_mid = self._midpoint(raw_nodes["POz"], raw_nodes["Oz"])
        for point in self._points_on_arc(occipital_left, occipital_mid, occipital_right, 7):
            aux_points.append(("AUX_OCC_CAP", point))

        self._register_auxiliary_points(aux_points)

    # -------------------------------------------------------------
    # Geometry helpers
    # -------------------------------------------------------------
    def _equidistant_circle_points(self, center, radius, names, start_angle_deg):
        result = {}
        step = 360.0 / len(names)
        for index, name in enumerate(names):
            angle = math.radians(start_angle_deg + index * step)
            result[name] = (center[0] + radius * math.cos(angle), center[1] - radius * math.sin(angle))
        return result

    def _points_on_arc(self, left, middle, right, count):
        circle = self._circle_from_three_points(left, middle, right)
        if circle is None:
            return self._interpolate_polyline([left, middle, right], count)
        center, radius = circle
        a_left = self._screen_angle(center, left)
        a_mid = self._screen_angle(center, middle)
        a_right = self._screen_angle(center, right)
        ccw_delta = (a_right - a_left) % (2 * math.pi)
        ccw_mid = (a_mid - a_left) % (2 * math.pi)
        delta = ccw_delta if ccw_mid <= ccw_delta else -((a_left - a_right) % (2 * math.pi))
        points = []
        for index in range(count):
            t = 0.0 if count == 1 else index / (count - 1)
            angle = a_left + delta * t
            points.append((center[0] + radius * math.cos(angle), center[1] - radius * math.sin(angle)))
        return points

    def _register_arc(self, arc_id, node_names, raw_nodes, left_name, middle_name, right_name):
        circle = self._circle_from_three_points(raw_nodes[left_name], raw_nodes[middle_name], raw_nodes[right_name])
        if circle is None:
            self._register_line(arc_id, node_names, raw_nodes)
            return
        center, radius = circle
        start_angle = self._screen_angle(center, raw_nodes[left_name])
        mid_angle = self._screen_angle(center, raw_nodes[middle_name])
        end_angle = self._screen_angle(center, raw_nodes[right_name])
        ccw_delta = (end_angle - start_angle) % (2 * math.pi)
        ccw_mid = (mid_angle - start_angle) % (2 * math.pi)
        delta = ccw_delta if ccw_mid <= ccw_delta else -((start_angle - end_angle) % (2 * math.pi))
        self.arc_meta[arc_id] = {
            "type": "arc",
            "center": center,
            "radius": radius,
            "start_angle": start_angle,
            "delta_angle": delta,
            "node_names": node_names,
            "node_angles": {name: self._screen_angle(center, raw_nodes[name]) for name in node_names},
        }

    def _register_circle(self, arc_id, node_names, raw_nodes, center, radius):
        self.arc_meta[arc_id] = {
            "type": "circle",
            "center": center,
            "radius": radius,
            "node_names": node_names,
            "node_angles": {name: self._screen_angle(center, raw_nodes[name]) for name in node_names},
        }

    def _register_line(self, arc_id, node_names, raw_nodes):
        self.arc_meta[arc_id] = {
            "type": "line",
            "node_names": node_names,
            "points": {name: raw_nodes[name] for name in node_names},
        }

    def _sample_arc_points(self, arc_id, count):
        meta = self.arc_meta[arc_id]
        if meta["type"] == "line":
            return self._interpolate_polyline([meta["points"][name] for name in meta["node_names"]], count)
        if meta["type"] == "circle":
            points = []
            for index in range(count):
                angle = 2.0 * math.pi * index / count
                points.append((meta["center"][0] + meta["radius"] * math.cos(angle), meta["center"][1] - meta["radius"] * math.sin(angle)))
            return points
        points = []
        for index in range(count):
            t = 0.0 if count == 1 else index / (count - 1)
            points.append(self._point_on_registered_arc(arc_id, t))
        return points

    def _point_on_registered_arc(self, arc_id, t):
        meta = self.arc_meta[arc_id]
        if meta["type"] == "line":
            names = meta["node_names"]
            start = meta["points"][names[0]]
            end = meta["points"][names[-1]]
            return (start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t)
        angle = meta["start_angle"] + meta["delta_angle"] * t
        return (meta["center"][0] + meta["radius"] * math.cos(angle), meta["center"][1] - meta["radius"] * math.sin(angle))

    def _arc_midpoint_by_names(self, left, right, arc_id):
        meta = self.arc_meta[arc_id]
        if meta["type"] == "line":
            return self._midpoint(meta["points"][left], meta["points"][right])
        if meta["type"] == "circle":
            a_left = meta["node_angles"][left]
            a_right = meta["node_angles"][right]
            ccw_delta = (a_right - a_left) % (2 * math.pi)
            if ccw_delta > math.pi:
                ccw_delta -= 2 * math.pi
            angle = a_left + ccw_delta * 0.5
            return (meta["center"][0] + meta["radius"] * math.cos(angle), meta["center"][1] - meta["radius"] * math.sin(angle))
        node_names = meta["node_names"]
        left_index = node_names.index(left)
        right_index = node_names.index(right)
        t = (left_index + right_index) * 0.5 / (len(node_names) - 1)
        return self._point_on_registered_arc(arc_id, t)

    def _pairwise_midpoints(self, rows, raw_nodes, prefix):
        points = []
        for upper, lower in zip(rows, rows[1:]):
            for upper_name, lower_name in zip(upper, lower):
                points.append((prefix, self._midpoint(raw_nodes[upper_name], raw_nodes[lower_name])))
        return points

    def _quad_centers(self, rows, raw_nodes, prefix):
        points = []
        for upper, lower in zip(rows, rows[1:]):
            for index in range(min(len(upper), len(lower)) - 1):
                quad_names = (upper[index], upper[index + 1], lower[index + 1], lower[index])
                points.append((prefix, self._quad_center_from_names(quad_names, raw_nodes)))
        return points

    def _quad_center_from_names(self, quad_names, raw_nodes):
        xs = [raw_nodes[name][0] for name in quad_names]
        ys = [raw_nodes[name][1] for name in quad_names]
        return (sum(xs) / 4.0, sum(ys) / 4.0)

    def _register_auxiliary_points(self, aux_points):
        exact_seen = {}
        accepted_points = []
        counters = {}
        for prefix, point in aux_points:
            rounded = (round(point[0], 4), round(point[1], 4))
            if rounded in exact_seen:
                continue
            if any(math.hypot(point[0] - old[0], point[1] - old[1]) < self.AUX_MERGE_DISTANCE for old in accepted_points):
                continue
            exact_seen[rounded] = True
            accepted_points.append(point)
            counters[prefix] = counters.get(prefix, 0) + 1
            self._register_node(
                f"{prefix}_{counters[prefix]:02d}",
                point,
                self.SMALL_NODE_RADIUS,
                kind="aux",
                label="",
                selected_radius=self.SELECTED_NODE_RADIUS,
            )

    def _register_node(self, name, raw_point, radius, kind, label, selected_radius=None):
        normalized = (raw_point[0] / self.OUTER_RADIUS, raw_point[1] / self.OUTER_RADIUS)
        meta = {
            "kind": kind,
            "radius": radius / self.OUTER_RADIUS,
            "label": label,
            "selectable": True,
            "display_priority": 2 if kind == "named" else 1,
            "standard_name": name,
            "coord_3d": self.standard_positions_3d.get(name),
        }
        if kind == "named":
            meta["state_capabilities"] = self._state_capabilities_for_node(name)
        final_selected_radius = selected_radius if selected_radius is not None else self.SELECTED_NODE_RADIUS
        meta["selected_radius"] = final_selected_radius / self.OUTER_RADIUS
        self.all_nodes[name] = normalized
        self.node_meta[name] = meta

    def _assign_aux_standard_names(self):
        used_standard_names = {meta["standard_name"] for meta in self.node_meta.values() if meta["kind"] == "named"}
        candidates = []
        for name in self.standard_channel_names:
            if name in used_standard_names:
                continue
            projected = self._project_standard_name(name)
            if projected is None:
                continue
            candidates.append({"name": name, "pos": projected})

        aux_names = [name for name, meta in self.node_meta.items() if meta["kind"] == "aux"]
        aux_names.sort(key=lambda item: (self.all_nodes[item][1], self.all_nodes[item][0]))

        remaining = candidates[:]
        for aux_name in aux_names:
            aux_pos = self.all_nodes[aux_name]
            if not remaining:
                break
            best_index = min(
                range(len(remaining)),
                key=lambda idx: (remaining[idx]["pos"][0] - aux_pos[0]) ** 2 + (remaining[idx]["pos"][1] - aux_pos[1]) ** 2,
            )
            chosen = remaining.pop(best_index)
            self.node_meta[aux_name]["standard_name"] = chosen["name"]
            self.node_meta[aux_name]["coord_3d"] = self.standard_positions_3d.get(chosen["name"])

    def _project_standard_name(self, name):
        key = name.upper()
        y_val = None
        if key.startswith("AFP"):
            y_val = 0.875
            key = key[3:]
        elif key.startswith("AFF"):
            y_val = 0.625
            key = key[3:]
        elif key.startswith("FFC"):
            y_val = 0.375
            key = key[3:]
        elif key.startswith("FCC"):
            y_val = 0.125
            key = key[3:]
        elif key.startswith("CCP"):
            y_val = -0.125
            key = key[3:]
        elif key.startswith("CPP"):
            y_val = -0.375
            key = key[3:]
        elif key.startswith("PPO"):
            y_val = -0.625
            key = key[3:]
        elif key.startswith("POO"):
            y_val = -0.875
            key = key[3:]
        elif key.startswith("FP"):
            y_val = 1.0
            key = key[2:]
        elif key.startswith("AF"):
            y_val = 0.75
            key = key[2:]
        elif key.startswith("FC"):
            y_val = 0.25
            key = key[2:]
        elif key.startswith("CP"):
            y_val = -0.25
            key = key[2:]
        elif key.startswith("PO"):
            y_val = -0.75
            key = key[2:]
        elif key.startswith("FT"):
            y_val = 0.25
            key = key[2:]
        elif key.startswith("TP"):
            y_val = -0.25
            key = key[2:]
        elif key.startswith("F"):
            y_val = 0.5
            key = key[1:]
        elif key.startswith("C"):
            y_val = 0.0
            key = key[1:]
        elif key.startswith("P"):
            y_val = -0.5
            key = key[1:]
        elif key.startswith("O"):
            y_val = -1.0
            key = key[1:]
        elif key.startswith("T"):
            y_val = 0.0
            key = key[1:]
        else:
            return None

        if key == "Z":
            x_val = 0.0
        elif key.endswith("H"):
            try:
                num = int(key[:-1])
            except ValueError:
                return None
            val = (num + 1) // 2 * 0.25 - 0.125
            x_val = -val if num % 2 != 0 else val
        else:
            try:
                num = int(key)
            except ValueError:
                return None
            val = (num + 1) // 2 * 0.25
            x_val = -val if num % 2 != 0 else val

        x_circle = x_val * math.sqrt(max(0.0, 1.0 - (y_val ** 2) / 2.0))
        y_circle = y_val * math.sqrt(max(0.0, 1.0 - (x_val ** 2) / 2.0))
        return (x_circle, -y_circle)

    def _add_guide_shape(self, shape_type, points, pen, closed=False):
        self.guide_shapes.append(
            {
                "type": shape_type,
                "points": [(point[0] / self.OUTER_RADIUS, point[1] / self.OUTER_RADIUS) for point in points],
                "color": pen["color"],
                "style": pen["style"],
                "width": pen["width"],
                "closed": closed,
            }
        )

    def _add_guide_circle(self, center, radius, pen):
        self.guide_shapes.append(
            {
                "type": "circle",
                "center": (center[0] / self.OUTER_RADIUS, center[1] / self.OUTER_RADIUS),
                "radius": radius / self.OUTER_RADIUS,
                "color": pen["color"],
                "style": pen["style"],
                "width": pen["width"],
                "closed": True,
            }
        )

    def _circle_from_three_points(self, p1, p2, p3):
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        determinant = 2.0 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
        if abs(determinant) < 1e-6:
            return None
        ux = ((x1 * x1 + y1 * y1) * (y2 - y3) + (x2 * x2 + y2 * y2) * (y3 - y1) + (x3 * x3 + y3 * y3) * (y1 - y2)) / determinant
        uy = ((x1 * x1 + y1 * y1) * (x3 - x2) + (x2 * x2 + y2 * y2) * (x1 - x3) + (x3 * x3 + y3 * y3) * (x2 - x1)) / determinant
        return (ux, uy), math.hypot(x1 - ux, y1 - uy)

    def _screen_angle(self, center, point):
        return math.atan2(-(point[1] - center[1]), point[0] - center[0])

    def _midpoint(self, p1, p2):
        return ((p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5)

    def _interpolate_polyline(self, points, count):
        if count <= 1:
            return [points[0]]
        lengths = [0.0]
        total = 0.0
        for start, end in zip(points, points[1:]):
            total += math.hypot(end[0] - start[0], end[1] - start[1])
            lengths.append(total)
        if total <= 1e-6:
            return [points[0]] * count
        samples = []
        for index in range(count):
            target = total * index / (count - 1)
            seg_index = 0
            while seg_index < len(lengths) - 2 and lengths[seg_index + 1] < target:
                seg_index += 1
            seg_start = points[seg_index]
            seg_end = points[seg_index + 1]
            seg_length = lengths[seg_index + 1] - lengths[seg_index]
            ratio = 0.0 if seg_length <= 1e-6 else (target - lengths[seg_index]) / seg_length
            samples.append((seg_start[0] + (seg_end[0] - seg_start[0]) * ratio, seg_start[1] + (seg_end[1] - seg_start[1]) * ratio))
        return samples

    # -------------------------------------------------------------
    # Selection and channel logic
    # -------------------------------------------------------------
    def cycle_node_state(self, node_name: str):
        if node_name not in self.all_nodes:
            return
        current = self.selected_states.get(node_name, "None")
        flow = ["None"] + self.node_meta.get(node_name, {}).get("state_capabilities", ["Source", "Detector", "EEG"])
        start_idx = flow.index(current)
        for offset in range(1, len(flow) + 1):
            next_state = flow[(start_idx + offset) % len(flow)]
            if next_state == "None":
                self.set_node_state(node_name, "None")
                return
            current_count = sum(1 for state in self.selected_states.values() if state == next_state)
            if next_state in {"Ref", "GND"} or current_count < self.limits.get(next_state, 999):
                self.set_node_state(node_name, next_state)
                return

    def set_node_state(self, node_name: str, state: str, alias: str = None):
        node_name = self.resolve_node_name(node_name)
        if node_name not in self.all_nodes:
            return
        capabilities = self.node_meta.get(node_name, {}).get("state_capabilities", ["Source", "Detector", "EEG"])
        if state not in ["None"] + capabilities:
            return
        if state != "None":
            current_count = sum(1 for value in self.selected_states.values() if value == state)
            if state not in {"Ref", "GND"} and current_count >= self.limits.get(state, 999):
                return
            if state in {"Ref", "GND"}:
                for old_node in [name for name, old_state in self.selected_states.items() if old_state == state and name != node_name]:
                    self.set_node_state(old_node, "None")

        old_state = self.selected_states.get(node_name, "None")
        if old_state != "None" and node_name in self.node_aliases:
            old_alias = self.node_aliases[node_name]
            self.blacklisted_channels = {pair for pair in self.blacklisted_channels if old_alias not in pair}
            del self.node_aliases[node_name]

        if state == "None":
            self.selected_states.pop(node_name, None)
        else:
            self.selected_states[node_name] = state
            if alias:
                self.node_aliases[node_name] = alias
            elif state == "Source":
                self.node_aliases[node_name] = self._get_next_alias("S")
            elif state == "Detector":
                self.node_aliases[node_name] = self._get_next_alias("D")
            elif state == "EEG":
                self.node_aliases[node_name] = self._get_next_alias("E")
            elif state == "Ref":
                self.node_aliases[node_name] = "REF"
            elif state == "GND":
                self.node_aliases[node_name] = "GND"

        self._calculate_channels()
        self.signal_selection_changed.emit()

    def _get_next_alias(self, prefix: str) -> str:
        existing_nums = []
        for alias in self.node_aliases.values():
            if alias.startswith(prefix):
                try:
                    existing_nums.append(int(alias[len(prefix):]))
                except ValueError:
                    pass
        candidate = 1
        while candidate in existing_nums:
            candidate += 1
        return f"{prefix}{candidate}"

    def _calculate_channels(self):
        self.valid_channels.clear()
        sources = [name for name, state in self.selected_states.items() if state == "Source"]
        detectors = [name for name, state in self.selected_states.items() if state == "Detector"]
        sources.sort(key=lambda name: self._alias_index(self.node_aliases.get(name, "S0")))
        detectors.sort(key=lambda name: self._alias_index(self.node_aliases.get(name, "D0")))
        for source in sources:
            for detector in detectors:
                s_alias = self.node_aliases[source]
                d_alias = self.node_aliases[detector]
                if (s_alias, d_alias) in self.blacklisted_channels or (d_alias, s_alias) in self.blacklisted_channels:
                    continue
                p1 = self.all_nodes[source]
                p2 = self.all_nodes[detector]
                if math.hypot(p1[0] - p2[0], p1[1] - p2[1]) <= self.channel_distance_threshold:
                    self.valid_channels.append((source, detector))

    def _alias_index(self, alias: str) -> int:
        try:
            return int(alias[1:])
        except (TypeError, ValueError):
            return 0

    def toggle_channel_blacklist(self, source_alias: str, detector_alias: str, disable: bool):
        pair = (source_alias, detector_alias)
        if disable:
            self.blacklisted_channels.add(pair)
        else:
            self.blacklisted_channels.discard(pair)
            self.blacklisted_channels.discard((detector_alias, source_alias))
        self._calculate_channels()
        self.signal_selection_changed.emit()

    def set_limits(self, eeg=32, source=16, detector=16, emg=16):
        self.limits["EEG"] = eeg
        self.limits["Source"] = source
        self.limits["Detector"] = detector
        self.limits["EMG"] = emg

    def clear_all_selections(self):
        self.selected_states.clear()
        self.node_aliases.clear()
        self.valid_channels.clear()
        self.blacklisted_channels.clear()
        self.signal_selection_changed.emit()

    # -------------------------------------------------------------
    # Export helpers
    # -------------------------------------------------------------
    def get_fnirs_montage_dict(self):
        sources = {}
        detectors = {}

        def alias_sort_key(item):
            alias = item[1]
            prefix = alias[0] if alias else ""
            number = int(alias[1:]) if len(alias) > 1 and alias[1:].isdigit() else 0
            return prefix, number

        for name, alias in sorted(self.node_aliases.items(), key=alias_sort_key):
            state = self.selected_states.get(name)
            coord = self.all_nodes.get(name)
            if state == "Source":
                sources[alias] = {
                    "standard_name": self.node_meta[name]["standard_name"],
                    "layout_name": name,
                    "coord": coord,
                    "coord_3d": self.node_meta[name].get("coord_3d"),
                }
            elif state == "Detector":
                detectors[alias] = {
                    "standard_name": self.node_meta[name]["standard_name"],
                    "layout_name": name,
                    "coord": coord,
                    "coord_3d": self.node_meta[name].get("coord_3d"),
                }

        channels = [f"{self.node_aliases[source_name]}-{self.node_aliases[detector_name]}" for source_name, detector_name in self.valid_channels]
        return {
            "source_num": len(sources),
            "detector_num": len(detectors),
            "sources": sources,
            "detectors": detectors,
            "fnirs_pairs": channels,
        }

    def get_eeg_montage_dict(self):
        eeg_electrodes = {}
        ref_node = None
        gnd_node = None

        def alias_sort_key(item):
            alias = item[1]
            prefix = alias[0] if alias else ""
            number = int(alias[1:]) if len(alias) > 1 and alias[1:].isdigit() else 0
            return prefix, number

        for name, alias in sorted(self.node_aliases.items(), key=alias_sort_key):
            state = self.selected_states.get(name)
            entry = {
                "standard_name": self.node_meta[name]["standard_name"],
                "layout_name": name,
                "coord": self.all_nodes.get(name),
                "coord_3d": self.node_meta[name].get("coord_3d"),
                "role": state,
            }
            if state == "EEG":
                eeg_electrodes[alias] = entry
            elif state == "Ref":
                ref_node = entry
            elif state == "GND":
                gnd_node = entry

        return {
            "eeg_num": len(eeg_electrodes),
            "eeg_channels": list(eeg_electrodes.keys()),
            "eeg_details": eeg_electrodes,
            "ref_node": ref_node,
            "gnd_node": gnd_node,
        }
