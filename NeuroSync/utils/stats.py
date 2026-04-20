# models/stats.py
from enum import IntEnum, IntFlag
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple
from PyQt5.QtCore import QObject, pyqtSignal
import time

# ==========================================
# 1. 通信协议与硬件定义层 (Enums & Dataclasses)
# ==========================================
class SensorTypes(IntFlag):
    """传感器类型定义 (基于位掩码)"""
    NotInit = 0
    EEG = 1             # 001
    SEMG = 2            # 010
    EEG_SEMG = 3        # 011
    FNIRS = 4           # 100
    EEG_FNIRS = 5       # 101
    SEMG_FNIRS = 6      # 110
    EEG_SEMG_FNIRS = 7  # 111

class Commands(IntEnum):
    """硬件通信协议指令集 (Hex)"""
    CONNECT = 0xB0
    DISCONNECT = 0xB1
    START_SAMPLE = 0xC0
    STOP_SAMPLE = 0xC1
    BATTERY_QUERY = 0xC2
    SAMPLE_RATE = 0xC3
    CHANNEL_CONFIG = 0xA0
    DATA_RECEIVE = 0xA1
    DATA_PATCHING = 0xA2

class WorkflowStates(IntEnum):
    """上位机工作流状态机"""
    DISCONNECTED = 0    
    CONNECTED = 1       
    CONFIGURED = 2      
    QUALIFIED = 3          
    ACQUIRED = 4        
    ANALYZED = 5        


@dataclass
class PendingCommand:
    """待确认的指令状态 (用于超时重传)"""
    command: Commands
    packet: bytes
    target_ip: str
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0


@dataclass
class Device:
    """设备物理信息映射"""
    ip: str
    id: List[int]
    type: SensorTypes
    port: int
    
    def __hash__(self):
        return hash((self.ip, tuple(self.id), self.type, self.port))


# ==========================================
# 2. 状态机与数据中心层 (Models / QObjects)
# ==========================================
class SystemState:
    """全局状态管理容器与安全锁 (单例)"""
    def __init__(self):
        self._workflow = WorkflowStates.DISCONNECTED
        
    @property
    def workflow(self) -> WorkflowStates:
        return self._workflow

    def advance_workflow(self, target_state: WorkflowStates) -> Tuple[bool, str]:
        """严格校验状态切换顺序"""
        if target_state == self._workflow:
            return True, "状态未改变"
        if target_state < self._workflow:
            self._workflow = target_state
            return True, f"状态已安全回退至: {target_state.name}"
        if target_state.value == self._workflow.value + 1:
            self._workflow = target_state
            return True, f"状态成功推进至: {target_state.name}"
            
        next_required_state = WorkflowStates(self._workflow.value + 1).name
        return False, f"非法操作！必须先完成 [{next_required_state}]。"
