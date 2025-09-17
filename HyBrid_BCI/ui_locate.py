# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui, QtWidgets
import logging
from typing import Dict, Tuple, List, Optional
from enum import Enum
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ElectrodeType(Enum):
    """电极类型枚举"""
    DEFAULT = "default"
    MIDDLE = "middle" 
    CENTER = "center"
    SOURCE = "Source"
    DETECTOR = "Detect"
    EEG = "eeg"


class ElectrodeSize(Enum):
    """电极大小枚举"""
    NORMAL = "normal"
    SMALL = "small"

@dataclass
class Position3D:
    """3D position with validation."""
    x: float
    y: float
    z: float
    
    def distance_to(self, other: 'Position3D') -> float:
        """Calculate 3D distance to another position."""
        distance = math.sqrt(
            (self.x - other.x)**2 + 
            (self.y - other.y)**2 + 
            (self.z - other.z)**2
        )
        logger.debug(f"3D Distance from {self} to {other}: {distance:.2f}")
        return distance
    
    def to_tuple(self) -> Tuple[float, float, float]:
        """Convert to tuple format."""
        return (self.x, self.y, self.z)
    
    @classmethod
    def from_tuple(cls, position: Tuple[float, float, float]) -> 'Position3D':
        """Create Position3D from tuple."""
        return cls(position[0], position[1], position[2])
    
    
class StyleConfig:
    """样式配置类，统一管理所有样式"""
    
    @staticmethod
    def _get_base_style(border_color: str, bg_color: str, text_color: str, 
                       border_radius: int, border_opacity: float = 1.0) -> str:
        """基础样式模板"""
        return f"""
            QPushButton {{
                border: 2px solid rgba({border_color}, {border_opacity});
                border-radius: {border_radius}px;
                background-color: {bg_color};
                color: {text_color};
                font: bold 12px;
                min-width: 10px;
                min-height: 10px;
                max-width: 40px;
                max-height: 40px;
            }}
            QPushButton:hover {{
                background-color: rgba(200, 200, 200, 0.3);
            }}
        """
    
    @staticmethod
    def get_head_style() -> str:
        """头部圆圈样式"""
        return """
            QLabel {
                border: 2px solid rgba(0, 0, 0, 0);
                border-radius: 240px;
                background-color: white;
                color: gray;
                font: bold 12px;
                min-width: 10px;
                min-height: 10px;
                max-width: 500px;
                max-height: 500px;
            }
        """
    
    @classmethod
    def get_electrode_style(cls, electrode_type: ElectrodeType, size: ElectrodeSize) -> str:
        """获取电极样式"""
        radius = 11 if size == ElectrodeSize.SMALL else 13
        
        style_configs = {
            ElectrodeType.DEFAULT: ("0, 0, 0", "transparent", "gray", radius, 1.0),
            ElectrodeType.MIDDLE: ("0, 0, 0", "transparent", "gray", radius, 0.65),
            ElectrodeType.CENTER: ("0, 0, 0", "transparent", "gray", radius, 0.05),
            ElectrodeType.SOURCE: ("255, 0, 0", "rgba(255, 0, 0, 0.3)", "red", radius, 1.0),
            ElectrodeType.DETECTOR: ("0, 0, 255", "rgba(0, 0, 255, 0.3)", "blue", radius, 1.0),
            ElectrodeType.EEG: ("0, 255, 0", "rgba(0, 255, 0, 0.3)", "green", radius, 1.0),
        }
        
        config = style_configs.get(electrode_type, style_configs[ElectrodeType.DEFAULT])
        return cls._get_base_style(*config)


class ElectrodePositions:
    """电极位置管理类"""
    
    @staticmethod
    def get_base_positions() -> Dict[str, Tuple[int, int]]:
        """基础电极位置"""
        return {
            # Left hemisphere electrodes
            'AF7': (134,  67),                    'AF3': (200,  82), 'Fp1': (199,  39), 
             'F7': ( 76, 121),  'F5': (114, 132),  'F3': (164, 141),  'F1': (214, 146),
            'FT7': ( 39, 196), 'FC5': ( 94, 200), 'FC3': (149, 204), 'FC1': (209, 206),
             'T7': ( 27, 267),  'C5': ( 87, 267),  'C3': (147, 267),  'C1': (207, 267),
            'TP7': ( 40, 340), 'CP5': ( 94, 334), 'CP3': (149, 330), 'CP1': (209, 328),
             'P7': ( 76, 413),  'P5': (114, 402),  'P3': (164, 393),  'P1': (214, 388),
            'PO7': (134, 467),                    'PO3': (200, 452),  'O1': (199, 496),
            
            # Midline electrodes
            'Fpz': (267,  27), 'AFz': (267,  87),  'Fz': (267, 147),
            'FCz': (267, 207),  'Cz': (267, 267), 'CPz': (267, 327),
             'Pz': (267, 387), 'POz': (267, 447),  'Oz': (267, 507),
            
            # Right hemisphere electrodes
            'AF8': (400,  67),                    'AF4': (334,  82), 'Fp2': (335,  39),
             'F8': (458, 121),  'F6': (420, 132),  'F4': (370, 141),  'F2': (320, 146),
            'FT8': (495, 196), 'FC6': (440, 200), 'FC4': (385, 204), 'FC2': (325, 206),
             'T8': (507, 267),  'C6': (447, 267),  'C4': (387, 267),  'C2': (327, 267),
            'TP8': (495, 340), 'CP6': (440, 334), 'CP4': (385, 330), 'CP2': (325, 328),
             'P8': (458, 413),  'P6': (420, 402),  'P4': (370, 393),  'P2': (320, 388),
            'PO8': (400, 467),                    'PO4': (334, 452),  'O2': (335, 496),
        }
    
    @staticmethod
    def get_3d_positions() -> Dict[str, Tuple[int, int, int]]:
        """3D电极位置"""
        return {
            # Left hemisphere electrodes
            'AF7': (-51,  71, -3),                        'AF3': (-36,  76, 24), 'Fp1': (-27,  83, -3), 
             'F7': (-71,  51, -3),  'F5': (-64,  55, 23),  'F3': (-48,  59, 44),  'F1': (-25,  62, 56),
            'FT7': (-83,  27, -3), 'FC5': (-78,  30, 27), 'FC3': (-59,  31, 56), 'FC1': (-33,  33, 74),
             'T7': (-87,   0, -3),  'C5': (-82,   0, 31),  'C3': (-63,   0, 61),  'C1': (-34,   0, 81),
            'TP7': (-83, -27, -3), 'CP5': (-78, -30, 27), 'CP3': (-59, -31, 56), 'CP1': (-33, -33, 74),
             'P7': (-71, -51, -3),  'P5': (-64, -55, 23),  'P3': (-48, -59, 44),  'P1': (-25, -62, 56),
            'PO7': (-51, -71, -3),                        'PO3': (-36, -76, 24),  'O1': (-27, -83, -3),
            
            # Midline electrodes
            'Fpz': (  0,  87, -3), 'AFz': (  0,  82, 31),  'Fz': (  0,  63, 61),
            'FCz': (  0,  34, 81),  'Cz': (  0,   0, 88), 'CPz': (  0, -34, 81),
             'Pz': (  0, -63, 61), 'POz': (  0, -82, 31),  'Oz': (  0, -87, -3),
            
            # Right hemisphere electrodes
            'AF8':  (51,  71, -3),                        'AF4': ( 36,  76, 24), 'Fp2': ( 27,  83, -3), 
             'F8':  (71,  51, -3),  'F6': ( 64,  55, 23),  'F4': ( 48,  59, 44),  'F2': ( 25,  62, 56),
            'FT8':  (83,  27, -3), 'FC6': ( 78,  30, 27), 'FC4': ( 59,  31, 56), 'FC2': ( 33,  33, 74),
             'T8':  (87,   0, -3),  'C6': ( 82,   0, 31),  'C4': ( 63,   0, 61),  'C2': ( 34,   0, 81),
            'TP8':  (83, -27, -3), 'CP6': ( 78, -30, 27), 'CP4': ( 59, -31, 56), 'CP2': ( 33, -33, 74),
             'P8':  (71, -51, -3),  'P6': ( 64, -55, 23),  'P4': ( 48, -59, 44),  'P2': ( 25, -62, 56),
            'PO8':  (51, -71, -3),                        'PO4': ( 36, -76, 24),  'O2': ( 27, -83, -3),
            
            # Additional electrodes
            'P10': (64, -47, -37),  'P9':(-64, -47, -37),  'Iz':  (0, -79, -37),
        }
    
    @classmethod
    def get_midpoint(cls, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> Tuple[int, int]:
        """计算两点中点"""
        return ((pos1[0] + pos2[0]) // 2, (pos1[1] + pos2[1]) // 2)
    
    @classmethod
    def get_center_point(cls, positions: List[Tuple[int, int]]) -> Tuple[int, int]:
        """计算多个点的中心点"""
        avg_x = sum(pos[0] for pos in positions) // len(positions)
        avg_y = sum(pos[1] for pos in positions) // len(positions)
        return (avg_x, avg_y)


class ElectrodeCalculator:
    """电极位置计算器"""
    
    def __init__(self, base_positions: Dict[str, Tuple[int, int]], node_names: List[str]):
        self.base_positions = base_positions
        self.node_names = node_names
        self.former = ["Fp", "AF", "F", "FC", "C", "CP", "P", "PO", "O"]
        self.latter = ["7", "5", "3", "1", "z", "2", "4", "6", "8"]
    
    def _get_adjusted_prefix(self, prefix: str, suffix: str) -> str:
        """根据后缀调整前缀"""
        if suffix in ["7", "8"]:
            prefix_map = {"FC": "FT", "C": "T", "CP": "TP"}
            return prefix_map.get(prefix, prefix)
        return prefix
    
    def _get_valid_nodes_for_row(self, prefix: str) -> List[str]:
        """获取行的有效节点"""
        valid_nodes = []
        for suffix in self.latter:
            adjusted_prefix = self._get_adjusted_prefix(prefix, suffix)
            node = adjusted_prefix + suffix
            if node in self.node_names:
                valid_nodes.append(node)
        return valid_nodes
    
    def _get_valid_nodes_for_column(self, suffix: str) -> List[str]:
        """获取列的有效节点"""
        if suffix in ['7', '8']:
            current_former = ["Fp", "AF", "F", "FT", "T", "TP", "P", "PO", "O"]
        else:
            current_former = self.former.copy()
        
        valid_nodes = []
        for prefix in current_former:
            node_name = prefix + suffix
            if node_name in self.node_names:
                valid_nodes.append(node_name)
        
        # 特殊处理
        if suffix == '1':
            valid_nodes.insert(1, "AF3")
            valid_nodes.insert(7, "PO3")
        elif suffix == '2':
            valid_nodes.insert(1, "AF4")
            valid_nodes.insert(7, "PO4")
        elif suffix in ["3", "4"]:
            if valid_nodes:
                valid_nodes = valid_nodes[1:-1]  # 去掉首尾
        
        return valid_nodes
    
    def _add_middle_nodes(self, valid_nodes: List[str]) -> Dict[str, Tuple[int, int]]:
        """添加相邻节点的中点"""
        middle_positions = {}
        for i in range(len(valid_nodes) - 1):
            node1, node2 = valid_nodes[i], valid_nodes[i + 1]
            pos1, pos2 = self.base_positions[node1], self.base_positions[node2]
            middle_positions[f'{node1}_{node2}'] = ElectrodePositions.get_midpoint(pos1, pos2)
        return middle_positions
    
    def calculate_mid_positions(self) -> Dict[str, Tuple[int, int]]:
        """计算中间电极位置"""
        middle_positions = {}
        
        # 水平中点（按行处理）
        for prefix in self.former:
            valid_nodes = self._get_valid_nodes_for_row(prefix)
            middle_positions.update(self._add_middle_nodes(valid_nodes))
        
        # 垂直处理
        for suffix in self.latter:
            valid_nodes = self._get_valid_nodes_for_column(suffix)
            middle_positions.update(self._add_middle_nodes(valid_nodes))
        
        return middle_positions
    
    def calculate_center_positions(self) -> Dict[str, Tuple[int, int]]:
        """计算中心电极位置"""
        center_positions = {}
        
        # 主网格中心点
        for j in range(len(self.latter) - 1):
            b1, b2 = self.latter[j], self.latter[j + 1]
            current_former1 = (["F", "FT", "T", "TP", "P"] if b1 == "7" 
                              else ["F", "FC", "C", "CP", "P"])
            current_former2 = (["F", "FT", "T", "TP", "P"] if b2 == "8" 
                              else ["F", "FC", "C", "CP", "P"])
            
            for i in range(len(current_former1) - 1):
                nodes = [
                    current_former1[i] + b1,
                    current_former1[i + 1] + b1,
                    current_former2[i] + b2,
                    current_former2[i + 1] + b2
                ]
                node_name = "_".join(nodes)
                positions = [self.base_positions[node] for node in nodes if node in self.base_positions]
                if positions:
                    center_positions[node_name] = ElectrodePositions.get_center_point(positions)
        
        # 特殊区域中心点
        special_groups = [
            (["Fp1", "Fpz", "AF3", "AFz"], "Fp1_Fpz_AF3_AFz"),
            (["Fpz", "Fp2", "AFz", "AF4"], "Fpz_Fp2_AFz_AF4"),
            (["O1", "Oz", "PO3", "POz"], "O1_Oz_PO3_POz"),
            (["Oz", "O2", "POz", "PO4"], "Oz_O2_POz_PO4"),
            (["AF3", "AFz", "F1", "Fz"], "AF3_AFz_F1_Fz"),
            (["AFz", "AF4", "Fz", "F2"], "AFz_AF4_Fz_F2"),
            (["P1", "Pz", "PO3", "POz"], "P1_Pz_PO3_POz"),
            (["Pz", "P2", "POz", "PO4"], "Pz_P2_POz_PO4"),
            (["AF7", "AF3", "F7", "F5"], "AF7_AF3_F7_F5"),
            (["AF4", "AF8", "F6", "F8"], "AF4_AF8_F6_F8"),
            (["P7", "P5", "PO7", "PO3"], "P7_P5_PO7_PO3"),
            (["P6", "P8", "PO4", "PO8"], "P6_P8_PO4_PO8"),
            (["AF7", "AF3", "F5", "F3"], "AF7_AF3_F5_F3"),
            (["AF4", "AF8", "F4", "F6"], "AF4_AF8_F4_F6"),
            (["P5", "P3", "PO3", "PO7"], "P5_P3_PO3_PO7"),
            (["P4", "P6", "PO4", "PO8"], "P4_P6_PO4_PO8"),
        ]
        
        for nodes, name in special_groups:
            positions = [self.base_positions[node] for node in nodes if node in self.base_positions]
            if positions:
                center_positions[name] = ElectrodePositions.get_center_point(positions)
        
        return center_positions


class PositionManager:
    """Manages position calculations and conversions."""
    
    def __init__(self):
        self.electrode_positions = ElectrodePositions()
        self._base_positions = self.electrode_positions.get_base_positions()
        self._base_3d_positions = self.electrode_positions.get_3d_positions()
        
        #计算所有类型的电极位置
        node_names = list(self._base_positions.keys())
        calculator = ElectrodeCalculator(self._base_positions, node_names)
        
        self._mid_positions = calculator.calculate_mid_positions()
        self._center_positions = calculator.calculate_center_positions()
        
        #合并所有2D位置
        self.all_2d_positions = {}
        self.all_2d_positions.update(self._base_positions)
        self.all_2d_positions.update(self._mid_positions)
        self.all_2d_positions.update(self._center_positions)
        
        logger.info(f"PositionManager initialized with {len(self.all_2d_positions)} 2D positions "
                   f"and {len(self._base_3d_positions)} 3D positions")
    
    def get_2d_positio(self, node_name: str) -> Optional[Tuple[int,int]]:
        position = self.all_2d_positions.get(node_name)
        if position:
            logger.debug(f"2D Position for {node_name}: {position}")
        else:
            logger.warning(f"No 2D position found for node: {node_name}")
        return position
    
    def get_3d_position(self, node: str) -> Optional[Position3D]:
        """Get 3D position with composite node handling."""
        logger.debug(f"Getting 3D position for node: {node}")
        
        try:
            if '_' in node:
                return self._get_composite_3d_position(node)
            elif node in self._base_3d_positions:
                pos = self._base_3d_positions[node]
                return Position3D.from_tuple(pos)
            else:
                logger.warning(f"Node {node} not found in 3D positions")
                return None
                
        except Exception as e:
            logger.error(f"Error getting 3D position for {node}: {e}")
            return None
    
    def _get_composite_3d_position(self, composite_node: str) -> Optional[Position3D]:
        """Calculate average position for composite nodes."""
        logger.debug(f"Calculating composite 3D position for: {composite_node}")
        
        components = composite_node.split('_')
        valid_positions = []
        
        for component in components:
            if component in self._base_3d_positions:
                pos = self._base_3d_positions[component]
                valid_positions.append(Position3D.from_tuple(pos))
                logger.debug(f"Added component {component} position: {pos}")
            else:
                logger.warning(f"Component {component} not found in 3D positions")
        
        if not valid_positions:
            logger.error(f"No valid positions found for composite node {composite_node}")
            return None
        
        # Calculate average
        avg_x = sum(pos.x for pos in valid_positions) / len(valid_positions)
        avg_y = sum(pos.y for pos in valid_positions) / len(valid_positions)
        avg_z = sum(pos.z for pos in valid_positions) / len(valid_positions)
        
        result = Position3D(avg_x, avg_y, avg_z)
        logger.debug(f"Composite position for {composite_node}: {result}")
        return result
    
    def calculate_3d_distance(self, node1: str, node2: str) -> float:
        """Calculate 3D distance between two nodes with error handling."""
        logger.debug(f"Calculating 3D distance between {node1} and {node2}")
        
        try:
            pos1 = self.get_3d_position(node1)
            pos2 = self.get_3d_position(node2)
            
            if pos1 is None or pos2 is None:
                logger.warning(f"Could not get 3D positions for {node1} or {node2}")
                return float('inf')
            
            distance = pos1.distance_to(pos2)
            logger.debug(f"3D distance {node1}-{node2}: {distance:.2f}mm")
            return distance
            
        except Exception as e:
            logger.error(f"Error calculating 3D distance {node1}-{node2}: {e}")
            return float('inf')

    def get_all_electrode_names(self) -> List[str]:
        """获取所有电极名称"""
        return list(self.all_2d_positions.keys())
    
    def get_base_electrode_names(self) -> List[str]:
        """获取基础电极名称"""
        return list(self._base_positions.keys())
    
    def get_mid_electrode_names(self) -> List[str]:
        """获取中间电极名称"""
        return list(self._mid_positions.keys())
    
    def get_center_electrode_names(self) -> List[str]:
        """获取中心电极名称"""
        return list(self._center_positions.keys())

class Ui_Locate(object):
    """UI class for EEG Electrode Interface with improved organization and consistency."""
    
    # Constants for better maintainability
    ELECTRODE_SIZE = 26
    HEAD_CIRCLE_SIZE = 480
    HEAD_CIRCLE_OFFSET = 40
    
    def __init__(self):
        self.dynamic_buttons = []
        self.position_manager = PositionManager()
        
    def setupUi(self, Form):
        """Setup the main UI components."""
        logger.info("Setting up UI components")
        
        Form.setObjectName("Form")
        Form.resize(564, 580)
        Form.setWindowTitle("EEG Electrode Interface")
        
        # Create components in logical order
        self._create_head_circle(Form)
        self._create_electrode_groups(Form)
        
        logger.info("UI setup completed successfully")
    
    def _create_head_circle(self, Form):
        """Create the circular background representing the head."""
        logger.debug("Creating head circle background")
        
        self.headCircle = QtWidgets.QLabel(Form)
        self.headCircle.setEnabled(False)
        self.headCircle.setGeometry(QtCore.QRect(
            self.HEAD_CIRCLE_OFFSET, 
            self.HEAD_CIRCLE_OFFSET, 
            self.HEAD_CIRCLE_SIZE, 
            self.HEAD_CIRCLE_SIZE
        ))
        self.headCircle.setStyleSheet(StyleConfig.get_head_style())
        self.headCircle.setText("")
        self.headCircle.setObjectName("headCircle")
        
        logger.debug("Head circle created successfully")
    
    def _create_electrode_groups(self, Form):
        """Create all electrode groups."""
        electrode_configs = [
            (self.position_manager._base_positions, ElectrodeType.DEFAULT, ElectrodeSize.NORMAL, 0, 0),
            (self.position_manager._mid_positions, ElectrodeType.MIDDLE, ElectrodeSize.SMALL, 2, 2),
            (self.position_manager._center_positions, ElectrodeType.CENTER, ElectrodeSize.SMALL, 2, 2),
        ]
        
        for positions, electrode_type, size, offset_x, offset_y in electrode_configs:
            self._create_electrode_buttons(Form, positions, electrode_type, size, offset_x, offset_y)
    
    def _create_electrode_buttons(self, Form, positions: Dict[str, Tuple[int, int]], 
                                electrode_type: ElectrodeType, size: ElectrodeSize, 
                                offset_x: int = 0, offset_y: int = 0):
        """Create electrode buttons from position data."""
        logger.info(f"Creating {electrode_type.value} electrode buttons")
        
        size_adjustment = -4 if size == ElectrodeSize.SMALL else 0
        button_size = self.ELECTRODE_SIZE + size_adjustment
        created_count = 0
        
        for name, (x, y) in positions.items():
            try:
                button = QtWidgets.QPushButton(Form)
                button.setGeometry(QtCore.QRect(
                    x + offset_x, y + offset_y, button_size, button_size
                ))
                button.setStyleSheet(StyleConfig.get_electrode_style(electrode_type, size))
                
                # 只有默认电极显示文本
                if electrode_type == ElectrodeType.DEFAULT:
                    button.setText(name)
                
                button.setObjectName(f"electrode_{name}")
                setattr(self, f"electrode_{name}", button)
                created_count += 1
                
            except Exception as e:
                logger.error(f"Failed to create electrode {name}: {e}")
        
        logger.info(f"Successfully created {created_count} {electrode_type.value} electrode buttons")
    
    def get_electrode_button(self, electrode_name: str) -> QtWidgets.QPushButton:
        """Get electrode button by name for easy access."""
        button = getattr(self, f"electrode_{electrode_name}", None)
        if button is None:
            logger.warning(f"Electrode button '{electrode_name}' not found")
        return button # type: ignore
    
    def get_default_electrode_names(self) -> List[str]:
        """Get list of all electrode names."""
        return self.position_manager.get_base_electrode_names()
    
    def get_all_electrode_names(self) -> List[str]:
        """Get list of all electrode names."""
        return self.position_manager.get_all_electrode_names()
    
    def get_position_manager(self) -> PositionManager:
        """Get the position manager instance."""
        if not hasattr(self, 'position_manager') or self.position_manager is None:
            logger.warning("Position manager not initialized, creating new instance")
            self.position_manager = PositionManager()
        return self.position_manager
    
    def get_style_for_type(self, electrode_type: str, button_size: str = "normal") -> str:
        """Get appropriate style for electrode type and size."""
        try:
            etype = ElectrodeType(electrode_type)
        except ValueError:
            etype = ElectrodeType.DEFAULT
        
        try:
            esize = ElectrodeSize(button_size)
        except ValueError:
            esize = ElectrodeSize.NORMAL
        
        return StyleConfig.get_electrode_style(etype, esize)
    
    def retranslateUi(self, Form):
        """Handle UI translation (placeholder for internationalization)."""
        pass