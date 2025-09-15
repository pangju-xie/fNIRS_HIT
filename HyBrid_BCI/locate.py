# -*- coding: utf-8 -*-

import sys
import math
from typing import Dict, List, Tuple, Optional, Union, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets
from ui_locate import Ui_Locate

# ===================== LOGGING CONFIGURATION =====================

def setup_logging(log_level: str = "DEBUG") -> logging.Logger:
    """Setup comprehensive logging configuration."""
    log_format = (
        '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - '
        '%(funcName)s:%(lineno)d - %(message)s'
    )
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.DEBUG),
        format=log_format,
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('electrode_interface.log', mode='a', encoding='utf-8')
        ],
        force=True
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized with level: {log_level}")
    return logger

logger = setup_logging()

# ===================== ENUMS AND DATA CLASSES =====================

class ElectrodeType(Enum):
    """Enum for electrode types with validation."""
    SOURCE = "Source"
    DETECT = "Detect"
    EEG = "eeg"
    FNIRS = "fnirs"
    
    @classmethod
    def from_string(cls, value: str) -> Optional['ElectrodeType']:
        """Safely convert string to ElectrodeType."""
        try:
            for electrode_type in cls:
                if electrode_type.value.lower() == value.lower():
                    return electrode_type
            return None
        except (ValueError, AttributeError):
            logger.warning(f"Invalid electrode type: {value}")
            return None

class ChannelState(Enum):
    """Enum for channel activation states with colors."""
    INACTIVE = ("gray", "#808080")
    GREAT = ("green", "#4CAF50") 
    NOTBAD = ("yellow", "#FFC107")
    BAD = ("red", "#F44336")
    
    @property
    def color_name(self) -> str:
        return self.value[0]
    
    @property
    def color_hex(self) -> str:
        return self.value[1]

@dataclass
class NodeInfo:
    """Data class for current node information with validation."""
    type: Optional[ElectrodeType] = None
    number: int = 0
    checked: bool = False
    
    def is_valid(self) -> bool:
        """Check if node info is valid for operations."""
        is_valid = self.type is not None and self.checked and self.number > 0
        logger.debug(f"NodeInfo validation: type={self.type}, number={self.number}, "
                    f"checked={self.checked}, valid={is_valid}")
        return is_valid
    
    def __post_init__(self):
        """Validate data after initialization."""
        if self.number < 0:
            logger.warning(f"Invalid node number: {self.number}, setting to 0")
            self.number = 0

@dataclass
class ElectrodeState:
    """Data class for electrode state information with validation."""
    number: int
    type: ElectrodeType
    original_name: str
    position: Optional[Tuple[int, int]] = None
    
    def __post_init__(self):
        """Validate electrode state after initialization."""
        if self.number <= 0:
            logger.error(f"Invalid electrode number: {self.number} for {self.original_name}")
            raise ValueError(f"Electrode number must be positive, got {self.number}")
        
        if not self.original_name:
            logger.error("Electrode name cannot be empty")
            raise ValueError("Electrode name cannot be empty")
        
        logger.debug(f"Created ElectrodeState: {self}")

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

# ===================== CORE MANAGERS =====================

class ElectrodeManager:
    """Manages electrode states and operations."""
    
    def __init__(self):
        self.states: Dict[str, ElectrodeState] = {}
        logger.info("ElectrodeManager initialized")
    
    def add_electrode(self, name: str, electrode_type: ElectrodeType, 
                     number: int, position: Optional[Tuple[int, int]] = None) -> bool:
        """Add or update electrode state with validation."""
        logger.info(f"Adding electrode: {name}, type={electrode_type.value}, "
                   f"number={number}, position={position}")
        
        try:
            if name in self.states:
                logger.info(f"Updating existing electrode: {name}")
            
            self.states[name] = ElectrodeState(
                number=number,
                type=electrode_type,
                original_name=name,
                position=position
            )
            logger.info(f"Successfully added/updated electrode: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add electrode {name}: {e}")
            return False
    
    def remove_electrode(self, name: str) -> bool:
        """Remove electrode state."""
        logger.info(f"Removing electrode: {name}")
        
        if name in self.states:
            del self.states[name]
            logger.info(f"Successfully removed electrode: {name}")
            return True
        else:
            logger.warning(f"Attempted to remove non-existent electrode: {name}")
            return False
    
    def get_electrode(self, name: str) -> Optional[ElectrodeState]:
        """Get electrode state safely."""
        state = self.states.get(name)
        if state:
            logger.debug(f"Retrieved electrode state for: {name}")
        else:
            logger.debug(f"No state found for electrode: {name}")
        return state
    
    def get_electrodes_by_type(self, electrode_type: ElectrodeType) -> Dict[int, str]:
        """Get all electrodes of a specific type."""
        result = {}
        for name, state in self.states.items():
            if state.type == electrode_type:
                result[state.number] = state.original_name
        
        logger.debug(f"Found {len(result)} electrodes of type {electrode_type.value}")
        return result
    
    def clear_all(self) -> int:
        """Clear all electrode states."""
        count = len(self.states)
        self.states.clear()
        logger.info(f"Cleared {count} electrode states")
        return count

class PositionManager:
    """Manages position calculations and conversions."""
    
    def __init__(self):
        self.ui_positions: Dict[str, Tuple[int, int]] = {}
        self.positions_3d: Dict[str, Tuple[int, int, int]] = {}
        logger.info("PositionManager initialized")
    
    def set_position_data(self, ui_positions: Dict, positions_3d: Dict):
        """Set position data for calculations."""
        self.ui_positions = ui_positions or {}
        self.positions_3d = positions_3d or {}
        logger.info(f"Position data set: {len(self.ui_positions)} 2D positions, "
                   f"{len(self.positions_3d)} 3D positions")
    
    def get_3d_position(self, node: str) -> Optional[Position3D]:
        """Get 3D position with composite node handling."""
        logger.debug(f"Getting 3D position for node: {node}")
        
        try:
            if '_' in node:
                return self._get_composite_3d_position(node)
            elif node in self.positions_3d:
                pos = self.positions_3d[node]
                return Position3D(pos[0], pos[1], pos[2])
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
            if component in self.positions_3d:
                pos = self.positions_3d[component]
                valid_positions.append(Position3D(pos[0], pos[1], pos[2]))
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

class ChannelCalculator:
    """Handles channel pair calculations and validations."""
    
    def __init__(self, distance_threshold: float = 40.0):
        self.distance_threshold = distance_threshold
        self.position_manager = PositionManager()
        logger.info(f"ChannelCalculator initialized with threshold: {distance_threshold}mm")
    
    def set_position_data(self, ui_positions: Dict, positions_3d: Dict):
        """Set position data for calculations."""
        self.position_manager.set_position_data(ui_positions, positions_3d)
    
    def calculate_fnirs_pairs(self, electrode_manager: ElectrodeManager) -> Dict[str, Dict]:
        """Calculate valid fNIRS channel pairs."""
        logger.info("Calculating fNIRS channel pairs")
        
        sources = electrode_manager.get_electrodes_by_type(ElectrodeType.SOURCE)
        detectors = electrode_manager.get_electrodes_by_type(ElectrodeType.DETECT)
        
        logger.info(f"Found {len(sources)} sources and {len(detectors)} detectors")
        
        valid_pairs = {}
        
        for source_num, source_node in sources.items():
            for detector_num, detector_node in detectors.items():
                try:
                    distance = self.position_manager.calculate_3d_distance(source_node, detector_node)
                    
                    if distance <= self.distance_threshold:
                        channel_name = f'S{source_num}-D{detector_num}'
                        valid_pairs[channel_name] = {
                            'node_pair': f"{source_node}-{detector_node}",
                            'distance': distance,
                            'source_node': source_node,
                            'detector_node': detector_node
                        }
                        logger.info(f"Valid fNIRS pair: {channel_name}, "
                                   f"distance: {distance:.2f}mm")
                    else:
                        logger.debug(f"Distance {distance:.2f}mm exceeds threshold "
                                    f"for S{source_num}-D{detector_num}")
                        
                except Exception as e:
                    logger.error(f"Error calculating distance for S{source_num}-D{detector_num}: {e}")
        
        logger.info(f"Found {len(valid_pairs)} valid fNIRS channel pairs")
        return valid_pairs
    
    def calculate_eeg_pairs(self, electrode_manager: ElectrodeManager) -> Dict[str, Dict]:
        """Calculate EEG channel pairs."""
        logger.info("Calculating EEG channel pairs")
        
        eeg_electrodes = electrode_manager.get_electrodes_by_type(ElectrodeType.EEG)
        
        eeg_pairs = {}
        for number, node_name in eeg_electrodes.items():
            channel_name = f'EEG{number}'
            eeg_pairs[channel_name] = {
                'node': node_name,
                'position': self.position_manager.ui_positions.get(node_name)
            }
            logger.debug(f"EEG pair: {channel_name} -> {node_name}")
        
        logger.info(f"Found {len(eeg_pairs)} EEG channel pairs")
        return eeg_pairs

# ===================== UI UTILITIES =====================

class UIUtilities:
    """Common UI utility functions."""
    
    @staticmethod
    def show_message(parent: QtWidgets.QWidget, message: str, title: str = "Information", 
                    icon: QtWidgets.QMessageBox.Icon = QtWidgets.QMessageBox.Information):
        """Show message dialog with error handling."""
        logger.info(f"Showing {icon.name} message: {message}")
        
        try:
            msg_box = QtWidgets.QMessageBox(parent)
            msg_box.setIcon(icon)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.exec_()
            
        except Exception as e:
            logger.error(f"Failed to show message: {e}")
    
    @staticmethod
    def show_error(parent: QtWidgets.QWidget, message: str, title: str = "Error"):
        """Show error message."""
        UIUtilities.show_message(parent, message, title, QtWidgets.QMessageBox.Warning)
    
    @staticmethod
    def format_pairs_list(pairs_list: List[str], max_display: int = 10) -> str:
        """Format pairs list for display."""
        if not pairs_list:
            return "None"
        
        if len(pairs_list) <= max_display:
            return ', '.join(pairs_list)
        else:
            displayed = ', '.join(pairs_list[:max_display])
            return f"{displayed}\n... and {len(pairs_list) - max_display} more"

# ===================== MAIN APPLICATION CLASS =====================

class Locate(QtWidgets.QWidget):
    """Main application class for EEG electrode interface."""
    
    # Configuration constants
    class Config:
        DISTANCE_THRESHOLD = 40.0    # mm for valid channels
        ELECTRODE_SIZE = 26          # pixels
        ALIGNMENT_THRESHOLD = 20     # pixels
        NEAR_THRESHOLD = 10          # pixels
        EXISTING_NODE_THRESHOLD = 30 # pixels
        HEAD_RADIUS = 240            # pixels
    
    def __init__(self):
        super().__init__()
        logger.info("Initializing Locate application")
        
        try:
            self._initialize_components()
            self._setup_ui()
            self._connect_signals()
            logger.info("Locate application initialized successfully")
            
        except Exception as e:
            logger.critical(f"Failed to initialize Locate application: {e}")
            raise
    
    def _initialize_components(self):
        """Initialize all components."""
        logger.debug("Initializing components")
        
        # Core components
        self.electrode_manager = ElectrodeManager()
        self.channel_calculator = ChannelCalculator(self.Config.DISTANCE_THRESHOLD)
        
        # State management
        self.current_node_info = NodeInfo()
        self.dynamic_buttons: Dict[str, QtWidgets.QPushButton] = {}
        
        # Channel data
        self.fnirs_node_pairs: Dict[str, Dict] = {}
        self.eeg_node_pairs: Dict[str, Dict] = {}
        
        logger.debug("Components initialized")
    
    def _setup_ui(self):
        """Setup user interface."""
        logger.debug("Setting up UI")
        
        try:
            self.ui = Ui_Locate()
            self.ui.setupUi(self)
            logger.debug("UI setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup UI: {e}")
            raise
    
    def _connect_signals(self):
        """Connect all signals with comprehensive error handling."""
        logger.debug("Connecting signals")
        
        try:
            self._connect_electrode_signals()
            logger.debug("All signals connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect signals: {e}")
            raise
    
    def _connect_electrode_signals(self):
        """Connect electrode button signals with error handling."""
        logger.debug("Connecting electrode signals")
        
        try:
            electrode_names = self.ui.get_all_electrode_names()
            logger.info(f"Connecting signals for {len(electrode_names)} electrodes")
            
            connected_count = 0
            failed_count = 0
            
            for name in electrode_names:
                try:
                    button = self.ui.get_electrode_button(name)
                    if not button:
                        logger.warning(f"Button not found for electrode: {name}")
                        failed_count += 1
                        continue
                    
                    # Connect signals
                    button.clicked.connect(
                        lambda checked, n=name: self._on_electrode_left_click(n)
                    )
                    button.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
                    button.customContextMenuRequested.connect(
                        lambda pos, n=name: self._on_electrode_right_click(n)
                    )
                    
                    connected_count += 1
                    logger.debug(f"Connected signals for electrode: {name}")
                    
                except Exception as e:
                    logger.error(f"Failed to connect signals for electrode {name}: {e}")
                    failed_count += 1
            
            logger.info(f"Signal connection complete: {connected_count} success, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Error in electrode signal connection: {e}")
            raise
    
    # ===================== EVENT HANDLERS =====================
    
    def _on_electrode_left_click(self, electrode_name: str):
        """Handle electrode left-click with comprehensive validation."""
        logger.info(f"Left click on electrode: {electrode_name}")
        
        try:
            if not self.current_node_info.is_valid():
                logger.warning(f"Invalid node info for electrode {electrode_name}: {self.current_node_info}")
                UIUtilities.show_error(self, "Please select electrode type and number first")
                return
            
            button = self.ui.get_electrode_button(electrode_name)
            if not button:
                logger.error(f"Button not found for electrode: {electrode_name}")
                UIUtilities.show_error(self, f"Button not found for electrode: {electrode_name}")
                return
            
            # Add to electrode manager
            success = self.electrode_manager.add_electrode(
                electrode_name, 
                self.current_node_info.type, 
                self.current_node_info.number,
                self._get_electrode_2d_position(electrode_name)
            )
            
            if success:
                self._update_button_appearance(button, self.current_node_info.type, self.current_node_info.number)
                logger.info(f"Successfully updated electrode {electrode_name}")
            else:
                logger.error(f"Failed to add electrode {electrode_name}")
                UIUtilities.show_error(self, f"Failed to update electrode: {electrode_name}")
            
        except Exception as e:
            logger.error(f"Error handling electrode left click {electrode_name}: {e}")
            UIUtilities.show_error(self, f"Error updating electrode: {str(e)}")
    
    def _on_electrode_right_click(self, electrode_name: str):
        """Handle electrode right-click with error handling."""
        logger.info(f"Right click on electrode: {electrode_name}")
        
        try:
            button = self.ui.get_electrode_button(electrode_name)
            if not button:
                logger.error(f"Button not found for electrode: {electrode_name}")
                return
            
            # Remove from electrode manager and restore appearance
            if self.electrode_manager.remove_electrode(electrode_name):
                self._restore_button_appearance(button, electrode_name)
                logger.info(f"Successfully restored electrode: {electrode_name}")
            else:
                logger.debug(f"Electrode {electrode_name} was not in modified state")
            
        except Exception as e:
            logger.error(f"Error handling electrode right click {electrode_name}: {e}")
            UIUtilities.show_error(self, f"Error restoring electrode: {str(e)}")
    
    # ===================== UI UPDATE METHODS =====================
    
    def _update_button_appearance(self, button: QtWidgets.QPushButton, 
                                electrode_type: ElectrodeType, number: int):
        """Update button appearance with error handling."""
        logger.debug(f"Updating button appearance: type={electrode_type.value}, number={number}")
        
        try:
            button.setText(str(number))
            
            if hasattr(self.ui, 'get_style_for_type'):
                button_size = "small" if button.width() < self.Config.ELECTRODE_SIZE else "normal"
                style = self.ui.get_style_for_type(electrode_type.value, button_size)
                button.setStyleSheet(style)
                logger.debug("Button style updated")
            else:
                logger.warning("UI does not have get_style_for_type method")
            
        except Exception as e:
            logger.error(f"Error updating button appearance: {e}")
    
    def _restore_button_appearance(self, button: QtWidgets.QPushButton, electrode_name: str):
        """Restore button to original appearance."""
        try:
            if hasattr(self.ui, 'get_style_for_type'):
                if "_" in electrode_name:
                    button.setText("")
                    style_type = 'center' if len(electrode_name.split("_")) > 2 else 'middle'
                    button.setStyleSheet(self.ui.get_style_for_type(style_type, 'small'))
                else:
                    button.setText(electrode_name)
                    button.setStyleSheet(self.ui.get_style_for_type('default'))
            logger.debug(f"Restored appearance for electrode: {electrode_name}")
            
        except Exception as e:
            logger.error(f"Error restoring button appearance for {electrode_name}: {e}")
    
    # ===================== POSITION METHODS =====================
    
    def _get_all_electrode_positions(self) -> Dict[str, Tuple[int, int]]:
        """Get all electrode positions with error handling."""
        logger.debug("Getting all electrode positions")
        
        try:
            # Get all position types for comprehensive coverage
            positions = {}
            
            # Base electrode positions
            if hasattr(self.ui, '_get_electrode_positions'):
                positions.update(self.ui._get_electrode_positions())
            
            # Mid electrode positions  
            if hasattr(self.ui, '_get_mid_electrode_positions'):
                positions.update(self.ui._get_mid_electrode_positions())
                
            # Center electrode positions
            if hasattr(self.ui, '_get_center_electrode_positions'):
                positions.update(self.ui._get_center_electrode_positions())
                
            logger.debug(f"Retrieved {len(positions)} total electrode positions")
            return positions
            
        except Exception as e:
            logger.error(f"Error getting electrode positions: {e}")
            return {}
    
    def _get_electrode_2d_position(self, electrode_name: str) -> Optional[Tuple[int, int]]:
        """Get 2D position of specific electrode."""
        logger.debug(f"Getting 2D position for electrode: {electrode_name}")
        
        try:
            positions = self._get_all_electrode_positions()
            position = positions.get(electrode_name)
            
            if position:
                logger.debug(f"Position for {electrode_name}: {position}")
            else:
                logger.warning(f"No position found for electrode: {electrode_name}")
            
            return position
            
        except Exception as e:
            logger.error(f"Error getting electrode position for {electrode_name}: {e}")
            return None
    
    def _update_position_data(self):
        """Update position data for channel calculator."""
        logger.debug("Updating position data for channel calculator")
        
        try:
            ui_positions = self._get_all_electrode_positions()
            positions_3d = {}
            
            if hasattr(self.ui, '_get_electrode_3d_positions'):
                positions_3d = self.ui._get_electrode_3d_positions()
                logger.debug(f"Retrieved {len(positions_3d)} 3D positions")
            else:
                logger.warning("UI does not have _get_electrode_3d_positions method")
            
            self.channel_calculator.set_position_data(ui_positions, positions_3d)
            
        except Exception as e:
            logger.error(f"Error updating position data: {e}")
    
    # ===================== DATA LOADING METHODS =====================
    
    def _load_fnirs_electrodes(self):
        """Load fNIRS electrodes from pairs data."""
        logger.info("Loading fNIRS electrodes")
        
        try:
            for channel_name, channel_info in self.fnirs_node_pairs.items():
                if '-' not in channel_info:
                    logger.warning(f"Invalid node pair format: {channel_info}")
                    continue
                
                source_node, detector_node = channel_info.split('-',1)
                
                try:
                    parts = channel_name.split('-',1)
                    source_num = int(parts[0][1:])  # Remove 'S' prefix
                    detector_num = int(parts[1][1:])  # Remove 'D' prefix
                    
                    # Add electrodes
                    self.set_current_node_info('Source', source_num, True)
                    self._on_electrode_left_click(source_node)
                    
                    self.set_current_node_info('Detect', detector_num, True)
                    self._on_electrode_left_click(detector_node)
                    
                    logger.debug(f"Loaded fNIRS pair: {channel_name}")
                    
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing channel name {channel_name}: {e}")
            
            logger.info(f"Loaded {len(self.fnirs_node_pairs)} fNIRS electrode pairs")
            
        except Exception as e:
            logger.error(f"Error loading fNIRS electrodes: {e}")
    
    def _load_eeg_electrodes(self):
        """Load EEG electrodes from pairs data."""
        logger.info("Loading EEG electrodes")
        
        try:
            for channel_name, channel_info in self.eeg_node_pairs.items():
                node_name = channel_info.get('node', '')
                
                if not node_name:
                    logger.warning(f"No node name for EEG channel: {channel_name}")
                    continue
                
                try:
                    eeg_num = int(channel_name[3:])  # Remove 'EEG' prefix
                    
                    self.electrode_manager.add_electrode(
                        node_name, ElectrodeType.EEG, eeg_num,
                        self._get_electrode_2d_position(node_name)
                    )
                    
                    logger.debug(f"Loaded EEG electrode: {channel_name}")
                    
                except ValueError as e:
                    logger.error(f"Error parsing EEG channel name {channel_name}: {e}")
            
            logger.info(f"Loaded {len(self.eeg_node_pairs)} EEG electrodes")
            
        except Exception as e:
            logger.error(f"Error loading EEG electrodes: {e}")
    
    # ===================== PUBLIC API METHODS =====================
    
    def set_current_node_info(self, electrode_type: Optional[str] = None, 
                            number: int = 0, checked: bool = False) -> bool:
        """Set current node information with validation."""
        logger.info(f"Setting node info: type={electrode_type}, number={number}, checked={checked}")
        
        try:
            node_type = None
            if electrode_type:
                node_type = ElectrodeType.from_string(electrode_type)
                if node_type is None:
                    logger.error(f"Invalid electrode type: {electrode_type}")
                    UIUtilities.show_error(self, f"Invalid electrode type: {electrode_type}")
                    return False
            
            self.current_node_info = NodeInfo(type=node_type, number=number, checked=checked)
            logger.info(f"Node info set successfully: {self.current_node_info}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting node info: {e}")
            UIUtilities.show_error(self, f"Error setting node info: {str(e)}")
            return False
    
    def load_pairs_info(self, node_pairs: Dict):
        """Load electrode pairs with validation."""
        logger.info(f"Loading pairs info: {list(node_pairs.keys())}")
        
        try:
            self.reset_all_electrodes()
            self._update_position_data()
            
            for electrode_type_key, pairs in node_pairs.items():
                logger.info(f"Processing {electrode_type_key}: {len(pairs)} pairs")
                
                try:
                    if 'fnirs' == electrode_type_key: 
                        self.fnirs_node_pairs = pairs
                        self._load_fnirs_electrodes()
                    elif 'eeg' in electrode_type_key:
                        self.eeg_node_pairs = pairs
                        self._load_eeg_electrodes()
                    else:
                        logger.warning(f"Unknown electrode type: {electrode_type_key}")
                        
                except Exception as e:
                    logger.error(f"Error processing {electrode_type_key}: {e}")
            
            logger.info("Pairs info loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading pairs info: {e}")
            UIUtilities.show_error(self, f"Error loading electrode data: {str(e)}")
    
    def reset_all_electrodes(self):
        """Reset all electrodes to original state."""
        logger.info("Resetting all electrodes")
        
        try:
            # Reset regular electrodes
            electrode_names = self.ui.get_all_electrode_names()
            reset_count = 0
            
            for name in electrode_names:
                try:
                    button = self.ui.get_electrode_button(name)
                    if button:
                        self._restore_button_appearance(button, name)
                        reset_count += 1
                except Exception as e:
                    logger.error(f"Error resetting electrode {name}: {e}")
            
            # Remove dynamic buttons
            dynamic_count = len(self.dynamic_buttons)
            for button_name, button in list(self.dynamic_buttons.items()):
                try:
                    button.deleteLater()
                except Exception as e:
                    logger.error(f"Error deleting dynamic button {button_name}: {e}")
            
            # Clear all data
            self.electrode_manager.clear_all()
            self.dynamic_buttons.clear()
            self.fnirs_node_pairs.clear()
            self.eeg_node_pairs.clear()
            
            logger.info(f"Reset complete: {reset_count} regular electrodes, "
                       f"{dynamic_count} dynamic buttons removed")
            
        except Exception as e:
            logger.error(f"Error during reset: {e}")
            UIUtilities.show_error(self, f"Error resetting electrodes: {str(e)}")
    
    def calculate_channel_pairs(self) -> Dict:
        """Calculate and return channel pair information."""
        logger.info("Calculating channel pairs")
        
        try:
            self._update_position_data()
            
            # Calculate fNIRS pairs
            calculated_fnirs = self.channel_calculator.calculate_fnirs_pairs(self.electrode_manager)
            
            # Calculate EEG pairs  
            calculated_eeg = self.channel_calculator.calculate_eeg_pairs(self.electrode_manager)
            
            # Update internal data
            self.fnirs_node_pairs = calculated_fnirs
            self.eeg_node_pairs = calculated_eeg
            
            summary = {
                'sources': len(self.get_sources()),
                'detectors': len(self.get_detectors()),
                'eeg_channels': len(self.get_eeg_electrodes()),
                'fnirs_channels': len(calculated_fnirs),
                'valid_fnirs_pairs': list(calculated_fnirs.keys()),
                'eeg_pairs': list(calculated_eeg.keys()),
                'calculation_timestamp': logger.name  # Simple timestamp placeholder
            }
            
            logger.info(f"Channel calculation complete: {summary}")
            return summary
            
        except Exception as e:
            logger.error(f"Error calculating channel pairs: {e}")
            UIUtilities.show_error(self, f"Error calculating channels: {str(e)}")
            return {}
    
    def get_channel_pairs_summary(self):
        """Get and display channel pairs summary."""
        logger.info("Generating channel pairs summary")
        
        try:
            summary = self.calculate_channel_pairs()
            
            if not summary:
                logger.warning("No summary data available")
                UIUtilities.show_error(self, "Failed to calculate channel summary")
                return
            
            # Format summary message
            summary_text = (
                f"Sources: {summary['sources']}\n"
                f"Detectors: {summary['detectors']}\n"
                f"EEG Channels: {summary['eeg_channels']}\n"
                f"Valid fNIRS Channels: {summary['fnirs_channels']}\n\n"
                f"fNIRS Pairs:\n{UIUtilities.format_pairs_list(summary['valid_fnirs_pairs'])}\n\n"
                f"EEG Pairs:\n{UIUtilities.format_pairs_list(summary['eeg_pairs'])}"
            )
            
            logger.info("Displaying channel summary to user")
            UIUtilities.show_message(self, summary_text, "Channel Configuration Summary")
            
        except Exception as e:
            logger.error(f"Error generating channel summary: {e}")
            UIUtilities.show_error(self, f"Error generating summary: {str(e)}")
    
    # ===================== GETTER METHODS =====================
    
    def get_fnirs_pairs(self) -> Dict[str, Dict]:
        """Get fNIRS channel pairs."""
        logger.debug(f"Returning {len(self.fnirs_node_pairs)} fNIRS pairs")
        return self.fnirs_node_pairs.copy()
    
    def get_eeg_pairs(self) -> Dict[str, Dict]:
        """Get EEG channel pairs."""
        logger.debug(f"Returning {len(self.eeg_node_pairs)} EEG pairs")
        return self.eeg_node_pairs.copy()
    
    def get_sources(self) -> Dict[int, str]:
        """Get all source electrodes."""
        sources = self.electrode_manager.get_electrodes_by_type(ElectrodeType.SOURCE)
        logger.debug(f"Returning {len(sources)} source electrodes")
        return sources
    
    def get_detectors(self) -> Dict[int, str]:
        """Get all detector electrodes."""
        detectors = self.electrode_manager.get_electrodes_by_type(ElectrodeType.DETECT)
        logger.debug(f"Returning {len(detectors)} detector electrodes")
        return detectors
    
    def get_eeg_electrodes(self) -> Dict[int, str]:
        """Get all EEG electrodes."""
        eeg = self.electrode_manager.get_electrodes_by_type(ElectrodeType.EEG)
        logger.debug(f"Returning {len(eeg)} EEG electrodes")
        return eeg
    
    def get_electrode_state(self, electrode_name: str) -> Optional[ElectrodeState]:
        """Get electrode state."""
        state = self.electrode_manager.get_electrode(electrode_name)
        if state:
            logger.debug(f"Retrieved state for electrode: {electrode_name}")
        else:
            logger.debug(f"No state found for electrode: {electrode_name}")
        return state
    
