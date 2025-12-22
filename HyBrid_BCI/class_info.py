# -*- UTF-8 _*_
import enum
import numpy as np
import logging

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
    
    @classmethod
    def get_active_signals(cls, sensor_type):
        """根据传感器类型获取激活的信号列表"""
        signal_map = {
            cls.NotInit: [],
            cls.EEG: ['eeg'],
            cls.SEMG: ['semg'],
            cls.EEG_SEMG: ['eeg', 'semg'],
            cls.FNIRS: ['fnirs'],
            cls.EEG_FNIRS: ['eeg', 'fnirs'],
            cls.SEMG_FNIRS: ['semg', 'fnirs'],
            cls.EEG_SEMG_FNIRS: ['eeg', 'semg', 'fnirs']
        }
        return signal_map.get(sensor_type, [])

# Constants
class WorkflowStates:
    """工作流状态定义"""
    DISCONNECTED = 0
    CONNECTED = 1
    CONFIGURED = 2
    TESTED = 3
    ACQUIRED = 4
    ANALYZED = 5
    
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
                callback(old_state, new_state)
    
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
    