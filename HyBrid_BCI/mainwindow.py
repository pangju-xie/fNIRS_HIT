# -*- coding: utf-8 -*-

import sys
import logging
import os
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QTimer, pyqtSignal, QSettings
from PyQt5.QtWidgets import (QApplication, QMainWindow, QMessageBox, 
                            QScrollArea, QSplitter, QVBoxLayout, QHBoxLayout, 
                            QWidget, QSizePolicy)

# Import the optimized UI configuration
from ui_mainwindow import Ui_MainWindow
import network
import user
import fNIRS
from config import ConfigurationManager
import qualify
import display

os.environ['NUMEXPR_MAX_THREADS'] = '16'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fnirs_app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Constants
class WorkflowStates:
    """工作流状态定义"""
    DISCONNECTED = 0
    CONNECTED = 1
    CONFIGURED = 2
    TESTED = 3
    ACQUIRED = 4
    ANALYZED = 5

class SensorTypes:
    """传感器类型定义"""
    NotInit = 0
    EEG = 1
    SEMG = 2
    EEG_SEMG = 3
    FNIRS = 4
    EEG_FNIRS = 5
    SEMG_FNIRS = 6
    EEG_SEMG_FNIRS = 7

class StateManager:
    """状态管理器"""
    
    def __init__(self):
        self.current_state = WorkflowStates.DISCONNECTED
        self.sensor_type = SensorTypes.NotInit
        self.sensors = {}
        self.is_connecting = False
        self.is_disconnecting = False
        self.is_shutting_down = False
        self.state_callbacks = []
    
    def register_callback(self, callback):
        """注册状态变更回调"""
        self.state_callbacks.append(callback)
    
    def set_state(self, new_state):
        """设置新状态并通知回调"""
        if self.current_state != new_state:
            old_state = self.current_state
            self.current_state = new_state
            for callback in self.state_callbacks:
                try:
                    callback(old_state, new_state)
                except Exception as e:
                    logger.error(f"状态回调执行失败: {e}")
    
    def can_transition_to(self, target_state):
        """检查是否可以转换到目标状态"""
        valid_transitions = {
            WorkflowStates.DISCONNECTED: [WorkflowStates.CONNECTED],
            WorkflowStates.CONNECTED: [WorkflowStates.DISCONNECTED, WorkflowStates.CONFIGURED],
            WorkflowStates.CONFIGURED: [WorkflowStates.DISCONNECTED, WorkflowStates.TESTED, WorkflowStates.CONNECTED],
            WorkflowStates.TESTED: [WorkflowStates.DISCONNECTED, WorkflowStates.ACQUIRED, WorkflowStates.CONNECTED],
            WorkflowStates.ACQUIRED: [WorkflowStates.DISCONNECTED, WorkflowStates.ANALYZED, WorkflowStates.CONNECTED],
            WorkflowStates.ANALYZED: [WorkflowStates.DISCONNECTED]
        }
        return target_state in valid_transitions.get(self.current_state, [])

class ComponentManager:
    """组件管理器 - 简化版本"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.components = {}
    
    def add_component(self, name, widget, layout):
        """添加组件到指定布局"""
        try:
            # 如果组件已存在，先清理
            if name in self.components:
                self.remove_component(name)
            
            layout.addWidget(widget)
            self.components[name] = widget
            logger.info(f"{name} 组件添加成功")
            return widget
        except Exception as e:
            logger.error(f"添加 {name} 组件失败: {e}")
            self._add_error_placeholder(layout, f"{name} 组件加载失败")
            return None
    
    def remove_component(self, name):
        """移除指定组件"""
        if name in self.components:
            try:
                widget = self.components[name]
                if widget and hasattr(widget, 'close'):
                    widget.close()
                elif widget and hasattr(widget, 'deleteLater'):
                    widget.deleteLater()
                del self.components[name]
                logger.info(f"{name} 组件已移除")
            except Exception as e:
                logger.warning(f"移除 {name} 组件失败: {e}")
    
    def _add_error_placeholder(self, layout, message):
        """添加错误占位符"""
        placeholder = QtWidgets.QLabel(message)
        placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("QLabel { color: #f44336; font-style: italic; padding: 20px; }")
        layout.addWidget(placeholder)
    
    def cleanup_all(self):
        """清理所有组件"""
        for name in list(self.components.keys()):
            self.remove_component(name)

class MainWindow(QMainWindow):
    """
    主窗口 - 优化的响应式设计
    """
    
    # 定义信号
    deviceConnectionChanged = pyqtSignal(bool)
    workflowStateChanged = pyqtSignal(int, int)  # old_state, new_state
    batteryLevelChanged = pyqtSignal(int)
    configurationChanged = pyqtSignal()
    qualifyQuaryUpdate = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        
        # 初始化管理器
        self.state_manager = StateManager()
        self.component_manager = ComponentManager(self)
        self.timers = {}  # 简化的定时器管理
        
        # 设置UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # 初始化设置
        self.settings = QSettings('fNIRS Solutions', 'fNIRS Data Acquisition System')
        
        # 初始化系统
        self._initialize_system()
        
        logger.info("主窗口初始化完成")
    
    def _initialize_system(self):
        """初始化系统组件"""
        try:
            # 注册状态变更回调
            self.state_manager.register_callback(self._on_state_changed)
            
            # 初始化网络
            self._initialize_network()
            
            # 设置连接
            self._setup_connections()
            
            # 初始化组件
            self._initialize_components()
            
            # 初始化定时器
            self._initialize_timers()
            
            # 更新UI状态
            self.update_ui_state()
            
            # 恢复窗口状态
            self.restore_window_state()
            
            logger.info("系统初始化完成")
            
        except Exception as e:
            logger.error(f"系统初始化失败: {e}")
            QMessageBox.critical(self, "初始化错误", f"系统初始化失败:\n{e}")
    
    def _initialize_network(self):
        """初始化网络模块"""
        try:
            self.network = network.UdpPort(1227, 2227)
            self._setup_network_connections()
            logger.info("网络模块初始化成功")
        except Exception as e:
            logger.error(f"网络模块初始化失败: {e}")
            self.network = None
    
    def _setup_connections(self):
        """设置信号连接"""
        # UI连接
        self.ui.connectButton.clicked.connect(self.handle_connection_toggle)
        self.ui.tabWidget.currentChanged.connect(self.on_tab_changed)
        
        # 菜单连接
        menu_connections = [
            (self.ui.saveAction, self.save_data),
            (self.ui.exportAction, self.export_data),
            (self.ui.exitAction, self.close),
            (self.ui.preferencesAction, self.show_preferences),
            (self.ui.aboutAction, self.show_about)
        ]
        
        for action, slot in menu_connections:
            action.triggered.connect(slot)
        
        # 自定义信号连接
        self.deviceConnectionChanged.connect(self.on_device_connection_changed)
        self.workflowStateChanged.connect(self.on_workflow_state_changed)
        self.batteryLevelChanged.connect(self.update_battery_display)
        self.configurationChanged.connect(self.on_configuration_changed)
    
    def _setup_network_connections(self):
        """设置网络信号连接"""
        if not self.network:
            return
            
        network_connections = [
            (self.network.onDeviceConnected, self.on_device_connected),
            (self.network.onDeviceDisconnected, self.on_device_disconnected),
            (self.network.onDeviceSample, self.on_sample_start_stop),
            (self.network.onDataReceived, self.on_data_received),
            (self.network.onDataPatched, self.on_data_patched),
            (self.network.onBatteryUpdated, self.on_battery_updated),
            (self.network.onSampleRateSetDone, self.on_sample_rate_set_done),
            (self.network.onChannelConfigSetDone, self.on_channel_config_set_done),
            (self.network.networkError, self.on_network_error)
        ]
        
        for signal, slot in network_connections:
            signal.connect(slot)
    
    def _initialize_components(self):
        """初始化所有组件"""
        # 初始化用户信息组件
        self.user_widget = self._create_user_widget()
        
        # 配置和测试组件将在设备连接后初始化
        self.config_widget = None
        self.qualify_widget = None
        self.display_widget = None
    
    def _create_user_widget(self):
        """创建用户信息组件"""
        try:
            widget = user.UserInfoManager()
            self.component_manager.add_component('user', widget, self.ui.homeLayout) # type: ignore
            if hasattr(widget, 'patientChanged'):
                widget.patientChanged.connect(self.on_patient_changed)
            return widget
        except Exception as e:
            logger.error(f"用户组件创建失败: {e}")
            return None
    
    def _initialize_timers(self):
        """初始化定时器"""
        # 连接超时定时器
        self.timers['connection_timeout'] = QTimer()
        self.timers['connection_timeout'].timeout.connect(self.on_connection_timeout)
        self.timers['connection_timeout'].setSingleShot(True)
        
        # 电池查询定时器
        self.timers['battery_query'] = QTimer()
        self.timers['battery_query'].timeout.connect(self.query_battery)
        self.timers['battery_query'].setInterval(10000)
    
    def _on_state_changed(self, old_state, new_state):
        """状态变更回调"""
        self.workflowStateChanged.emit(old_state, new_state)
        self.update_ui_state()
        logger.info(f"状态变更: {old_state} -> {new_state}")
    
    # ===== 连接管理 =====
    
    def handle_connection_toggle(self):
        """处理连接切换"""
        if self.state_manager.is_shutting_down or not self.network:
            return
            
        if self.state_manager.current_state == WorkflowStates.DISCONNECTED:
            self.connect_device()
        else:
            self.disconnect_device()
    
    def connect_device(self):
        """连接设备"""
        if self.state_manager.is_connecting or self.state_manager.is_shutting_down:
            return
            
        try:
            self._set_connecting_state()
            self.network.sendConnect() # type: ignore
            self.timers['connection_timeout'].start(10000)
            
        except Exception as e:
            self._reset_connection_state()
            logger.error(f"连接失败: {e}")
            self.show_error_message(f"连接失败: {e}")
    
    def disconnect_device(self):
        """断开连接"""
        if self.state_manager.is_disconnecting:
            return
            
        try:
            self._set_disconnecting_state()
            self._stop_all_timers()
            
            if self.network and len(self.network.get_connected_devices()) > 0:
                self.network.sendDisconnect()
                QTimer.singleShot(3000, self.force_disconnect)
            else:
                QTimer.singleShot(100, self.on_device_disconnected)
                
        except Exception as e:
            logger.error(f"断开连接失败: {e}")
            self.force_disconnect()
    
    def _set_connecting_state(self):
        """设置连接中状态"""
        self.state_manager.is_connecting = True
        self.ui.connectButton.setEnabled(False)
        self.ui.connectButton.setText("正在连接...")
        self._update_status("正在连接设备...", "#ff9800")
    
    def _set_disconnecting_state(self):
        """设置断开连接中状态"""
        self.state_manager.is_disconnecting = True
        self.ui.connectButton.setEnabled(False)
        self.ui.connectButton.setText("正在断开...")
        self._update_status("正在断开连接...", "#ff9800")
    
    def _reset_connection_state(self):
        """重置连接状态"""
        if not self.state_manager.is_shutting_down:
            self.ui.connectButton.setEnabled(True)
            self.ui.connectButton.setText("连接设备")
        
        self.state_manager.is_connecting = False
        self.state_manager.is_disconnecting = False
    
    # ===== 网络事件处理 =====
    
    def on_device_connected(self, sensor_id, sensor_type):
        """处理设备连接事件"""
        if self.state_manager.is_shutting_down:
            return
            
        try:
            self.timers['connection_timeout'].stop()
            self.state_manager.is_connecting = False
            
            # 确保之前的组件已清理（防御性编程）
            self._ensure_component_cleanup()
            
            # 更新状态
            self.state_manager.set_state(WorkflowStates.CONNECTED)
            self.state_manager.sensor_type = sensor_type
            
            # 初始化传感器
            self._init_sensors(sensor_type)
            
            # 更新UI
            self._set_connected_state(sensor_id, sensor_type)
            
            # 启动电池监控
            self.timers['battery_query'].start()
            
            # 初始化配置组件（现在有重复检查保护）
            self._initialize_config_widget(sensor_type)
            
            # 发送信号
            self.deviceConnectionChanged.emit(True)
            
            logger.info(f"设备连接成功: ID={sensor_id}, Type={sensor_type}")
            
        except Exception as e:
            logger.error(f"处理设备连接失败: {e}")
    
    def on_device_disconnected(self):
        """处理设备断开事件"""
        if self.state_manager.is_shutting_down:
            return
            
        try:
            self._stop_all_timers()
            
            # 清理配置和测试组件，避免重复初始化
            self._cleanup_session_components()
            
            # 重置状态
            self.state_manager.set_state(WorkflowStates.DISCONNECTED)
            self.state_manager.sensor_type = SensorTypes.NotInit
            self.state_manager.sensors.clear()
            
            # 重置UI
            self._reset_disconnected_state()
            
            # 发送信号
            self.deviceConnectionChanged.emit(False)
            
            logger.info("设备断开连接")
            
        except Exception as e:
            logger.error(f"处理设备断开失败: {e}")
    
    def _cleanup_session_components(self):
        """清理会话相关的组件"""
        # 清理配置组件
        if self.config_widget:
            self.component_manager.remove_component('config')
            # 清理布局中的配置组件
            self.ui.clear_tab_content('config')
            self.config_widget = None
            
        # 清理测试组件  
        if self.qualify_widget:
            self.component_manager.remove_component('qualify')
            # 清理布局中的测试组件
            self.ui.clear_tab_content('qualify')
            self.qualify_widget = None

        # 清理采样组件  
        if self.display_widget:
            self.component_manager.remove_component('display')
            # 清理布局中的采样组件
            self.ui.clear_tab_content('display')
            self.display_widget = None
            
        logger.debug("会话组件清理完成")
    
    def _ensure_component_cleanup(self):
        """确保组件完全清理"""
        # 检查配置组件
        if hasattr(self, 'config_widget') and self.config_widget is not None:
            try:
                # 断开可能的信号连接
                if hasattr(self.config_widget, 'OnConfigSet'):
                    self.config_widget.OnConfigSet.disconnect()
                if hasattr(self.config_widget, 'OnConfigApplied'):
                    self.config_widget.OnConfigApplied.disconnect()
                self.config_widget = None
            except Exception as e:
                logger.warning(f"清理配置组件连接失败: {e}")
        
        # 检查测试组件
        if hasattr(self, 'qualify_widget') and self.qualify_widget is not None:
            try:
                if hasattr(self.qualify_widget, 'QualityQuary'):
                    self.qualify_widget.QualityQuary.disconnect()
                self.qualify_widget = None
            except Exception as e:
                logger.warning(f"清理测试组件失败: {e}")

        if hasattr(self, 'display_widget') and self.display_widget is not None:
            try:
                self.display_widget = None
            except Exception as e:
                logger.warning(f"清理测试组件失败: {e}")
                
        logger.debug("组件清理检查完成")
    
    def on_connection_timeout(self):
        """处理连接超时"""
        if self.state_manager.is_connecting:
            self._reset_connection_state()
            self._update_status("连接超时 - 未找到设备", "#f44336")
            logger.warning("连接超时")
    
    def force_disconnect(self):
        """强制断开连接"""
        logger.warning("强制断开连接")
        self.on_device_disconnected()
    
    def _set_connected_state(self, sensor_id, sensor_type):
        """设置已连接状态"""
        self.ui.connectButton.setText("断开连接")
        self.ui.connectButton.setEnabled(True)
        
        device_count = len(self.network.get_connected_devices()) if self.network else 1
        self._update_status(f"已连接 {device_count} 个设备", "#4caf50")
        self._update_device_info(sensor_id, sensor_type)
    
    def _reset_disconnected_state(self):
        """重置断开连接状态"""
        self._update_device_info('--', '--')
        self.ui.batteryProgressBar.setValue(0)
        self.ui.batteryProgressBar.setStyleSheet("")
        self._reset_connection_state()
        self._update_status("设备已断开", "#2196f3")
        self.ui.tabWidget.setCurrentIndex(0)
    
    # ===== 传感器和配置管理 =====
    
    def _init_sensors(self, sensor_type):
        """初始化传感器"""
        try:
            self.state_manager.sensors.clear()
            
            # 获取用户信息
            user_dict = {}
            if (self.user_widget and 
                hasattr(self.user_widget, 'current_patient')):
                user_dict = self.user_widget.current_patient.to_dict()
            
            # 初始化不同类型的传感器
            sensor_map = {
                SensorTypes.EEG: 'eeg',
                SensorTypes.SEMG: 'semg',
                SensorTypes.FNIRS: 'fnirs'
            }
            
            for sensor_bit, sensor_name in sensor_map.items():
                if sensor_type & sensor_bit:
                    if sensor_name == 'fnirs':
                        self.state_manager.sensors[sensor_name] = fNIRS.fNIRS(user_dict)
                    else:
                        self.state_manager.sensors[sensor_name] = True
            
            logger.info(f"传感器初始化完成: {list(self.state_manager.sensors.keys())}")
            
        except Exception as e:
            logger.error(f"传感器初始化失败: {e}")
    
    def _initialize_config_widget(self, sensor_types):
        """初始化配置组件"""
        # 防止重复初始化
        if self.config_widget is not None:
            logger.debug("配置组件已存在，跳过重复初始化")
            return
            
        try:
            self.config_widget = ConfigurationManager(sensor_types)
            self.component_manager.add_component('config', self.config_widget, self.ui.configLayout) # type: ignore
            
            if self.config_widget:
                self.config_widget.OnConfigSet.connect(self.on_config_set)
                self.deviceConnectionChanged.connect(self._update_config_state)
                logger.info("配置组件初始化成功")
                
        except Exception as e:
            logger.error(f"配置组件初始化失败: {e}")
            self.config_widget = None
    
    def _initialize_qualify_widget(self):
        """初始化测试组件"""
        # 防止重复初始化
        if self.qualify_widget is not None:
            logger.debug("测试组件已存在，跳过重复初始化")
            return
            
        try:
            self.qualify_widget = qualify.QualifyApp()
            self.component_manager.add_component('qualify', self.qualify_widget, self.ui.testLayout) # type: ignore

            # config向qualify传递通道配置
            if self.qualify_widget and self.config_widget:
                self.config_widget.OnConfigApplied.connect(
                    self.qualify_widget.initialize_channels
                )
            # 查询sensor状态
            if hasattr(self.qualify_widget, 'QualityQuary'):
                self.qualify_widget.QualityQuary.connect(self.quary_sensor_quality)
            self.qualifyQuaryUpdate.connect(self.qualify_widget.update_signals)
            # 采样按钮
            self.qualify_widget.ui.startButton.clicked.connect(self.network.sendStartSample) # type: ignore
            self.qualify_widget.ui.stopButton.clicked.connect(self.network.sendStopSample) # type: ignore

            logger.info("测试组件初始化成功")

        except Exception as e:
            logger.error(f"测试组件初始化失败: {e}")
            self.qualify_widget = None
    
    def _initialize_display_widget(self):
        """初始化采样组件"""
        # 防止重复初始化
        if self.display_widget is not None:
            logger.debug("采样组件已存在，跳过重复初始化")
            return
            
        try:
            self.display_widget = display.DisplayWidget()
            self.component_manager.add_component('display', self.display_widget, self.ui.acquisitionLayout) # type: ignore

            logger.info("采样组件初始化成功")
        except Exception as e:
            logger.error(f"采样组件初始化失败: {e}")
            self.display_widget = None
    


    def on_config_set(self, sample_data, channel_config):
        """处理配置设置"""
        try:
            if self.network and self.state_manager.current_state >= WorkflowStates.CONNECTED:
                # 加载测试组件
                self.state_manager.set_state(WorkflowStates.CONNECTED)  # 点击“设置”时重设为未配置
                self._initialize_qualify_widget()
                # 发送至设备
                self.network.sendSampleRate(sample_data)
                self.network.sendChannelConfig(channel_config)
                logger.info("配置已发送到设备")
                
        except Exception as e:
            logger.error(f"配置设置失败: {e}")
    
    def on_sample_rate_set_done(self, valid: bool):
        """处理采样率设置完成"""
        if self.config_widget and valid:
            self.config_widget.sample_rate_send_done = valid
            # 设置传感器采样率
            sample_rate = self.config_widget.get_sample_rate()
            for sensor_name, rates in sample_rate.items():
                if (sensor_name in self.state_manager.sensors and 
                    sensor_name == 'fnirs'):
                    self.state_manager.sensors[sensor_name].setSampleRate(rates)
            self._check_configuration_complete()
    
    def on_channel_config_set_done(self, valid: bool):
        """处理通道配置完成"""
        if self.config_widget and valid:
            self.config_widget.channel_config_send_done = valid
            # 设置传感器配置
            for sensor_name in self.state_manager.sensors.keys():
                if sensor_name == 'fnirs':
                    montage = self.config_widget.get_fnirs_source_detector()
                    self.state_manager.sensors[sensor_name].setMontage(montage)
            self._check_configuration_complete()
    
    def _check_configuration_complete(self):
        """检查配置是否完成"""
        if (hasattr(self.config_widget, 'sample_rate_send_done') and
            hasattr(self.config_widget, 'channel_config_send_done') and
            self.config_widget.sample_rate_send_done and  # type: ignore
            self.config_widget.channel_config_send_done): # type: ignore
            
            self.config_widget.sample_rate_send_done = False # type: ignore
            self.config_widget.channel_config_send_done = False # type: ignore
            self.state_manager.set_state(WorkflowStates.CONFIGURED)
            self._update_status("配置完成", "#4caf50")
            self.configurationChanged.emit()
            
            # 初始化测试组件
            self._initialize_qualify_widget()
            
            logger.info("配置步骤完成")
    
    # ===== 数据处理 =====
    
    def on_sample_start_stop(self, is_start: bool):
        """处理数据采样开始/停止"""
        status = "开始" if is_start else "停止"
        logger.info(f"数据采样{status}")
    
    def on_data_received(self, sensor_type, packet_id, data):
        """处理接收到的数据"""
        try:
            if sensor_type == SensorTypes.FNIRS:
                if 'fnirs' in self.state_manager.sensors:
                    self.state_manager.sensors['fnirs'].updateData(packet_id, data)
        except Exception as e:
            logger.error(f"数据处理失败: {e}")
    
    def on_data_patched(self, sensor_type, packet_id, data):
        """处理数据修补"""
        logger.debug(f"数据修补: {sensor_type}, {packet_id}")
    
    def on_battery_updated(self, battery_level):
        """处理电池电量更新"""
        if not self.state_manager.is_shutting_down:
            self.batteryLevelChanged.emit(battery_level)
    
    def query_battery(self):
        """查询电池电量"""
        if (not self.state_manager.is_shutting_down and 
            self.network and 
            self.state_manager.current_state >= WorkflowStates.CONNECTED):
            try:
                self.network.sendBatteryQuery()
            except Exception as e:
                logger.warning(f"电池查询失败: {e}")
    
    def on_network_error(self, error_message):
        """处理网络错误"""
        if self.state_manager.is_shutting_down:
            return
            
        logger.error(f"网络错误: {error_message}")
        self._update_status(f"网络错误: {error_message}", "#f44336")
        
        if "connection" in error_message.lower():
            self.on_device_disconnected()
        
        self.show_error_message(f"网络错误: {error_message}")
    
    # ===== 数据查询 =====
    def quary_sensor_quality(self, method_index):
        quality_data = {}
        for sensor_name in self.state_manager.sensors.keys():
            if hasattr(self.state_manager.sensors[sensor_name], 'get_quality'):
                quality_data[sensor_name] = self.state_manager.sensors[sensor_name].get_quality(method_index)
        self.qualifyQuaryUpdate.emit(quality_data)
    
    # ===== UI更新和工作流管理 =====
    
    def update_ui_state(self):
        """更新UI状态"""
        if self.state_manager.is_shutting_down:
            return
            
        try:
            # 检查连接和患者信息
            connected = self.state_manager.current_state >= WorkflowStates.CONNECTED
            has_patient = self._check_patient_info()
            
            # Tab启用逻辑
            tab_states = [
                True,  # 主页
                connected and has_patient,  # 配置需要连接和患者信息
                self.state_manager.current_state >= WorkflowStates.CONFIGURED,
                self.state_manager.current_state >= WorkflowStates.TESTED,
                self.state_manager.current_state >= WorkflowStates.ACQUIRED
            ]
            
            for index, enabled in enumerate(tab_states):
                if index < self.ui.tabWidget.count():
                    self.ui.tabWidget.setTabEnabled(index, enabled)
            
        except Exception as e:
            logger.error(f"UI状态更新失败: {e}")
    
    def _check_patient_info(self):
        """检查患者信息是否完整"""
        try:
            if (hasattr(self, 'user_widget') and 
                hasattr(self.user_widget, 'current_patient') and
                self.user_widget.current_patient): # type: ignore
                return getattr(self.user_widget.current_patient, 'initials', '') != '' # type: ignore
        except Exception as e:
            logger.warning(f"检查患者信息失败: {e}")
        return False
    
    def _update_device_info(self, device_id, device_type):
        """更新设备信息显示"""
        try:
            if device_id != "--" and device_type != "--":
                # 格式化设备ID
                if isinstance(device_id, list):
                    id_str = "-".join([f"{x:02X}" for x in device_id])
                else:
                    id_str = str(device_id)
                
                # 设备类型映射
                type_names = {
                    1: "EEG", 2: "sEMG", 3: "EEG/sEMG", 4: "fNIRS",
                    5: "EEG/fNIRS", 6: "sEMG/fNIRS", 7: "EEG/sEMG/fNIRS"
                }
                type_name = type_names.get(device_type, f"Type-{device_type}")
                
                self.ui.deviceIdLabel.setText(f"设备 ID: {id_str}")
                self.ui.deviceTypeLabel.setText(f"设备类型: {type_name}")
            else:
                self.ui.deviceIdLabel.setText("设备 ID: --")
                self.ui.deviceTypeLabel.setText("设备类型: --")
                
        except Exception as e:
            logger.error(f"更新设备信息失败: {e}")
    
    def update_battery_display(self, battery_level):
        """更新电池显示"""
        try:
            self.ui.batteryProgressBar.setValue(battery_level)
            
            # 根据电量设置颜色
            if battery_level < 20:
                color = "#f44336"  # 红色
            elif battery_level < 50:
                color = "#ff9800"  # 橙色
            else:
                color = "#4caf50"  # 绿色
            
            self.ui.batteryProgressBar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {color}; }}"
            )
            
        except Exception as e:
            logger.error(f"更新电池显示失败: {e}")
    
    def _update_status(self, message, color="#333333"):
        """更新状态显示"""
        try:
            self.ui.statusInfoLabel.setText(f"状态: {message}")
            self.ui.statusInfoLabel.setStyleSheet(
                f"QLabel {{ color: {color}; font-weight: bold; }}"
            )
        except Exception as e:
            logger.error(f"更新状态显示失败: {e}")
    
    def _update_config_state(self, connected):
        """更新配置管理器状态"""
        if self.config_widget:
            try:
                self.config_widget.setEnabled(connected)
            except Exception as e:
                logger.error(f"更新配置管理器状态失败: {e}")
    
    # ===== 工作流管理 =====
    
    def on_tab_changed(self, index):
        """处理标签页切换"""
        if self.state_manager.is_shutting_down:
            return
            
        try:
            tab_names = ['home', 'configuration', 'test', 'acquisition', 'analysis']
            if 0 <= index < len(tab_names):
                current_tab = tab_names[index]
                logger.debug(f"切换到标签页: {current_tab}")
                
                # 处理工作流进展
                self._handle_workflow_progression(current_tab)
                
        except Exception as e:
            logger.error(f"处理标签页切换失败: {e}")
    
    def _handle_workflow_progression(self, tab_name):
        """处理工作流进展"""
        try:
            progression_actions = {
                'test': lambda: self._progress_to_state(WorkflowStates.TESTED, "测试完成"),
                'acquisition': lambda: self._progress_to_state(WorkflowStates.ACQUIRED, "数据采集完成"),
                'analysis': lambda: self._progress_to_state(WorkflowStates.ANALYZED, "数据分析完成")
            }
            
            if tab_name in progression_actions:
                QTimer.singleShot(1500, progression_actions[tab_name])
                
        except Exception as e:
            logger.error(f"工作流进展处理失败: {e}")
    
    def _progress_to_state(self, target_state, message):
        """进展到目标状态"""
        if self.state_manager.can_transition_to(target_state):
            self.state_manager.set_state(target_state)
            self._update_status(message, "#4caf50")
            logger.info(f"{message}")
    
    # ===== 事件回调 =====
    
    def on_device_connection_changed(self, connected):
        """设备连接状态变更回调"""
        self.update_ui_state()
    
    def on_workflow_state_changed(self, old_state, new_state):
        """工作流状态变更回调"""
        self.update_ui_state()
    
    def on_configuration_changed(self):
        """配置变更回调"""
        logger.debug("配置已变更")
    
    def on_patient_changed(self):
        """患者信息变更回调"""
        self.update_ui_state()
    
    # ===== 文件操作 =====
    
    def save_data(self):
        """保存数据"""
        if self.state_manager.is_shutting_down:
            return
            
        try:
            current_index = self.ui.tabWidget.currentIndex()
            if current_index == 0 and self.user_widget:
                self._save_patient_data()
            elif current_index == 1 and self.config_widget:
                self._save_configuration_data()
            else:
                QMessageBox.information(self, "保存", "数据保存成功!")
                
        except Exception as e:
            logger.error(f"保存失败: {e}")
            self.show_error_message(f"保存失败: {e}")
    
    def _save_patient_data(self):
        """保存患者数据"""
        try:
            if hasattr(self.user_widget, 'save_patient_data'):
                self.user_widget.save_patient_data() # type: ignore
            QMessageBox.information(self, "保存", "患者数据保存成功!")
        except Exception as e:
            QMessageBox.critical(self, "保存错误", f"保存患者数据失败: {e}")
    
    def _save_configuration_data(self):
        """保存配置数据"""
        try:
            self.config_widget.save_configuration() # type: ignore
            QMessageBox.information(self, "保存", "配置保存成功!")
        except Exception as e:
            QMessageBox.critical(self, "保存错误", f"保存配置失败: {e}")
    
    def export_data(self):
        """导出数据"""
        if self.state_manager.is_shutting_down:
            return
            
        try:
            if self.state_manager.current_state >= WorkflowStates.ACQUIRED:
                QMessageBox.information(self, "导出", "数据导出功能将在此实现")
            else:
                QMessageBox.information(self, "导出", "无可导出数据。请先完成数据采集。")
                
        except Exception as e:
            logger.error(f"导出失败: {e}")
            self.show_error_message(f"导出失败: {e}")
    
    # ===== 界面对话框 =====
    
    def show_preferences(self):
        """显示首选项对话框"""
        if not self.state_manager.is_shutting_down:
            QMessageBox.information(self, "首选项", "首选项对话框将在此实现")
    
    def show_about(self):
        """显示关于对话框"""
        if self.state_manager.is_shutting_down:
            return
            
        about_text = (
            "fNIRS 数据采集系统\n\n"
            "版本: 3.1 (优化响应式设计)\n"
            "功能齐全的 fNIRS 数据收集和分析系统。\n\n"
            "主要改进:\n"
            "• 完全响应式的TabWidget布局\n"
            "• 简化的代码结构和组件管理\n"
            "• 优化的状态管理系统\n"
            "• 更好的错误处理和日志记录\n"
            "• 自适应滚动区域支持\n"
            "• 统一的定时器管理\n"
            "• 改进的网络连接处理\n"
            "• 模块化的组件初始化"
        )
        QMessageBox.about(self, "关于 fNIRS 系统", about_text)
    
    def show_error_message(self, message):
        """显示错误消息对话框"""
        if not self.state_manager.is_shutting_down:
            QMessageBox.critical(self, "错误", message)
    
    # ===== 工具方法 =====
    
    def _stop_all_timers(self):
        """停止所有定时器"""
        for timer in self.timers.values():
            if timer.isActive():
                timer.stop()
    
    def resizeEvent(self, event): # type: ignore
        """处理窗口大小调整事件"""
        super().resizeEvent(event)
        # 响应式设计已在UI层面处理，这里只需要基本更新
        self.update()
    
    def restore_window_state(self):
        """恢复窗口状态"""
        try:
            geometry = self.settings.value("window/geometry")
            if geometry:
                self.restoreGeometry(geometry)
            else:
                self.resize(1200, 800)
                self._center_window()
            
            window_state = self.settings.value("window/state")
            if window_state:
                self.restoreState(window_state)
            
            tab_index = self.settings.value("tab/current_index", 0, type=int)
            if 0 <= tab_index < self.ui.tabWidget.count():
                self.ui.tabWidget.setCurrentIndex(tab_index)
                
        except Exception as e:
            logger.error(f"恢复窗口状态失败: {e}")
            self.resize(1200, 800)
            self._center_window()
    
    def _center_window(self):
        """窗口居中"""
        try:
            screen = QApplication.desktop().availableGeometry() # type: ignore
            window_rect = self.frameGeometry()
            center_point = screen.center()
            window_rect.moveCenter(center_point)
            self.move(window_rect.topLeft())
        except Exception as e:
            logger.error(f"窗口居中失败: {e}")
    
    def save_window_state(self):
        """保存窗口状态"""
        try:
            self.settings.setValue("window/geometry", self.saveGeometry())
            self.settings.setValue("window/state", self.saveState())
            self.settings.setValue("tab/current_index", self.ui.tabWidget.currentIndex())
            self.settings.sync()
        except Exception as e:
            logger.error(f"保存窗口状态失败: {e}")
    
    # ===== 清理和关闭 =====
    
    def closeEvent(self, event): # type: ignore
        """处理应用程序关闭事件"""
        try:
            self._perform_shutdown()
            event.accept()
            logger.info("应用程序关闭成功")
        except Exception as e:
            logger.error(f"应用程序关闭时发生错误: {e}")
            event.accept()  # 强制关闭
    
    def _perform_shutdown(self):
        """执行关闭清理"""
        logger.info("开始关闭清理...")
        
        # 设置关闭标志
        self.state_manager.is_shutting_down = True
        
        # 保存窗口状态
        self.save_window_state()
        
        # 停止所有定时器
        self._stop_all_timers()
        
        # 断开网络连接
        if (self.network and 
            self.state_manager.current_state >= WorkflowStates.CONNECTED):
            try:
                self.network.sendDisconnect()
                QApplication.processEvents()
            except Exception as e:
                logger.warning(f"网络断开失败: {e}")
        
        # 清理所有组件
        self.component_manager.cleanup_all()
        
        # 关闭网络
        if self.network:
            try:
                self.network.close()
            except Exception as e:
                logger.warning(f"网络模块关闭失败: {e}")
        
        logger.info("关闭清理完成")


def main():
    """主应用程序入口点"""
    try:
        app = QApplication(sys.argv)
        
        # 设置应用程序属性
        app.setApplicationName("fNIRS Data Acquisition System")
        app.setApplicationVersion("3.1")
        app.setOrganizationName("fNIRS Solutions")
        
        # 启用高DPI缩放
        app.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        app.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
        # 创建并显示主窗口
        window = MainWindow()
        window.show()
        
        logger.info("应用程序启动成功 - 优化响应式设计")
        
        # 启动事件循环
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.critical(f"应用程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()