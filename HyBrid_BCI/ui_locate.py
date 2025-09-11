# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui, QtWidgets
import logging

logger = logging.getLogger(__name__)

class Ui_Locate(object):
    """UI class for EEG Electrode Interface with improved organization and consistency."""
    
    # Constants for better maintainability
    ELECTRODE_SIZE = 26
    HEAD_CIRCLE_SIZE = 480
    HEAD_CIRCLE_OFFSET = 40
    
    def __init__(self):
        self.dynamic_buttons = []
        
    def setupUi(self, Form):
        """Setup the main UI components."""
        logger.info("Setting up UI components")
        
        Form.setObjectName("Form")
        Form.resize(564, 580)
        Form.setWindowTitle("EEG Electrode Interface")
        
        # Create components in logical order
        self._create_head_circle(Form)
        self._create_electrodes(Form)
        
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
        self.headCircle.setStyleSheet(self._get_head_style())
        self.headCircle.setText("")
        self.headCircle.setObjectName("headCircle")
        
        logger.debug("Head circle created successfully")
    
    def _create_electrodes(self, Form):
        """Create all electrode buttons using position data."""
        logger.info("Creating electrode buttons")
        
        electrode_positions = self._get_electrode_positions()
        created_count = 0
        
        for name, (x, y) in electrode_positions.items():
            try:
                button = QtWidgets.QPushButton(Form)
                button.setGeometry(QtCore.QRect(x, y, self.ELECTRODE_SIZE, self.ELECTRODE_SIZE))
                button.setStyleSheet(self._get_electrode_style())
                button.setText(name)
                button.setObjectName(f"electrode_{name}")
                
                # Store reference to button using the electrode name
                setattr(self, f"electrode_{name}", button)
                created_count += 1
                
            except Exception as e:
                logger.error(f"Failed to create electrode {name}: {e}")
        
        logger.info(f"Successfully created {created_count} electrode buttons")
    
    def _get_head_style(self):
        """Return CSS style for the head circle."""
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
    
    def _get_electrode_style(self):
        """Return CSS style for default electrode buttons."""
        return """
            QPushButton {
                border: 2px solid rgba(0, 0, 0, 1);
                border-radius: 13px;
                background-color: transparent;
                color: gray;
                font: bold 12px;
                min-width: 10px;
                min-height: 10px;
                max-width: 40px;
                max-height: 40px;
            }
            QPushButton:hover {
                background-color: rgba(200, 200, 200, 0.3);
            }
        """
    
    def _get_source_electrode_style(self):
        """Return CSS style for source electrode buttons."""
        return """
            QPushButton {
                border: 2px solid rgba(255, 0, 0, 1);
                border-radius: 13px;
                background-color: rgba(255, 0, 0, 0.3);
                color: red;
                font: bold 12px;
                min-width: 10px;
                min-height: 10px;
                max-width: 40px;
                max-height: 40px;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 0.5);
            }
        """
    
    def _get_detector_electrode_style(self):
        """Return CSS style for detector electrode buttons."""
        return """
            QPushButton {
                border: 2px solid rgba(0, 0, 255, 1);
                border-radius: 13px;
                background-color: rgba(0, 0, 255, 0.3);
                color: blue;
                font: bold 12px;
                min-width: 10px;
                min-height: 10px;
                max-width: 40px;
                max-height: 40px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 255, 0.5);
            }
        """
    
    def _get_eeg_electrode_style(self):
        """Return CSS style for EEG electrode buttons."""
        return """
            QPushButton {
                border: 2px solid rgba(0, 255, 0, 1);
                border-radius: 13px;
                background-color: rgba(0, 255, 0, 0.3);
                color: green;
                font: bold 12px;
                min-width: 10px;
                min-height: 10px;
                max-width: 40px;
                max-height: 40px;
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 0, 0.5);
            }
        """
    
    def _get_dynamic_button_style(self):
        """Return CSS style for dynamically created buttons."""
        return """
            QPushButton {
                border: 2px solid rgba(128, 0, 128, 1);
                border-radius: 13px;
                background-color: rgba(128, 0, 128, 0.3);
                color: purple;
                font: bold 10px;
                min-width: 10px;
                min-height: 10px;
                max-width: 60px;
                max-height: 40px;
            }
            QPushButton:hover {
                background-color: rgba(128, 0, 128, 0.5);
            }
        """
    
    def _get_electrode_positions(self):
        """Return dictionary mapping electrode names to (x, y) positions."""
        return {
            # Midline electrodes (center vertical line)
            'FPz': (267,  27),  'AFz':(267,  87),  'Fz': (267, 147),
            'FCz': (267, 207),  'Cz': (267, 267), 'CPz': (267, 327),
             'Pz': (267, 387), 'POz': (267, 447),  'Oz': (267, 507),
            
            # Left hemisphere electrodes
            'AF7': (134, 67),                     'AF3': (200,  82), 'Fp1': (199,  39), 
             'F7': ( 76, 121),  'F5': (114, 132),  'F3': (164, 141),  'F1': (214, 146),
            'FT7': ( 39, 196), 'FC5': ( 94, 200), 'FC3': (149, 204), 'FC1': (209, 206),
             'T7': ( 27, 267),  'C5': ( 87, 267),  'C3': (147, 267),  'C1': (207, 267),
            'TP7': ( 40, 340), 'CP5': ( 94, 334), 'CP3': (149, 330), 'CP1': (209, 328),
             'P7': ( 76, 413),  'P5': (114, 402),  'P3': (164, 393),  'P1': (214, 388),
            'PO7': (134, 467),                    'PO3': (200, 452),  'O1': (199, 496),
            
            # Right hemisphere electrodes
            'AF8': (400,  67),                    'AF4': (334,  82), 'Fp2': (335,  39),
             'F8': (458, 121),  'F6': (420, 132),  'F4': (370, 141),  'F2': (320, 146),
            'FT8': (495, 196), 'FC6': (440, 200), 'FC4': (385, 204), 'FC2': (325, 206),
             'T8': (507, 267),  'C6': (447, 267),  'C4': (387, 267),  'C2': (327, 267),
            'TP8': (495, 340), 'CP6': (440, 334), 'CP4': (385, 330), 'CP2': (325, 328),
             'P8': (458, 413),  'P6': (420, 402),  'P4': (370, 393),  'P2': (320, 388),
            'PO8': (400, 467),                    'PO4': (334, 452),  'O2': (335, 496),
        }
    
    def _get_electrode_3d_positions(self):
        """Return dictionary mapping electrode names to (x, y, z) 3D positions."""
        return {
            # Midline electrodes (center vertical line)
            'FPz': (  0,  87, -3), 'AFz': (  0,  82, 31),  'Fz': (  0,  63, 61),
            'FCz': (  0,  34, 81),  'Cz': (  0,   0, 88), 'CPz': (  0, -34, 81),
             'Pz': (  0, -63, 61), 'POz': (  0, -82, 31),  'Oz': (  0, -87, -3),
            
            # Left hemisphere electrodes
            'AF7': (-51,  71, -3),                        'AF3': (-36,  76, 24), 'Fp1': (-27,  83, -3), 
             'F7': (-71,  51, -3),  'F5': (-64,  55, 23),  'F3': (-48,  59, 44),  'F1': (-25,  62, 56),
            'FT7': (-83,  27, -3), 'FC5': (-78,  30, 27), 'FC3': (-59,  31, 56), 'FC1': (-33,  33, 74),
             'T7': (-87,   0, -3),  'C5': (-82,   0, 31),  'C3': (-63,   0, 61),  'C1': (-34,   0, 81),
            'TP7': (-83, -27, -3), 'CP5': (-78, -30, 27), 'CP3': (-59, -31, 56), 'CP1': (-33, -33, 74),
             'P7': (-71, -51, -3),  'P5': (-64, -55, 23),  'P3': (-48, -59, 44),  'P1': (-25, -62, 56),
            'PO7': (-51, -71, -3),                        'PO3': (-36, -76, 24),  'O1': (-27, -83, -3),
            
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
    
    def get_electrode_button(self, electrode_name):
        """Get electrode button by name for easy access."""
        button = getattr(self, f"electrode_{electrode_name}", None)
        if button is None:
            logger.warning(f"Electrode button '{electrode_name}' not found")
        return button
    
    def get_all_electrode_names(self):
        """Get list of all electrode names."""
        return list(self._get_electrode_positions().keys())
    
    def create_dynamic_button(self, parent, x, y, text):
        """Create a dynamic button at specified position."""
        logger.debug(f"Creating dynamic button '{text}' at position ({x}, {y})")
        
        try:
            button = QtWidgets.QPushButton(parent)
            button.setGeometry(QtCore.QRect(x, y, self.ELECTRODE_SIZE, self.ELECTRODE_SIZE))
            button.setStyleSheet(self._get_dynamic_button_style())
            button.setText(text)
            button.setObjectName(f"dynamic_{text}")
            
            self.dynamic_buttons.append(button)
            logger.debug(f"Dynamic button '{text}' created successfully")
            return button
            
        except Exception as e:
            logger.error(f"Failed to create dynamic button '{text}': {e}")
            return None
    
    def get_style_for_type(self, electrode_type):
        """Get appropriate style for electrode type."""
        style_map = {
            'Source': self._get_source_electrode_style,
            'Detect': self._get_detector_electrode_style,
            'eeg': self._get_eeg_electrode_style,
            'default': self._get_electrode_style
        }
        
        style_func = style_map.get(electrode_type, style_map['default'])
        return style_func()
    
    def retranslateUi(self, Form):
        """Handle UI translation (placeholder for internationalization)."""
        pass