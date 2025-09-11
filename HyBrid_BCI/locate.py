# -*- coding: utf-8 -*-

import sys
import math
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets
from ui_locate import Ui_Locate

# Enhanced logging configuration with more detailed formatting
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
        force=True  # Override existing configuration
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized with level: {log_level}")
    return logger

logger = setup_logging()

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
            return cls(value)
        except ValueError:
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
class Position2D:
    """2D position with validation."""
    x: int
    y: int
    
    def distance_to(self, other: 'Position2D') -> float:
        """Calculate distance to another position."""
        distance = math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
        logger.debug(f"Distance from {self} to {other}: {distance:.2f}")
        return distance
    
    def __post_init__(self):
        """Validate position values."""
        if not isinstance(self.x, int) or not isinstance(self.y, int):
            logger.warning(f"Converting position values to int: x={self.x}, y={self.y}")
            self.x = int(self.x)
            self.y = int(self.y)

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

class ChannelCalculator:
    """Handles channel pair calculations and validations."""
    
    def __init__(self, distance_threshold: float = 35.0):
        self.distance_threshold = distance_threshold + 3
        self.ui_positions = {}
        self.positions_3d = {}
        logger.info(f"ChannelCalculator initialized with threshold: {distance_threshold}mm")
    
    def set_position_data(self, ui_positions: Dict, positions_3d: Dict):
        """Set position data for calculations."""
        self.ui_positions = ui_positions or {}
        self.positions_3d = positions_3d or {}
        logger.info(f"Position data set: {len(self.ui_positions)} 2D positions, "
                   f"{len(self.positions_3d)} 3D positions")
    
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
                    distance = self._calculate_3d_distance(source_node, detector_node)
                    
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
                'position': self._get_2d_position(node_name)
            }
            logger.debug(f"EEG pair: {channel_name} -> {node_name}")
        
        logger.info(f"Found {len(eeg_pairs)} EEG channel pairs")
        return eeg_pairs
    
    def _calculate_3d_distance(self, node1: str, node2: str) -> float:
        """Calculate 3D distance between two nodes with error handling."""
        logger.debug(f"Calculating 3D distance between {node1} and {node2}")
        
        try:
            pos1 = self._get_3d_position(node1)
            pos2 = self._get_3d_position(node2)
            
            if pos1 is None or pos2 is None:
                logger.warning(f"Could not get 3D positions for {node1} or {node2}")
                return float('inf')
            
            distance = pos1.distance_to(pos2)
            logger.debug(f"3D distance {node1}-{node2}: {distance:.2f}mm")
            return distance
            
        except Exception as e:
            logger.error(f"Error calculating 3D distance {node1}-{node2}: {e}")
            return float('inf')
    
    def _get_3d_position(self, node: str) -> Optional[Position3D]:
        """Get 3D position with composite node handling."""
        logger.debug(f"Getting 3D position for node: {node}")
        
        try:
            if '_' in node:
                # Handle composite nodes
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
    
    def _get_2d_position(self, node: str) -> Optional[Tuple[int, int]]:
        """Get 2D position with error handling."""
        logger.debug(f"Getting 2D position for node: {node}")
        
        try:
            if '_' in node:
                return self._get_composite_2d_position(node)
            elif node in self.ui_positions:
                pos = self.ui_positions[node]
                logger.debug(f"2D position for {node}: {pos}")
                return pos
            else:
                logger.warning(f"Node {node} not found in 2D positions")
                return None
                
        except Exception as e:
            logger.error(f"Error getting 2D position for {node}: {e}")
            return None
    
    def _get_composite_2d_position(self, composite_node: str) -> Optional[Tuple[int, int]]:
        """Calculate average 2D position for composite nodes."""
        logger.debug(f"Calculating composite 2D position for: {composite_node}")
        
        components = composite_node.split('_')
        valid_positions = []
        
        for component in components:
            if component in self.ui_positions:
                valid_positions.append(self.ui_positions[component])
                logger.debug(f"Added component {component} 2D position")
            else:
                logger.warning(f"Component {component} not found in 2D positions")
        
        if not valid_positions:
            logger.error(f"No valid 2D positions found for composite node {composite_node}")
            return None
        
        avg_x = sum(pos[0] for pos in valid_positions) // len(valid_positions)
        avg_y = sum(pos[1] for pos in valid_positions) // len(valid_positions)
        
        result = (avg_x, avg_y)
        logger.debug(f"Composite 2D position for {composite_node}: {result}")
        return result

class Locate(QtWidgets.QWidget):
    """Main application class for EEG electrode interface."""
    
    # Configuration constants
    class Config:
        ALIGNMENT_THRESHOLD = 20  # pixels
        NEAR_THRESHOLD = 10      # pixels
        DISTANCE_THRESHOLD = 35.0  # mm for valid channels
        EXISTING_NODE_THRESHOLD = 30  # pixels
        HEAD_RADIUS = 240  # pixels
        ELECTRODE_SIZE = 26  # pixels
    
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
            self._setup_head_circle_interactions()
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
                    
                    # Left click connection
                    button.clicked.connect(
                        lambda checked, n=name: self._on_electrode_left_click(n)
                    )
                    
                    # Right click connection
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
    
    def _setup_head_circle_interactions(self):
        """Setup head circle interactions with error handling."""
        logger.debug("Setting up head circle interactions")
        
        try:
            if not hasattr(self.ui, 'headCircle'):
                logger.error("UI does not have headCircle attribute")
                return
            
            self.ui.headCircle.mousePressEvent = self._on_head_circle_click
            self.ui.headCircle.setEnabled(True)
            
            # Right-click setup
            self.ui.headCircle.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
            self.ui.headCircle.customContextMenuRequested.connect(self._on_head_circle_right_click)
            
            logger.debug("Head circle interactions setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup head circle interactions: {e}")
    
    def _on_electrode_left_click(self, electrode_name: str):
        """Handle electrode left-click with comprehensive validation."""
        logger.info(f"Left click on electrode: {electrode_name}")
        
        try:
            if not self.current_node_info.is_valid():
                logger.warning(f"Invalid node info for electrode {electrode_name}: {self.current_node_info}")
                self._show_error_message("Please select electrode type and number first")
                return
            
            button = self.ui.get_electrode_button(electrode_name)
            if not button:
                logger.error(f"Button not found for electrode: {electrode_name}")
                self._show_error_message(f"Button not found for electrode: {electrode_name}")
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
                self._show_error_message(f"Failed to update electrode: {electrode_name}")
            
        except Exception as e:
            logger.error(f"Error handling electrode left click {electrode_name}: {e}")
            self._show_error_message(f"Error updating electrode: {str(e)}")
    
    def _on_electrode_right_click(self, electrode_name: str):
        """Handle electrode right-click with error handling."""
        logger.info(f"Right click on electrode: {electrode_name}")
        
        try:
            button = self.ui.get_electrode_button(electrode_name)
            if not button:
                logger.error(f"Button not found for electrode: {electrode_name}")
                return
            
            # Remove from electrode manager
            if self.electrode_manager.remove_electrode(electrode_name):
                # Restore original appearance
                button.setText(electrode_name)
                if hasattr(self.ui, 'get_style_for_type'):
                    button.setStyleSheet(self.ui.get_style_for_type('default'))
                logger.info(f"Successfully restored electrode: {electrode_name}")
            else:
                logger.debug(f"Electrode {electrode_name} was not in modified state")
            
        except Exception as e:
            logger.error(f"Error handling electrode right click {electrode_name}: {e}")
            self._show_error_message(f"Error restoring electrode: {str(e)}")
    
    def _on_head_circle_click(self, event):
        """Handle head circle clicks with validation."""
        logger.debug("Head circle click detected")
        
        try:
            if event.button() != QtCore.Qt.MouseButton.LeftButton:
                logger.debug("Non-left click ignored")
                return
            
            click_pos = event.pos()
            global_x = click_pos.x() + self.ui.headCircle.x()
            global_y = click_pos.y() + self.ui.headCircle.y()
            
            logger.info(f"Head circle click at global position ({global_x}, {global_y})")
            
            # Validate click location
            if self._is_click_on_existing_electrode(global_x, global_y):
                logger.debug("Click on existing electrode, ignoring")
                return
            
            if not self._is_click_in_head_circle(click_pos.x(), click_pos.y()):
                logger.debug("Click outside head circle, ignoring")
                return
            
            # Process click
            self._process_head_circle_click(global_x-13, global_y-13)
            
        except Exception as e:
            logger.error(f"Error handling head circle click: {e}")
            self._show_error_message(f"Error processing click: {str(e)}")
    
    def _on_monitor_head_circle_click(self, pos_x, pos_y):
        """Handle head circle clicks with validation."""
        logger.debug("monitor Head circle click detected")
        
        try:
            logger.info(f"monitor Head circle click at global position ({pos_x}, {pos_y})")
            
            # Validate click location
            if self._is_click_on_existing_electrode(pos_x, pos_y):
                logger.debug("monitor Click on existing electrode, ignoring")
                return
            
            if not self._is_click_in_head_circle(pos_x, pos_y):
                logger.debug("monitor Click outside head circle, ignoring")
                return
            
            # Process click
            self._process_head_circle_click(pos_x-13, pos_y-13)
            
        except Exception as e:
            logger.error(f"Error handling head circle click: {e}")
            self._show_error_message(f"Error processing click: {str(e)}")
    
    def _process_head_circle_click(self, global_x: int, global_y: int):
        """Process head circle click to create new electrode."""
        logger.info(f"Processing head circle click at ({global_x}, {global_y})")
        
        if not self.current_node_info.is_valid():
            logger.warning("No valid node info set for creating new electrode")
            self._show_error_message("Please select electrode type and number first")
            return
        
        try:
            # Find optimal position based on nearby electrodes
            nearest_electrodes = self._find_nearest_electrodes(global_x, global_y)
            
            if len(nearest_electrodes) < 2:
                logger.warning("Insufficient nearby electrodes for positioning")
                self._create_simple_electrode(global_x+13, global_y+13)
                return
            
            # Try different positioning strategies
            if self._try_aligned_positioning(global_x, global_y, nearest_electrodes):
                return
            
            if len(nearest_electrodes) >= 4:
                if self._try_quadrilateral_positioning(global_x, global_y, nearest_electrodes[:4]):
                    return
            
            # Fallback to simple positioning
            logger.info("Using fallback simple positioning")
            self._create_simple_electrode(global_x, global_y)
            
        except Exception as e:
            logger.error(f"Error processing head circle click: {e}")
            self._show_error_message(f"Error creating electrode: {str(e)}")
    
    def _create_simple_electrode(self, x: int, y: int):
        """Create a simple electrode at the specified position."""
        logger.info(f"Creating simple electrode at ({x}, {y})")
        
        try:
            button_name = f"custom_{x}_{y}"
            self._create_dynamic_electrode(x, y, button_name)
            logger.info(f"Successfully created simple electrode: {button_name}")
            
        except Exception as e:
            logger.error(f"Failed to create simple electrode: {e}")
    
    def _try_aligned_positioning(self, click_x: int, click_y: int, nearest_electrodes: List[str]) -> bool:
        """Try to create electrode at aligned position."""
        logger.debug("Attempting aligned positioning")
        
        try:
            electrode1, electrode2 = nearest_electrodes[0], nearest_electrodes[1]
            alignment, is_near = self._check_electrode_alignment(click_x, click_y, electrode1, electrode2)
            
            if alignment != 0 and is_near:
                logger.info(f"Creating aligned electrode between {electrode1} and {electrode2}")
                self._create_aligned_electrode(electrode1, electrode2)
                return True
            
            logger.debug("No suitable alignment found")
            return False
            
        except Exception as e:
            logger.error(f"Error in aligned positioning: {e}")
            return False
    
    def _try_quadrilateral_positioning(self, click_x: int, click_y: int, electrodes: List[str]) -> bool:
        """Try to create electrode at quadrilateral center."""
        logger.debug("Attempting quadrilateral positioning")
        
        try:
            if self._is_valid_quadrilateral(electrodes, click_x, click_y):
                logger.info(f"Creating quadrilateral electrode for: {electrodes}")
                self._create_quadrilateral_electrode(electrodes)
                return True
            
            logger.debug("Invalid quadrilateral configuration")
            return False
            
        except Exception as e:
            logger.error(f"Error in quadrilateral positioning: {e}")
            return False
    
    def _create_aligned_electrode(self, electrode1: str, electrode2: str):
        """Create electrode at midpoint of two aligned electrodes."""
        logger.info(f"Creating aligned electrode between {electrode1} and {electrode2}")
        
        try:
            positions = self._get_all_electrode_positions()
            pos1, pos2 = positions[electrode1], positions[electrode2]
            
            mid_x = (pos1[0] + pos2[0]) // 2
            mid_y = (pos1[1] + pos2[1]) // 2
            
            button_name = f"{electrode1}_{electrode2}"
            self._create_dynamic_electrode(mid_x, mid_y, button_name)
            
            logger.info(f"Successfully created aligned electrode: {button_name}")
            
        except Exception as e:
            logger.error(f"Failed to create aligned electrode: {e}")
    
    def _create_quadrilateral_electrode(self, electrodes: List[str]):
        """Create electrode at center of quadrilateral."""
        logger.info(f"Creating quadrilateral electrode for: {electrodes}")
        
        try:
            positions = self._get_all_electrode_positions()
            quad_positions = [positions[name] for name in electrodes]
            
            center_x = sum(pos[0] for pos in quad_positions) // 4
            center_y = sum(pos[1] for pos in quad_positions) // 4
            
            button_name = '_'.join(electrodes)
            self._create_dynamic_electrode(center_x, center_y, button_name)
            
            logger.info(f"Successfully created quadrilateral electrode: {button_name}")
            
        except Exception as e:
            logger.error(f"Failed to create quadrilateral electrode: {e}")
    
    def _create_dynamic_electrode(self, x: int, y: int, button_name: str):
        """Create a dynamic electrode button with error handling."""
        logger.info(f"Creating dynamic electrode '{button_name}' at ({x}, {y})")
        
        try:
            # Check for existing nearby electrode
            existing = self._find_existing_electrode_nearby(x, y)
            if existing:
                logger.info(f"Updating existing electrode: {existing}")
                self._update_existing_electrode(existing)
                return
            
            # Create new button
            button = self._create_button_widget(x, y)
            if not button:
                logger.error("Failed to create button widget")
                return
            
            # Configure button
            button.setText(str(self.current_node_info.number))
            if hasattr(self.ui, 'get_style_for_type'):
                button.setStyleSheet(self.ui.get_style_for_type(self.current_node_info.type.value))
            
            # Connect signals
            self._connect_dynamic_button_signals(button, button_name)
            
            # Show button
            button.show()
            
            # Store references
            self.dynamic_buttons[button_name] = button
            
            # Add to electrode manager
            success = self.electrode_manager.add_electrode(
                button_name,
                self.current_node_info.type,
                self.current_node_info.number,
                (x, y)
            )
            
            if success:
                logger.info(f"Successfully created dynamic electrode: {button_name}")
            else:
                logger.error(f"Failed to add dynamic electrode to manager: {button_name}")
                button.deleteLater()
                if button_name in self.dynamic_buttons:
                    del self.dynamic_buttons[button_name]
            
        except Exception as e:
            logger.error(f"Error creating dynamic electrode {button_name}: {e}")
    
    def _create_button_widget(self, x: int, y: int) -> Optional[QtWidgets.QPushButton]:
        """Create button widget with error handling."""
        logger.debug(f"Creating button widget at ({x}, {y})")
        
        try:
            if hasattr(self.ui, 'create_dynamic_button'):
                button = self.ui.create_dynamic_button(self, x, y, "")
                logger.debug("Button created using UI method")
                return button
            else:
                # Fallback button creation
                button = QtWidgets.QPushButton(self)
                button.setGeometry(x, y, 26, 26)
                logger.debug("Button created using fallback method")
                return button
                
        except Exception as e:
            logger.error(f"Failed to create button widget: {e}")
            return None
    
    def _connect_dynamic_button_signals(self, button: QtWidgets.QPushButton, button_name: str):
        """Connect signals for dynamic button with error handling."""
        logger.debug(f"Connecting signals for dynamic button: {button_name}")
        
        try:
            # Left click
            button.clicked.connect(
                lambda checked, name=button_name: self._on_dynamic_button_left_click(name)
            )
            
            # Right click
            button.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda pos, name=button_name: self._on_dynamic_button_right_click(name)
            )
            
            logger.debug(f"Successfully connected signals for: {button_name}")
            
        except Exception as e:
            logger.error(f"Failed to connect signals for dynamic button {button_name}: {e}")
    
    def _find_existing_electrode_nearby(self, x: int, y: int) -> Optional[str]:
        """Find existing electrode near the specified position."""
        logger.debug(f"Searching for existing electrode near ({x}, {y})")
        
        try:
            threshold = self.Config.EXISTING_NODE_THRESHOLD
            
            for name, state in self.electrode_manager.states.items():
                if (state.type == self.current_node_info.type and 
                    state.number == self.current_node_info.number and 
                    state.position is not None):
                    
                    existing_x, existing_y = state.position
                    distance = math.sqrt((x - existing_x)**2 + (y - existing_y)**2)
                    
                    if distance <= threshold:
                        logger.info(f"Found existing electrode {name} nearby (distance: {distance:.1f})")
                        return name
            
            logger.debug("No existing electrode found nearby")
            return None
            
        except Exception as e:
            logger.error(f"Error finding existing electrode: {e}")
            return None
    
    def _update_existing_electrode(self, electrode_name: str):
        """Update existing electrode with current node info."""
        logger.info(f"Updating existing electrode: {electrode_name}")
        
        try:
            success = self.electrode_manager.add_electrode(
                electrode_name,
                self.current_node_info.type,
                self.current_node_info.number,
                self.electrode_manager.get_electrode(electrode_name).position
            )
            
            if success:
                # Update button appearance
                if electrode_name in self.dynamic_buttons:
                    button = self.dynamic_buttons[electrode_name]
                    button.setText(str(self.current_node_info.number))
                    if hasattr(self.ui, 'get_style_for_type'):
                        button.setStyleSheet(self.ui.get_style_for_type(self.current_node_info.type.value))
                else:
                    # Regular electrode
                    button = self.ui.get_electrode_button(electrode_name)
                    if button:
                        self._update_button_appearance(button, self.current_node_info.type, self.current_node_info.number)
                
                logger.info(f"Successfully updated existing electrode: {electrode_name}")
            else:
                logger.error(f"Failed to update electrode in manager: {electrode_name}")
                
        except Exception as e:
            logger.error(f"Error updating existing electrode {electrode_name}: {e}")
    
    def _on_dynamic_button_left_click(self, button_name: str):
        """Handle dynamic button left-click."""
        logger.info(f"Left click on dynamic button: {button_name}")
        
        try:
            if not self.current_node_info.is_valid():
                logger.warning(f"Invalid node info for dynamic button {button_name}")
                self._show_error_message("Please select electrode type and number first")
                return
            
            self._update_existing_electrode(button_name)
            
        except Exception as e:
            logger.error(f"Error handling dynamic button left click {button_name}: {e}")
            self._show_error_message(f"Error updating electrode: {str(e)}")
    
    def _on_dynamic_button_right_click(self, button_name: str):
        """Handle dynamic button right-click - delete electrode."""
        logger.info(f"Right click on dynamic button: {button_name}")
        
        try:
            self._delete_dynamic_electrode(button_name)
            
        except Exception as e:
            logger.error(f"Error handling dynamic button right click {button_name}: {e}")
            self._show_error_message(f"Error deleting electrode: {str(e)}")
    
    def _delete_dynamic_electrode(self, button_name: str):
        """Delete dynamic electrode with cleanup."""
        logger.info(f"Deleting dynamic electrode: {button_name}")
        
        try:
            # Remove button
            if button_name in self.dynamic_buttons:
                button = self.dynamic_buttons[button_name]
                button.deleteLater()
                del self.dynamic_buttons[button_name]
                logger.debug(f"Removed button for: {button_name}")
            
            # Remove from electrode manager
            self.electrode_manager.remove_electrode(button_name)
            
            logger.info(f"Successfully deleted dynamic electrode: {button_name}")
            
        except Exception as e:
            logger.error(f"Error deleting dynamic electrode {button_name}: {e}")
    
    def _on_head_circle_right_click(self, pos):
        """Handle right-click on head circle area."""
        logger.info(f"Right click on head circle at position {pos}")
        
        try:
            # Convert to global coordinates
            global_pos = self.ui.headCircle.mapToGlobal(pos)
            
            # Find dynamic button at position
            for button_name, button in self.dynamic_buttons.items():
                try:
                    button_rect = button.geometry()
                    button_global_pos = button.mapToGlobal(QtCore.QPoint(0, 0))
                    button_global_rect = QtCore.QRect(button_global_pos, button_rect.size())
                    
                    if button_global_rect.contains(global_pos):
                        logger.info(f"Right-click on dynamic button {button_name}, deleting")
                        self._delete_dynamic_electrode(button_name)
                        return
                        
                except Exception as e:
                    logger.error(f"Error checking button {button_name}: {e}")
            
            logger.debug("Right-click not on any dynamic button")
            
        except Exception as e:
            logger.error(f"Error handling head circle right click: {e}")
    
    def _find_nearest_electrodes(self, click_x: int, click_y: int, max_count: int = 6) -> List[str]:
        """Find nearest electrodes to click position."""
        logger.debug(f"Finding nearest electrodes to ({click_x}, {click_y})")
        
        try:
            electrode_positions = self._get_all_electrode_positions()
            distances = []
            
            for name, (ex, ey) in electrode_positions.items():
                distance = math.sqrt((click_x - ex)**2 + (click_y - ey)**2)
                distances.append((distance, name))
                logger.debug(f"Distance to {name}: {distance:.2f}")
            
            # Sort by distance
            distances.sort()
            nearest = [name for _, name in distances[:max_count]]
            
            logger.info(f"Nearest electrodes: {nearest[:3]}...")  # Log first 3
            return nearest
            
        except Exception as e:
            logger.error(f"Error finding nearest electrodes: {e}")
            return []
    
    def _check_electrode_alignment(self, click_x: int, click_y: int, 
                                 electrode1: str, electrode2: str) -> Tuple[int, bool]:
        """Check if electrodes are aligned horizontally or vertically."""
        logger.debug(f"Checking alignment for {electrode1}-{electrode2}")
        
        try:
            positions = self._get_all_electrode_positions()
            pos1, pos2 = positions[electrode1], positions[electrode2]
            
            dx = abs(pos1[0] - pos2[0])
            dy = abs(pos1[1] - pos2[1])
            
            alignment = 0
            is_near = False
            
            # Check horizontal alignment
            if dy <= self.Config.ALIGNMENT_THRESHOLD:
                alignment = 1
                is_near = (abs(click_y - pos1[1]) < self.Config.NEAR_THRESHOLD or 
                          abs(click_y - pos2[1]) < self.Config.NEAR_THRESHOLD)
                logger.debug(f"Horizontal alignment detected: near={is_near}")
            
            # Check vertical alignment
            elif dx <= self.Config.ALIGNMENT_THRESHOLD:
                alignment = -1
                is_near = (abs(click_x - pos1[0]) < self.Config.NEAR_THRESHOLD or 
                          abs(click_x - pos2[0]) < self.Config.NEAR_THRESHOLD)
                logger.debug(f"Vertical alignment detected: near={is_near}")
            
            logger.debug(f"Alignment result: {alignment}, near: {is_near}")
            return alignment, is_near
            
        except Exception as e:
            logger.error(f"Error checking electrode alignment: {e}")
            return 0, False
    
    def _is_valid_quadrilateral(self, electrodes: List[str], click_x: int, click_y: int) -> bool:
        """Validate quadrilateral electrode configuration."""
        logger.debug(f"Validating quadrilateral: {electrodes}")
        
        try:
            if len(electrodes) != 4:
                logger.debug("Invalid electrode count for quadrilateral")
                return False
            
            alignment_sum = 0
            absolute_alignment_sum = 0
            
            # Check all pairs
            for i in range(len(electrodes)):
                for j in range(i + 1, len(electrodes)):
                    name1, name2 = electrodes[i], electrodes[j]
                    alignment, _ = self._check_electrode_alignment(click_x, click_y, name1, name2)
                    
                    alignment_sum += alignment
                    absolute_alignment_sum += abs(alignment)
                    logger.debug(f"Pair {name1}-{name2} alignment: {alignment}")
            
            # Valid quadrilateral has balanced alignments
            is_valid = alignment_sum == 0 and absolute_alignment_sum == 4
            logger.info(f"Quadrilateral validation: valid={is_valid}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error validating quadrilateral: {e}")
            return False
    
    def _is_click_on_existing_electrode(self, x: int, y: int) -> bool:
        """Check if click is on existing electrode."""
        logger.debug(f"Checking if click ({x}, {y}) is on existing electrode")
        
        try:
            # Check regular electrodes
            electrode_positions = self._get_all_electrode_positions()
            for name, (ex, ey) in electrode_positions.items():
                if (ex <= x <= ex + self.Config.ELECTRODE_SIZE and 
                    ey <= y <= ey + self.Config.ELECTRODE_SIZE):
                    logger.debug(f"Click on regular electrode: {name}")
                    return True
            
            # Check dynamic buttons
            for button_name, button in self.dynamic_buttons.items():
                rect = button.geometry()
                if (rect.x() <= x <= rect.x() + rect.width() and 
                    rect.y() <= y <= rect.y() + rect.height()):
                    logger.debug(f"Click on dynamic button: {button_name}")
                    return True
            
            logger.debug("Click not on any existing electrode")
            return False
            
        except Exception as e:
            logger.error(f"Error checking click on electrode: {e}")
            return False
    
    def _is_click_in_head_circle(self, local_x: int, local_y: int) -> bool:
        """Check if click is within head circle."""
        try:
            center_x, center_y = self.Config.HEAD_RADIUS, self.Config.HEAD_RADIUS
            distance = math.sqrt((local_x - center_x)**2 + (local_y - center_y)**2)
            is_inside = distance <= self.Config.HEAD_RADIUS
            
            logger.debug(f"Head circle check: distance={distance:.2f}, "
                        f"radius={self.Config.HEAD_RADIUS}, inside={is_inside}")
            return is_inside
            
        except Exception as e:
            logger.error(f"Error checking head circle bounds: {e}")
            return False
    
    def _get_all_electrode_positions(self) -> Dict[str, Tuple[int, int]]:
        """Get all electrode positions with error handling."""
        logger.debug("Getting all electrode positions")
        
        try:
            if hasattr(self.ui, '_get_electrode_positions'):
                positions = self.ui._get_electrode_positions()
                logger.debug(f"Retrieved {len(positions)} electrode positions")
                return positions
            else:
                logger.warning("UI does not have _get_electrode_positions method")
                return {}
                
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
    
    def _update_button_appearance(self, button: QtWidgets.QPushButton, 
                                electrode_type: ElectrodeType, number: int):
        """Update button appearance with error handling."""
        logger.debug(f"Updating button appearance: type={electrode_type.value}, number={number}")
        
        try:
            button.setText(str(number))
            
            if hasattr(self.ui, 'get_style_for_type'):
                style = self.ui.get_style_for_type(electrode_type.value)
                button.setStyleSheet(style)
                logger.debug("Button style updated")
            else:
                logger.warning("UI does not have get_style_for_type method")
            
        except Exception as e:
            logger.error(f"Error updating button appearance: {e}")
    
    def _show_error_message(self, message: str, title: str = "Error"):
        """Show error message to user."""
        logger.info(f"Showing error message: {message}")
        
        try:
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Warning)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.exec_()
            
        except Exception as e:
            logger.error(f"Failed to show error message: {e}")
    
    def _show_info_message(self, message: str, title: str = "Information"):
        """Show information message to user."""
        logger.info(f"Showing info message: {message}")
        
        try:
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Information)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.exec_()
            
        except Exception as e:
            logger.error(f"Failed to show info message: {e}")
    
    # Public API Methods
    def set_current_node_info(self, electrode_type: Optional[str] = None, 
                            number: int = 0, checked: bool = False):
        """Set current node information with validation."""
        logger.info(f"Setting node info: type={electrode_type}, number={number}, checked={checked}")
        
        try:
            node_type = None
            if electrode_type:
                node_type = ElectrodeType.from_string(electrode_type)
                if node_type is None:
                    logger.error(f"Invalid electrode type: {electrode_type}")
                    self._show_error_message(f"Invalid electrode type: {electrode_type}")
                    return False
            
            self.current_node_info = NodeInfo(type=node_type, number=number, checked=checked)
            logger.info(f"Node info set successfully: {self.current_node_info}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting node info: {e}")
            self._show_error_message(f"Error setting node info: {str(e)}")
            return False
    
    def load_pairs_info(self, node_pairs: Dict):
        """Load electrode pairs with validation."""
        logger.info(f"Loading pairs info: {list(node_pairs.keys())}")
        
        try:
            # Reset current state
            self.reset_all_electrodes()
            
            # Update channel calculator positions
            self._update_position_data()
            
            # Process each electrode type
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
            
            # Load button appearances
            self._load_electrode_buttons()
            
            logger.info("Pairs info loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading pairs info: {e}")
            self._show_error_message(f"Error loading electrode data: {str(e)}")
    
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
    
    def _load_fnirs_electrodes(self):
        """Load fNIRS electrodes from pairs data."""
        logger.info("Loading fNIRS electrodes")
        
        positions = self._get_all_electrode_positions()
        try:
            for channel_name, channel_info in self.fnirs_node_pairs.items():
                # node_pair = channel_info.get('node_pair', '')
                
                if '-' not in channel_info:
                    logger.warning(f"Invalid node pair format: {channel_info}")
                    continue
                
                source_node, detector_node = channel_info.split('-')
                
                # Extract numbers from channel name (e.g., 'S1-D2')
                try:
                    parts = channel_name.split('-')
                    source_num = int(parts[0][1:])  # Remove 'S' prefix
                    detector_num = int(parts[1][1:])  # Remove 'D' prefix
                    
                    # Add source electrode
                    self.set_current_node_info('Source', source_num, True)
                    
                    if '_' in source_node:
                        source_node_pairs = source_node.split('_')
                        quad_positions = [positions[name] for name in source_node_pairs]
                        source_x = sum(pos[0] for pos in quad_positions) // len(source_node_pairs)
                        source_y = sum(pos[1] for pos in quad_positions) // len(source_node_pairs)
                        logger.debug(f"monitoring clicked position, {source_node_pairs[0]}, {source_node_pairs[1]}, {source_x}, {source_y}, {len(source_node_pairs)}")
                        self._on_monitor_head_circle_click(source_x + 13, source_y + 13)
                    else:
                        self._on_electrode_left_click(source_node)
                    
                    # Add detector electrode
                    self.set_current_node_info('Detect', detector_num, True)
                    if '_' in detector_node:
                        detect_node_pairs = detector_node.split('_')
                        quad_positions = [positions[name] for name in detect_node_pairs]
                        detecy_x = sum(pos[0] for pos in quad_positions) // len(detect_node_pairs)
                        detecy_y = sum(pos[1] for pos in quad_positions) // len(detect_node_pairs)
                        logger.debug(f"monitoring clicked position, {detect_node_pairs[0]}, {detect_node_pairs[1]}, {detecy_x}, {detecy_y}, {len(detect_node_pairs)}")
                        self._on_monitor_head_circle_click(detecy_x + 13, detecy_y + 13)
                    else:
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
                
                # Extract number from channel name (e.g., 'EEG1')
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
    
    def _load_electrode_buttons(self):
        """Load button appearances for all electrodes."""
        logger.info("Loading electrode button appearances")
        
        try:
            loaded_count = 0
            
            for name, state in self.electrode_manager.states.items():
                try:
                    if '_' in name:
                        # Dynamic electrode
                        self._create_dynamic_electrode_from_state(name, state)
                    else:
                        # Regular electrode
                        button = self.ui.get_electrode_button(name)
                        if button:
                            self._update_button_appearance(button, state.type, state.number)
                            loaded_count += 1
                        else:
                            logger.warning(f"Button not found for electrode: {name}")
                            
                except Exception as e:
                    logger.error(f"Error loading button for {name}: {e}")
            
            logger.info(f"Loaded {loaded_count} electrode button appearances")
            
        except Exception as e:
            logger.error(f"Error loading electrode buttons: {e}")
    
    def _create_dynamic_electrode_from_state(self, name: str, state: ElectrodeState):
        """Create dynamic electrode from saved state."""
        logger.debug(f"Creating dynamic electrode from state: {name}")
        
        try:
            if not state.position:
                logger.error(f"No position data for dynamic electrode: {name}")
                return
            
            x, y = state.position
            button = self._create_button_widget(x, y)
            
            if button:
                button.setText(str(state.number))
                if hasattr(self.ui, 'get_style_for_type'):
                    button.setStyleSheet(self.ui.get_style_for_type(state.type.value))
                
                self._connect_dynamic_button_signals(button, name)
                button.show()
                
                self.dynamic_buttons[name] = button
                logger.debug(f"Successfully created dynamic electrode: {name}")
            else:
                logger.error(f"Failed to create button for dynamic electrode: {name}")
                
        except Exception as e:
            logger.error(f"Error creating dynamic electrode from state {name}: {e}")
    
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
                        button.setText(name)
                        if hasattr(self.ui, 'get_style_for_type'):
                            button.setStyleSheet(self.ui.get_style_for_type('default'))
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
            self._show_error_message(f"Error resetting electrodes: {str(e)}")
    
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
            self._show_error_message(f"Error calculating channels: {str(e)}")
            return {}
    
    def get_channel_pairs_summary(self):
        """Get and display channel pairs summary."""
        logger.info("Generating channel pairs summary")
        
        try:
            summary = self.calculate_channel_pairs()
            
            if not summary:
                logger.warning("No summary data available")
                self._show_error_message("Failed to calculate channel summary")
                return
            
            # Format summary message
            summary_text = (
                f"Sources: {summary['sources']}\n"
                f"Detectors: {summary['detectors']}\n"
                f"EEG Channels: {summary['eeg_channels']}\n"
                f"Valid fNIRS Channels: {summary['fnirs_channels']}\n\n"
                f"fNIRS Pairs:\n{self._format_pairs_list(summary['valid_fnirs_pairs'])}\n\n"
                f"EEG Pairs:\n{self._format_pairs_list(summary['eeg_pairs'])}"
            )
            
            logger.info("Displaying channel summary to user")
            self._show_info_message(summary_text, "Channel Configuration Summary")
            
        except Exception as e:
            logger.error(f"Error generating channel summary: {e}")
            self._show_error_message(f"Error generating summary: {str(e)}")
    
    def _format_pairs_list(self, pairs_list: List[str], max_display: int = 10) -> str:
        """Format pairs list for display."""
        if not pairs_list:
            return "None"
        
        if len(pairs_list) <= max_display:
            return ', '.join(pairs_list)
        else:
            displayed = ', '.join(pairs_list[:max_display])
            return f"{displayed}\n... and {len(pairs_list) - max_display} more"


class TestControlWidget(QtWidgets.QFrame):
    """Enhanced test control widget with better error handling."""
    
    def __init__(self, locator: Locate):
        super().__init__()
        self.locator = locator
        logger.info("Initializing TestControlWidget")
        
        try:
            self.setup_ui()
            logger.info("TestControlWidget initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TestControlWidget: {e}")
            raise
    
    def setup_ui(self):
        """Setup the test control UI with improved layout."""
        logger.debug("Setting up TestControlWidget UI")
        
        try:
            self.setGeometry(QtCore.QRect(10, 10, 240, 140))
            self.setStyleSheet(
                "QFrame { background-color: lightgray; border: 2px solid black; border-radius: 5px; }"
                "QPushButton { background-color: white; border: 1px solid gray; border-radius: 3px; }"
                "QPushButton:hover { background-color: lightblue; }"
                "QPushButton:pressed { background-color: darkgray; }"
            )
            
            # Create layout
            layout = QtWidgets.QVBoxLayout(self)
            layout.setSpacing(5)
            layout.setContentsMargins(5, 5, 5, 5)
            
            # Mode selection row
            mode_row = QtWidgets.QHBoxLayout()
            
            self.source_btn = QtWidgets.QPushButton("Source")
            self.source_btn.clicked.connect(lambda: self._set_mode(ElectrodeType.SOURCE.value))
            mode_row.addWidget(self.source_btn)
            
            self.detector_btn = QtWidgets.QPushButton("Detector")
            self.detector_btn.clicked.connect(lambda: self._set_mode(ElectrodeType.DETECT.value))
            mode_row.addWidget(self.detector_btn)
            
            self.eeg_btn = QtWidgets.QPushButton("EEG")
            self.eeg_btn.clicked.connect(lambda: self._set_mode(ElectrodeType.EEG.value))
            mode_row.addWidget(self.eeg_btn)
            
            layout.addLayout(mode_row)
            
            # Number input row
            number_row = QtWidgets.QHBoxLayout()
            
            number_label = QtWidgets.QLabel("Number:")
            number_row.addWidget(number_label)
            
            self.num_input = QtWidgets.QSpinBox()
            self.num_input.setRange(1, 999)
            self.num_input.setValue(1)
            self.num_input.valueChanged.connect(self._update_number)
            number_row.addWidget(self.num_input)
            
            layout.addLayout(number_row)
            
            # Control buttons row 1
            control_row1 = QtWidgets.QHBoxLayout()
            
            self.reset_btn = QtWidgets.QPushButton("Reset All")
            self.reset_btn.clicked.connect(self._safe_reset)
            control_row1.addWidget(self.reset_btn)
            
            self.clear_btn = QtWidgets.QPushButton("Clear Selection")
            self.clear_btn.clicked.connect(self._clear_selection)
            control_row1.addWidget(self.clear_btn)
            
            layout.addLayout(control_row1)
            
            # Control buttons row 2
            control_row2 = QtWidgets.QHBoxLayout()
            
            self.summary_btn = QtWidgets.QPushButton("Show Summary")
            self.summary_btn.clicked.connect(self._safe_show_summary)
            control_row2.addWidget(self.summary_btn)
            
            self.calculate_btn = QtWidgets.QPushButton("Calculate Pairs")
            self.calculate_btn.clicked.connect(self._safe_calculate_pairs)
            control_row2.addWidget(self.calculate_btn)
            
            layout.addLayout(control_row2)
            
            # Status label
            self.status_label = QtWidgets.QLabel("Ready")
            self.status_label.setStyleSheet("QLabel { background-color: white; padding: 2px; }")
            layout.addWidget(self.status_label)
            
            logger.debug("TestControlWidget UI setup completed")
            
        except Exception as e:
            logger.error(f"Error setting up TestControlWidget UI: {e}")
            raise
    
    def _set_mode(self, electrode_type: str):
        """Set electrode mode with error handling."""
        logger.info(f"Setting mode to: {electrode_type}")
        
        try:
            success = self.locator.set_current_node_info(
                electrode_type, 
                self.num_input.value(), 
                True
            )
            
            if success:
                self.status_label.setText(f"Mode: {electrode_type} #{self.num_input.value()}")
                logger.info(f"Mode set successfully: {electrode_type} #{self.num_input.value()}")
            else:
                self.status_label.setText("Error setting mode")
                logger.error("Failed to set mode")
                
        except Exception as e:
            logger.error(f"Error setting mode {electrode_type}: {e}")
            self.status_label.setText("Mode error")
    
    def _update_number(self, value: int):
        """Update number with current mode maintained."""
        logger.debug(f"Updating number to: {value}")
        
        try:
            current_info = self.locator.current_node_info
            if current_info.type and current_info.checked:
                success = self.locator.set_current_node_info(
                    current_info.type.value, 
                    value, 
                    True
                )
                
                if success:
                    self.status_label.setText(f"Mode: {current_info.type.value} #{value}")
                    logger.debug(f"Number updated successfully: {value}")
                else:
                    logger.error("Failed to update number")
            else:
                self.status_label.setText("Select mode first")
                logger.debug("No active mode for number update")
                
        except Exception as e:
            logger.error(f"Error updating number: {e}")
            self.status_label.setText("Update error")
    
    def _clear_selection(self):
        """Clear current selection."""
        logger.info("Clearing selection")
        
        try:
            success = self.locator.set_current_node_info(None, 0, False)
            if success:
                self.status_label.setText("Selection cleared")
                logger.info("Selection cleared successfully")
            else:
                self.status_label.setText("Clear failed")
                logger.error("Failed to clear selection")
                
        except Exception as e:
            logger.error(f"Error clearing selection: {e}")
            self.status_label.setText("Clear error")
    
    def _safe_reset(self):
        """Safely reset all electrodes."""
        logger.info("Executing safe reset")
        
        try:
            self.locator.reset_all_electrodes()
            self.status_label.setText("Reset complete")
            logger.info("Reset completed successfully")
            
        except Exception as e:
            logger.error(f"Error during reset: {e}")
            self.status_label.setText("Reset error")
    
    def _safe_show_summary(self):
        """Safely show channel summary."""
        logger.info("Showing summary")
        
        try:
            self.locator.get_channel_pairs_summary()
            self.status_label.setText("Summary shown")
            logger.info("Summary displayed successfully")
            
        except Exception as e:
            logger.error(f"Error showing summary: {e}")
            self.status_label.setText("Summary error")
    
    def _safe_calculate_pairs(self):
        """Safely calculate channel pairs."""
        logger.info("Calculating channel pairs")
        
        try:
            summary = self.locator.calculate_channel_pairs()
            if summary:
                pair_count = summary.get('fnirs_channels', 0) + summary.get('eeg_channels', 0)
                self.status_label.setText(f"Calculated: {pair_count} pairs")
                logger.info(f"Calculation completed: {pair_count} total pairs")
            else:
                self.status_label.setText("Calculation failed")
                logger.error("Channel pair calculation failed")
                
        except Exception as e:
            logger.error(f"Error calculating pairs: {e}")
            self.status_label.setText("Calc error")


def main():
    """Enhanced main function with comprehensive error handling."""
    logger.info("Starting EEG Electrode Interface application")
    
    # Set up application
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("EEG Electrode Interface")
    app.setApplicationVersion("2.0")
    
    # Set application style
    try:
        app.setStyle('Fusion')  # Modern look
        logger.info("Application style set to Fusion")
    except Exception as e:
        logger.warning(f"Could not set application style: {e}")
    
    try:
        # Create main window
        logger.info("Creating main application window")
        locator = Locate()
        
        # Add test control widget
        logger.info("Adding test control widget")
        test_widget = TestControlWidget(locator)
        test_widget.setParent(locator)
        
        # Show window
        locator.show()
        logger.info("Application window displayed")
        
        # Set window properties
        locator.setWindowTitle("EEG Electrode Interface v2.0")
        locator.setMinimumSize(800, 600)
        
        logger.info("Application started successfully")
        
        # Start event loop
        exit_code = app.exec_()
        logger.info(f"Application exited with code: {exit_code}")
        sys.exit(exit_code)
        
    except ImportError as e:
        error_msg = f"Missing required module: {e}"
        logger.critical(error_msg)
        
        # Show error dialog if possible
        try:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Critical)
            msg.setWindowTitle("Import Error")
            msg.setText(error_msg)
            msg.exec_()
        except:
            print(error_msg)
        
        sys.exit(1)
        
    except Exception as e:
        error_msg = f"Critical application error: {e}"
        logger.critical(error_msg)
        
        # Show error dialog if possible
        try:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Critical)
            msg.setWindowTitle("Application Error")
            msg.setText(error_msg)
            msg.setDetailedText(str(e))
            msg.exec_()
        except:
            print(error_msg)
        
        sys.exit(1)


if __name__ == "__main__":
    main()