"""
数据模型与系统状态层 (Data Models & System State)

本包统一定义系统运行时所需的全部数据结构、常量和状态枚举：
- subjects.py: 受试者信息的标准数据类 (Dataclass)。
- config.py: 硬件通道映射 (如哪些通道是760nm，哪些是EEG)、采样率等。
- stats.py: 系统全局状态枚举 (如系统处于 IDLE, RECORDING, ERROR 状态)。
"""

# from .subjects import SubjectInfo
# from .config import HardwareConfig
# from .stats import SystemStatus

__all__ = [
    'SubjectInfo',
    'HardwareConfig',
    'SystemStatus'
]