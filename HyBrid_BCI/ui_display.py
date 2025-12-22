# -*- coding: utf-8 -*-

"""
Optimized UI Display Module for Signal Processing and Data Visualization
This module provides a clean, well-structured UI for multi-modal signal processing
including EEG, sEMG, and fNIRS signals with dict-based parameter management.
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from class_info import SensorTypes
    

class Ui_DisplayWidget(object):
    """UI class for the Display Widget - handles only UI setup and styling"""
    
    def __init__(self, sensor_type=SensorTypes.FNIRS):
        """初始化UI类"""
        self.sensor_type = SensorTypes.get_active_signals(sensor_type)  # 默认为fNIRS
        self.signal_configs = {}
        self._init_signal_configs()
        self._init_filter_widgets()
        
    def _init_signal_configs(self):
        """初始化信号配置字典"""
        for types in self.sensor_type:
            if types == 'eeg':
                self.signal_configs[types] = {
                    'label': 'EEG',
                    'chinese_label': 'EEG',
                    'freq_range': (0.1, 100.0),
                    'freq_defaults': (1.0, 30.0),
                    'freq_step': 0.1,
                    'freq_decimals': 3,
                    'order_default': 4,
                    'window_default': 11,
                    'enabled': False
                }
            elif types == 'semg':
                self.signal_configs[types] = {
                    'label': 'sEMG',
                    'chinese_label': 'sEMG',
                    'freq_range': (1.0, 500.0),
                    'freq_defaults': (20.0, 250.0),
                    'freq_step': 1.0,
                    'freq_decimals': 1,
                    'order_default': 4,
                    'window_default': 11,
                    'enabled': False
                }
            elif types == 'fnirs':
                self.signal_configs[types] = {
                    'label': 'fNIRS',
                    'chinese_label': 'fNIRS',
                    'freq_range': (0.01, 10.0),
                    'freq_defaults': (0.01, 0.5),
                    'freq_step': 0.01,
                    'freq_decimals': 3,
                    'order_default': 4,
                    'window_default': 11,
                    'enabled': False
                }
        
        self.filter_types = ["低通滤波", "高通滤波", "带通滤波", "S-G滤波", "平滑滤波"]
        self.signal_types = ["原始光强", "光密度OD", "血红蛋白浓度"]
        
    def _init_filter_widgets(self):
        """初始化滤波器组件字典"""
        self.filter_widgets = {}
        
    def setupUi(self, DisplayWidget):
        """Main UI setup method"""
        self.mainWidget = DisplayWidget
        self._setup_main_window(DisplayWidget)
        self._create_layouts()
        self._setup_control_panel()
        self._setup_settings_panel()
        self._setup_plot_panel()
        self._setup_translations()
        self._configure_initial_states()
        
        QtCore.QMetaObject.connectSlotsByName(DisplayWidget)

    def _setup_main_window(self, DisplayWidget):
        """Configure main window properties"""
        DisplayWidget.setObjectName("DisplayWidget")
        DisplayWidget.resize(1245, 850)
        DisplayWidget.setMinimumSize(QtCore.QSize(1000, 700))
        DisplayWidget.setWindowTitle("Signal Processing and Data Visualization")
        
    def _create_layouts(self):
        """Create main layout structure"""
        self.mainLayout = QtWidgets.QVBoxLayout()
        self.mainLayout.setContentsMargins(2, 2, 2, 2)
        self.mainLayout.setSpacing(2)
        self.mainLayout.setObjectName("mainLayout")

    def _setup_control_panel(self):
        """Setup the control panel with buttons and signal type selection"""
        self.controlGroup = QtWidgets.QGroupBox()
        self.controlGroup.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.controlGroup.setObjectName("controlGroup")
        
        self.controlLayout = QtWidgets.QHBoxLayout(self.controlGroup)
        self.controlLayout.setContentsMargins(2, 2, 2, 2)
        self.controlLayout.setSpacing(2)
        
        # Control buttons
        self._create_control_buttons()
        
        # Add horizontal spacer
        spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.controlLayout.addItem(spacer)
        
        self._create_ylim_spinbox()
        # Add horizontal spacer
        spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.controlLayout.addItem(spacer)
        
        # Filter enable checkboxes
        self._create_filter_checkboxes()
        
        # Signal type selection
        self._create_signal_type_selection()
        
        self.mainLayout.addWidget(self.controlGroup)

    def _create_control_buttons(self):
        """Create control buttons (Start, Reset, Record, Stop, Save)"""
        self.startButton = QtWidgets.QPushButton("开始")
        self.startButton.setObjectName("startButton")
        self.startButton.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.startButton.setToolTip("Start data acquisition")
        self.startButton.setEnabled(True)
        self.startButton.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.controlLayout.addWidget(self.startButton)
        
        self.resetButton = QtWidgets.QPushButton("复位")
        self.resetButton.setObjectName("resetButton")
        self.resetButton.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.resetButton.setToolTip("Reset system and clear all data")
        self.resetButton.setEnabled(False)
        self.resetButton.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.controlLayout.addWidget(self.resetButton)
        
        self.recordButton = QtWidgets.QPushButton("记录")
        self.recordButton.setObjectName("recordButton")
        self.recordButton.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.recordButton.setToolTip("Toggle data recording")
        self.recordButton.setEnabled(False)
        self.recordButton.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.controlLayout.addWidget(self.recordButton)
        
        self.stopButton = QtWidgets.QPushButton("结束")
        self.stopButton.setObjectName("stopButton")
        self.stopButton.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.stopButton.setToolTip("Stop data acquisition")
        self.stopButton.setEnabled(False)
        self.stopButton.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.controlLayout.addWidget(self.stopButton)
        
    def _create_ylim_spinbox(self):
        self.ylimlabel = QtWidgets.QLabel("Y轴范围:")
        self.ylimlabel.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.controlLayout.addWidget(self.ylimlabel)
        
        self.fnirs_spinbox = QtWidgets.QSpinBox()
        self.fnirs_spinbox.setRange(0, 5000)
        self.fnirs_spinbox.setValue(10)
        self.controlLayout.addWidget(self.fnirs_spinbox)

    def _create_filter_checkboxes(self):
        """Create filter enable checkboxes"""
        filter_layout = QtWidgets.QHBoxLayout()
        
        self.filterEnableLabel = QtWidgets.QLabel("开启滤波：")
        filter_layout.addWidget(self.filterEnableLabel)
        
        # 创建复选框字典
        self.filter_checkboxes = {}
        for signal_key, config in self.signal_configs.items():
            checkbox = QtWidgets.QCheckBox(config['chinese_label'])
            checkbox.setObjectName(f"{signal_key}CheckBox")
            checkbox.setChecked(config['enabled'])
            self.filter_checkboxes[signal_key] = checkbox
            filter_layout.addWidget(checkbox)
        
        self.controlLayout.addLayout(filter_layout)

    def _create_signal_type_selection(self):
        """Create signal type selection combo box"""
        signal_layout = QtWidgets.QHBoxLayout()
        
        self.signalTypeLabel = QtWidgets.QLabel("信号类型:")
        self.signalTypeLabel.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        signal_layout.addWidget(self.signalTypeLabel)
        
        self.signalTypeCombo = QtWidgets.QComboBox()
        self.signalTypeCombo.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.signalTypeCombo.setToolTip("Select signal type for processing")
        self.signalTypeCombo.addItems(self.signal_types)
        signal_layout.addWidget(self.signalTypeCombo)
        
        self.controlLayout.addLayout(signal_layout)

    def _setup_settings_panel(self):
        """Setup the settings panel with filter configurations"""
        self.settingsGroup = QtWidgets.QGroupBox()
        self.settingsGroup.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.settingsGroup.setObjectName("settingsGroup")
        
        self.settingsLayout = QtWidgets.QHBoxLayout(self.settingsGroup)
        self.settingsLayout.setContentsMargins(2, 2, 2, 2)
        self.settingsLayout.setSpacing(2)
        
        # Create filter settings for each signal type
        for signal_key in self.signal_configs.keys():
            self._create_filter_settings(signal_key)
            self._add_spacer()
        
        # Apply button
        self._add_spacer()
        self.applyButton = QtWidgets.QPushButton("完成")
        self.applyButton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        self.applyButton.setObjectName("applyButton")
        self.settingsLayout.addWidget(self.applyButton)
        
        self.mainLayout.addWidget(self.settingsGroup)

    def _create_filter_settings(self, signal_key):
        """Create filter settings for a specific signal type"""
        config = self.signal_configs[signal_key]
        filter_layout = QtWidgets.QHBoxLayout()
        
        # 为每个信号类型创建组件字典
        self.filter_widgets[signal_key] = {}
        
        # Main filter layout
        main_layout = QtWidgets.QHBoxLayout()
        # self.filter_widgets[signal_key]['main_layout'] = main_layout
        
        # Label and combo
        label = QtWidgets.QLabel(f"{config['chinese_label']}:")
        label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.filter_widgets[signal_key]['label'] = label
        main_layout.addWidget(label)
        
        combo = QtWidgets.QComboBox()
        combo.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        combo.setToolTip("Choose filter method")
        combo.addItems(self.filter_types)
        self.filter_widgets[signal_key]['filter_combo'] = combo
        main_layout.addWidget(combo)
        
        filter_layout.addLayout(main_layout)
        
        # Parameters layout
        params_layout = QtWidgets.QHBoxLayout()
        
        # Frequency parameters
        freq1_spin = QtWidgets.QDoubleSpinBox()
        freq1_spin.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        freq1_spin.setRange(*config['freq_range'])
        freq1_spin.setSingleStep(config['freq_step'])
        freq1_spin.setValue(config['freq_defaults'][0])
        freq1_spin.setDecimals(config['freq_decimals'])
        freq1_spin.setSuffix(" Hz")
        self.filter_widgets[signal_key]['freq1_spin'] = freq1_spin
        params_layout.addWidget(freq1_spin)
        freq1_spin.setVisible(combo.currentText() in ["低通滤波", "带通滤波"])
        
        freq2_spin = QtWidgets.QDoubleSpinBox()
        freq2_spin.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        freq2_spin.setRange(*config['freq_range'])
        freq2_spin.setSingleStep(config['freq_step'])
        freq2_spin.setValue(config['freq_defaults'][1])
        freq2_spin.setDecimals(config['freq_decimals'])
        freq2_spin.setSuffix(" Hz")
        self.filter_widgets[signal_key]['freq2_spin'] = freq2_spin
        params_layout.addWidget(freq2_spin)
        freq2_spin.setVisible(combo.currentText() in ["高通滤波", "带通滤波"])
        
        # Order
        order_label = QtWidgets.QLabel("阶数:")
        order_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.filter_widgets[signal_key]['order_label'] = order_label
        params_layout.addWidget(order_label)
        order_label.setVisible(combo.currentText() in ["低通滤波", "高通滤波", "带通滤波"])
        
        order_spin = QtWidgets.QSpinBox()
        order_spin.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        order_spin.setRange(1, 10)
        order_spin.setValue(config['order_default'])
        order_spin.setToolTip("Filter order (higher = steeper cutoff)")
        self.filter_widgets[signal_key]['order_spin'] = order_spin
        params_layout.addWidget(order_spin)
        order_spin.setVisible(combo.currentText() in ["低通滤波", "高通滤波", "带通滤波"])
        
        filter_layout.addLayout(params_layout)
        
        # Window size layout
        window_layout = QtWidgets.QHBoxLayout()
        
        window_label = QtWidgets.QLabel("窗口值:")
        window_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.filter_widgets[signal_key]['window_label'] = window_label
        window_layout.addWidget(window_label)
        window_label.setVisible(combo.currentText() in ["S-G滤波", "平滑滤波"])
        
        window_spin = QtWidgets.QSpinBox()
        window_spin.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        window_spin.setRange(3, 101)
        window_spin.setSingleStep(2)
        window_spin.setValue(config['window_default'])
        window_spin.setToolTip("Window size for Savitzky-Golay filter (must be odd)")
        self.filter_widgets[signal_key]['window_spin'] = window_spin
        window_layout.addWidget(window_spin)
        window_spin.setVisible(combo.currentText() in ["S-G滤波", "平滑滤波"])
        
        filter_layout.addLayout(window_layout)
        self.settingsLayout.addLayout(filter_layout)

    def _add_spacer(self):
        """Add horizontal spacer to settings layout"""
        spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.settingsLayout.addItem(spacer)

    def _setup_plot_panel(self):
        """Setup the plot panel"""
        self.plotGroup = QtWidgets.QGroupBox()
        self.plotGroup.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        self.plotGroup.setObjectName("plotGroup")
        
        self.plotLayout = QtWidgets.QVBoxLayout(self.plotGroup)
        self.plotLayout.setContentsMargins(2, 2, 2, 6)
        self.plotLayout.setSpacing(5)
        
        # Plot widget placeholder
        self.plotWidget = QtWidgets.QWidget()
        self.plotWidget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.plotWidget.setStyleSheet("background-color: white; border: 1px solid #cccccc;")
        self.plotWidget.setObjectName("plotWidget")
        self.plotLayout.addWidget(self.plotWidget)
        
        self.mainLayout.addWidget(self.plotGroup)

    def _setup_translations(self):
        """Setup text translations and internationalization"""
        _translate = QtCore.QCoreApplication.translate
        
        # Main window title
        if hasattr(self, 'mainWidget'):
            self.mainWidget.setWindowTitle(_translate("DisplayWidget", "Signal Processing and Data Visualization"))
        
        # Control buttons
        button_texts = {
            'startButton': '开始',
            'resetButton': '复位',
            'recordButton': '记录',
            'stopButton': '停止'
        }
        
        for button_name, text in button_texts.items():
            if hasattr(self, button_name):
                getattr(self, button_name).setText(_translate("DisplayWidget", text))
        
        # Filter enable section
        self.filterEnableLabel.setText(_translate("DisplayWidget", "开启滤波："))
        
        for signal_key, checkbox in self.filter_checkboxes.items():
            checkbox.setText(_translate("DisplayWidget", self.signal_configs[signal_key]['chinese_label']))
        
        # Signal type selection
        self.signalTypeLabel.setText(_translate("DisplayWidget", "信号类型:"))
        
        # Filter settings labels
        for signal_key, widgets in self.filter_widgets.items():
            widgets['label'].setText(_translate("DisplayWidget", f"{self.signal_configs[signal_key]['chinese_label']}:"))
            widgets['order_label'].setText(_translate("DisplayWidget", "阶数:"))
            widgets['window_label'].setText(_translate("DisplayWidget", "窗口值:"))
        
        # Apply button
        self.applyButton.setText(_translate("DisplayWidget", "完成"))

    def _configure_initial_states(self):
        """Configure initial widget states and default values"""
        # 根据传感器类型设置初始状态
        self._update_ui_for_sensor_type()
        
        # Set initial button states
        button_states = {
            'startButton': True,
            'resetButton': False,
            'recordButton': False,
            'stopButton': False
        }
        
        for button_name, enabled in button_states.items():
            if hasattr(self, button_name):
                getattr(self, button_name).setEnabled(enabled)
        
        # Set initial combo box selections
        self.signalTypeCombo.setCurrentIndex(0)
        
        for signal_key, widgets in self.filter_widgets.items():
            widgets['filter_combo'].setCurrentIndex(0)
        
        # Set tab order for better keyboard navigation
        self._setup_tab_order()
        
        # Connect signals for dynamic UI updates
        self._connect_dynamic_signals()

    def _update_ui_for_sensor_type(self):
        """根据传感器类型更新UI状态"""
        # active_signals = SensorTypes.get_active_signals(self.sensor_type)
        
        # 更新复选框和滤波器组的可见性和启用状态
        for signal_key in self.signal_configs.keys():
            is_active = False
            
            # 设置复选框状态
            if signal_key in self.filter_checkboxes:
                self.filter_checkboxes[signal_key].setChecked(is_active)
                # self.filter_checkboxes[signal_key].setVisible(True)
            
            # 设置滤波器组件容器可见性
            if signal_key in self.filter_widgets:
                widgets = self.filter_widgets[signal_key]
                for widget in widgets.values():
                    widget.setVisible(is_active)
                # self.filter_widgets[signal_key]['main_layout'].setVisible(is_active)
        
        # 更新settingsGroup可见性
        self._update_settings_group_visibility()

    def _update_settings_group_visibility(self):
        """更新设置组的可见性（所有checkbox为false时隐藏）"""
        any_checked = any(checkbox.isChecked() for checkbox in self.filter_checkboxes.values())
        self.settingsGroup.setVisible(any_checked)
        
    def set_sensor_type(self, sensor_type):
        """设置传感器类型"""
        if sensor_type in [SensorTypes.NotInit, SensorTypes.EEG, SensorTypes.SEMG, 
                          SensorTypes.EEG_SEMG, SensorTypes.FNIRS, SensorTypes.EEG_FNIRS,
                          SensorTypes.SEMG_FNIRS, SensorTypes.EEG_SEMG_FNIRS]:
            self.sensor_type = sensor_type
            if hasattr(self, 'filter_checkboxes'):  # 确保UI已初始化
                self._update_ui_for_sensor_type()

    def _setup_tab_order(self):
        """Setup logical tab order for keyboard navigation"""
        tab_order = []
        
        # Control buttons
        for button_name in ['startButton', 'resetButton', 'recordButton', 'stopButton']:
            if hasattr(self, button_name):
                tab_order.append(getattr(self, button_name))
        
        # Filter checkboxes
        for checkbox in self.filter_checkboxes.values():
            tab_order.append(checkbox)
        
        # Signal type combo
        tab_order.append(self.signalTypeCombo)
        
        # Filter settings for each signal type
        for signal_key in self.signal_configs.keys():
            if signal_key in self.filter_widgets:
                widgets = self.filter_widgets[signal_key]
                widget_order = ['filter_combo', 'freq1_spin', 'freq2_spin', 'order_spin', 'window_spin']
                for widget_name in widget_order:
                    if widget_name in widgets:
                        tab_order.append(widgets[widget_name])
        
        # Apply button
        tab_order.append(self.applyButton)
        
        # Set tab order
        for i in range(len(tab_order) - 1):
            if hasattr(self, 'mainWidget'):
                self.mainWidget.setTabOrder(tab_order[i], tab_order[i + 1])

    def _connect_dynamic_signals(self):
        """Connect signals for dynamic UI behavior"""
        # Connect filter type changes to show/hide relevant parameters
        for signal_key, widgets in self.filter_widgets.items():
            combo = widgets['filter_combo']
            combo.currentTextChanged.connect(
                lambda text, sk=signal_key: self._update_filter_params_visibility(sk, text)
            )
        
        # Connect checkbox changes to enable/disable filter settings
        for signal_key, checkbox in self.filter_checkboxes.items():
            checkbox.toggled.connect(
                lambda checked, sk=signal_key: self._toggle_filter_group(sk, checked)
            )
        
        # Ensure window size is always odd for S-G filter
        for signal_key, widgets in self.filter_widgets.items():
            window_spin = widgets['window_spin']
            window_spin.valueChanged.connect(self._ensure_odd_window_size)

    def _update_filter_params_visibility(self, signal_key, filter_type):
        """Update parameter visibility based on selected filter type"""
        if signal_key not in self.filter_widgets:
            return
            
        widgets = self.filter_widgets[signal_key]
        
        if filter_type == "低通滤波" or filter_type == "高通滤波" or filter_type == " 带通滤波":
            # Show frequency and order, hide window
            if filter_type == "低通滤波":
                widgets['freq1_spin'].setVisible(True)
                widgets['freq2_spin'].setVisible(False)
            elif filter_type == "高通滤波":
                widgets['freq1_spin'].setVisible(False)
                widgets['freq2_spin'].setVisible(True)
            else: # 带通滤波
                widgets['freq1_spin'].setVisible(True)
                widgets['freq2_spin'].setVisible(True)
            widgets['order_label'].setVisible(True)
            widgets['order_spin'].setVisible(True)
            widgets['window_label'].setVisible(False)
            widgets['window_spin'].setVisible(False)
        elif filter_type == "S-G滤波" or filter_type == "平滑滤波":
            # Show window, hide frequency and order
            widgets['freq1_spin'].setVisible(False)
            widgets['freq2_spin'].setVisible(False)
            widgets['order_label'].setVisible(False)
            widgets['order_spin'].setVisible(False)
            widgets['window_label'].setVisible(True)
            widgets['window_spin'].setVisible(True)

    def _toggle_filter_group(self, signal_key, enabled):
        """Enable/disable filter settings group based on checkbox state"""
        if signal_key not in self.filter_widgets:
            return
            
        # 显示或隐藏整个容器
        widgets = self.filter_widgets[signal_key]
        for widget in widgets.values():
                    widget.setVisible(enabled)
        if enabled:
            # 根据当前选择的滤波器类型更新参数可见性
            current_filter = widgets['filter_combo'].currentText()
            self._update_filter_params_visibility(signal_key, current_filter)
        # self.filter_widgets[signal_key].setVisible(enabled)
        
        # 更新settingsGroup可见性
        self._update_settings_group_visibility()

    def _ensure_odd_window_size(self, value):
        """Ensure window size is always odd for S-G filter"""
        sender = self.sender() if hasattr(self, 'sender') else None # type: ignore
        if sender and value % 2 == 0:   
            sender.setValue(value + 1)

    # Utility methods for external control
    def get_control_states(self):
        """Get current state of control buttons"""
        states = {}
        button_names = ['startButton', 'resetButton', 'recordButton', 'stopButton']
        
        for button_name in button_names:
            if hasattr(self, button_name):
                states[f'{button_name[:-6]}_enabled'] = getattr(self, button_name).isEnabled()
        
        return states

    def set_control_states(self, **states):
        """Set control button states"""
        state_mapping = {
            'start_enabled': 'startButton',
            'stop_enabled': 'stopButton',
            'reset_enabled': 'resetButton',
            'record_enabled': 'recordButton'
        }
        
        for state_name, enabled in states.items():
            if state_name in state_mapping:
                button_name = state_mapping[state_name]
                if hasattr(self, button_name):
                    getattr(self, button_name).setEnabled(enabled)

    def get_filter_settings(self, signal_key):
        """Get filter settings for a specific signal type"""
        if signal_key not in self.filter_widgets:
            raise ValueError(f"Invalid signal type: {signal_key}")
        
        widgets = self.filter_widgets[signal_key]
        
        return {
            'filter_type': widgets['filter_combo'].currentText(),
            'freq1': widgets['freq1_spin'].value(),
            'freq2': widgets['freq2_spin'].value(),
            'order': widgets['order_spin'].value(),
            'window': widgets['window_spin'].value(),
            'enabled': self.filter_checkboxes[signal_key].isChecked() if signal_key in self.filter_checkboxes else False
        }

    def get_all_filter_settings(self):
        """Get complete filter settings for all signal types"""
        return {signal_key: self.get_filter_settings(signal_key) 
                for signal_key in self.signal_configs.keys()}

    def get_active_filter_params(self):
        """
        获取当前激活的滤波器参数
        仅返回checkbox为true的滤波器及其对应类型的参数
        
        Returns:
            dict: 格式为 {signal_key: {filter_type: str, params: dict}}
        """
        active_filters = {}
        
        for signal_key, checkbox in self.filter_checkboxes.items():
            if checkbox.isChecked():
                widgets = self.filter_widgets[signal_key]
                filter_type = widgets['filter_combo'].currentText()
                
                params = {}
                
                # 根据滤波器类型返回对应的参数
                if filter_type == "低通滤波":
                    params = {
                        'cutoff_freq': widgets['freq1_spin'].value(),
                        'order': widgets['order_spin'].value()
                    }
                elif filter_type == "高通滤波":
                    params = {
                        'cutoff_freq': widgets['freq2_spin'].value(),
                        'order': widgets['order_spin'].value()
                    }
                elif filter_type == "带通滤波":
                    params = {
                        'low_freq': widgets['freq1_spin'].value(),
                        'high_freq': widgets['freq2_spin'].value(),
                        'order': widgets['order_spin'].value()
                    }
                elif filter_type == "S-G滤波":
                    params = {
                        'window_length': widgets['window_spin'].value(),
                        'polyorder': widgets['order_spin'].value()  # S-G滤波也可能需要多项式阶数
                    }
                elif filter_type == "平滑滤波":
                    params = {
                        'window_length': widgets['window_spin'].value()
                    }
                
                active_filters[signal_key] = {
                    'filter_type': filter_type,
                    'params': params,
                    'signal_label': self.signal_configs[signal_key]['chinese_label']
                }
        
        return active_filters

    def get_active_filter_params_by_signal(self, signal_key):
        """
        获取指定信号类型的滤波器参数（如果激活）
        
        Args:
            signal_key: 信号类型键 ('eeg', 'semg', 'fnirs')
            
        Returns:
            dict or None: 如果该信号滤波器激活则返回参数字典，否则返回None
        """
        if signal_key not in self.filter_checkboxes:
            raise ValueError(f"Invalid signal type: {signal_key}")
        
        if not self.filter_checkboxes[signal_key].isChecked():
            return None
        
        active_filters = self.get_active_filter_params()
        return active_filters.get(signal_key)

    def has_active_filters(self):
        """检查是否有激活的滤波器"""
        return any(checkbox.isChecked() for checkbox in self.filter_checkboxes.values())

    def get_enabled_signal_keys(self):
        """获取已启用滤波器的信号类型列表"""
        return [signal_key for signal_key, checkbox in self.filter_checkboxes.items() 
                if checkbox.isChecked()]
        
    def set_filter_settings(self, signal_key, settings):
        """Set filter settings for a specific signal type"""
        if signal_key not in self.filter_widgets:
            raise ValueError(f"Invalid signal type: {signal_key}")
        
        widgets = self.filter_widgets[signal_key]
        
        if 'filter_type' in settings:
            index = widgets['filter_combo'].findText(settings['filter_type'])
            if index >= 0:
                widgets['filter_combo'].setCurrentIndex(index)
        
        if 'freq1' in settings:
            widgets['freq1_spin'].setValue(settings['freq1'])
        if 'freq2' in settings:
            widgets['freq2_spin'].setValue(settings['freq2'])
        if 'order' in settings:
            widgets['order_spin'].setValue(settings['order'])
        if 'window' in settings:
            widgets['window_spin'].setValue(settings['window'])
        if 'enabled' in settings and signal_key in self.filter_checkboxes:
            self.filter_checkboxes[signal_key].setChecked(settings['enabled'])

    def get_enabled_filters(self):
        """Get which signal filters are enabled"""
        return {signal_key: checkbox.isChecked() 
                for signal_key, checkbox in self.filter_checkboxes.items()}

    def set_enabled_filters(self, **filters):
        """Set which signal filters are enabled"""
        for signal_key, enabled in filters.items():
            if signal_key in self.filter_checkboxes:
                self.filter_checkboxes[signal_key].setChecked(enabled)

    def get_signal_type(self):
        """Get currently selected signal type"""
        return self.signalTypeCombo.currentText()

    def set_signal_type(self, signal_type):
        """Set signal type selection"""
        index = self.signalTypeCombo.findText(signal_type)
        if index >= 0:
            self.signalTypeCombo.setCurrentIndex(index)

    def reset_all_settings(self):
        """Reset all settings to default values"""
        # Reset to default sensor type
        self.set_sensor_type(SensorTypes.FNIRS)
        
        # Reset signal type
        self.signalTypeCombo.setCurrentIndex(0)
        
        # Reset filter settings to defaults from config
        for signal_key, config in self.signal_configs.items():
            default_settings = {
                'filter_type': self.filter_types[0],
                'freq1': config['freq_defaults'][0],
                'freq2': config['freq_defaults'][1],
                'order': config['order_default'],
                'window': config['window_default'],
                'enabled': config['enabled']
            }
            self.set_filter_settings(signal_key, default_settings)

    def get_ui_state(self):
        """Get complete UI state for saving/restoring"""
        return {
            'sensor_type': self.sensor_type,
            'control_states': self.get_control_states(),
            'enabled_filters': self.get_enabled_filters(),
            'signal_type': self.get_signal_type(),
            'filter_settings': self.get_all_filter_settings()
        }

    def set_ui_state(self, state):
        """Restore complete UI state"""
        if 'sensor_type' in state:
            self.set_sensor_type(state['sensor_type'])
        
        if 'control_states' in state:
            self.set_control_states(**state['control_states'])
        
        if 'enabled_filters' in state:
            self.set_enabled_filters(**state['enabled_filters'])
        
        if 'signal_type' in state:
            self.set_signal_type(state['signal_type'])
        
        if 'filter_settings' in state:
            for signal_key, settings in state['filter_settings'].items():
                self.set_filter_settings(signal_key, settings)

    def validate_settings(self):
        """Validate current settings and return validation results"""
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check if any filters are enabled
        enabled_filters = self.get_enabled_filters()
        if not any(enabled_filters.values()):
            validation_results['warnings'].append("No filters are enabled")
        
        # Validate filter settings for enabled filters
        for signal_key, enabled in enabled_filters.items():
            if enabled:
                settings = self.get_filter_settings(signal_key)
                signal_label = self.signal_configs[signal_key]['chinese_label']
                
                # Validate frequency ranges for frequency-based filters
                filter_type = settings['filter_type']
                if filter_type in ['低通滤波', '高通滤波', '带通滤波']:
                    if settings['freq1'] >= settings['freq2']:
                        validation_results['valid'] = False
                        validation_results['errors'].append(
                            f"{signal_label}: Lower frequency must be less than upper frequency"
                        )
                
                # Validate window size for S-G filter
                if filter_type == 'S-G滤波' and settings['window'] % 2 == 0:
                    validation_results['valid'] = False
                    validation_results['errors'].append(
                        f"{signal_label}: Window size must be odd for S-G filter"
                    )
                
                # Check frequency ranges are within sensor limits
                freq_range = self.signal_configs[signal_key]['freq_range']
                if (settings['freq1'] < freq_range[0] or settings['freq1'] > freq_range[1] or
                    settings['freq2'] < freq_range[0] or settings['freq2'] > freq_range[1]):
                    validation_results['warnings'].append(
                        f"{signal_label}: Frequencies outside recommended range "
                        f"({freq_range[0]}-{freq_range[1]} Hz)"
                    )
        
        return validation_results

    def get_active_signal_keys(self):
        """获取当前传感器类型下激活的信号键列表"""
        return self.sensor_type

    def update_signal_visibility(self):
        """根据传感器类型更新信号组件的可见性"""
        active_signals = self.get_active_signal_keys()
        
        for signal_key in self.signal_configs.keys():
            is_active = signal_key in active_signals
            
            # 更新复选框可见性
            if signal_key in self.filter_checkboxes:
                self.filter_checkboxes[signal_key].setVisible(is_active)
            
            # 更新滤波器设置组可见性
            if signal_key in self.filter_widgets:
                for widget in self.filter_widgets[signal_key].values():
                    widget.setVisible(is_active)

    def get_sensor_config_summary(self):
        """获取当前传感器配置摘要"""
        active_signals = self.get_active_signal_keys()
        enabled_filters = self.get_enabled_filters()
        
        summary = {
            'sensor_type': self.sensor_type,
            'active_signals': active_signals,
            'enabled_filters': {k: v for k, v in enabled_filters.items() if k in active_signals},
            'signal_processing_type': self.get_signal_type()
        }
        
        return summary

    def apply_sensor_defaults(self, sensor_type):
        """应用特定传感器类型的默认设置"""
        self.set_sensor_type(sensor_type)
        
        # 根据传感器类型设置默认的滤波器启用状态
        active_signals = SensorTypes.get_active_signals(sensor_type)
        
        filter_settings = {}
        for signal_key in active_signals:
            filter_settings[signal_key] = True
        
        # 禁用非激活信号的滤波器
        for signal_key in self.signal_configs.keys():
            if signal_key not in active_signals:
                filter_settings[signal_key] = False
        
        self.set_enabled_filters(**filter_settings)


# Test the UI class independently
if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    
    # Create main window
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("Optimized UI Display Test")
    
    # Create and setup the display widget
    display_widget = QtWidgets.QWidget()
    ui = Ui_DisplayWidget(SensorTypes.FNIRS)  # Default to FNIRS sensor type
    
    # Test different sensor types
    print("Testing sensor type configurations:")
    print(f"Default sensor type: {ui.sensor_type}")
    print(f"Active signals for FNIRS: {SensorTypes.get_active_signals(SensorTypes.FNIRS)}")
    print(f"Active signals for EEG_SEMG_FNIRS: {SensorTypes.get_active_signals(SensorTypes.EEG_SEMG_FNIRS)}")
    
    ui.setupUi(display_widget)
    
    # Apply the main layout to the widget
    display_widget.setLayout(ui.mainLayout)
    
    # # Test setting different sensor types
    # ui.set_sensor_type(SensorTypes.EEG_SEMG_FNIRS)
    # print(f"Changed to EEG_SEMG_FNIRS, active signals: {ui.get_active_signal_keys()}")
    
    # Test getting filter settings
    print("Current filter settings:")
    for signal_key in ui.signal_configs.keys():
        try:
            settings = ui.get_filter_settings(signal_key)
            print(f"{signal_key}: {settings}")
        except Exception as e:
            print(f"Error getting {signal_key} settings: {e}")
    
    # Set as central widget
    main_window.setCentralWidget(display_widget)
    main_window.show()
    
    sys.exit(app.exec_())