# 储存全局数据, 如通道配置等

import numpy
from PyQt5.QtCore import pyqtSignal, QObject

# node_config示例
# {'enabled_sensors': ['fnirs'], 'sampling_rates': {'fnirs': 10}, 'total_channels': {'fnirs': 1}, 
#  'channel_counts': {'fnirs_sources': 8, 'fnirs_detectors': 8}, 
#  'enabled_channels': {'fnirs': {'S1-D1': {'node_pair': 'C1-Cz', 'distance': 35}}, 
#  'fnirssource': {1: {'node_name': 'C1', 'position_3d': (-34, 0, 81)}}, 
#  'fnirsdetect': {1: {'node_name': 'Cz', 'position_3d': (0, 0, 88)}}, 'eeg': {}}}

class DeviceData(QObject):
    fnirsSampleRateChanged = pyqtSignal()
    nodeConfigChanged = pyqtSignal()
    def __init__(self):
        super().__init__()

        self.fnirs_sample_rate = {}  # 暂未启用
        self.node_config = {}

    # 重写set方法
    @property
    def node_config(self):
        return self._node_config

    @node_config.setter
    def node_config(self, value):
        self._node_config = value
        self.nodeConfigChanged.emit()
    
    def set_fnirs_sample_rate(self, fnirs_sample_rate):
        self.fnirs_sample_rate = fnirs_sample_rate
        self.fnirsSampleRateChanged.emit()

    def get_fnirs_sample_rate(self):
        return self.fnirs_sample_rate