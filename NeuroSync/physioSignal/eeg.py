# physioSignal/eeg.py
import numpy as np
import logging
import scipy.signal as signal

logger = logging.getLogger(__name__)

class EegProcessor:
    """
    脑电信号处理核心模块 (EEG Processor)
    负责：通道拓扑解析、矩阵动态重置、原始信号缓冲与滤波处理
    """
    def __init__(self, sample_rate=500):
        # 1. 基础物理参数
        self.sample_rate = sample_rate
        
        # 2. 拓扑参数初始化 (与 fNIRS 完全对齐)
        self.channels = []          # 存放通道列表，如 ['E1', 'E2', 'E3']
        self.channel_num = 0        # 有效通道数量
        self.eeg_montage = {}       # 存放通道键值对映射，如 {'E1': 'Cz', 'E2': 'Oz'}
        self.is_configured = False  # 配置完成标志
        
        # 初始化底层数据结构
        self.reset_data()

    def set_sample_rate(self, sample_rate: int):
        """动态更新采样率，并可在此时重置可能依赖采样率的滤波器"""
        self.sample_rate = sample_rate
        logger.info(f"EEG 处理器采样率已更新为: {self.sample_rate} Hz")

    def set_config(self, montage_dict: dict):
        """
        根据上位机下发的字典动态解析 EEG 通道配置
        """
        self.montage_dict = montage_dict
        
        # 1. 基础数量与通道列表解析
        self.channels = montage_dict.get('eeg_channels', [])
        self.channel_num = montage_dict.get('eeg_num', 0)
        
        self.eeg_montage.clear()
        self.is_configured = False

        if self.channel_num > 0:
            # 2. 解析电极的具体键值对 (提取 10-5 标准名称)
            details_dict = montage_dict.get('eeg_details', {})
            for e_alias, e_info in details_dict.items():
                # 提取出例如 'E1': 'Cz' 的纯净映射，方便后续画图打标签
                self.eeg_montage[e_alias] = e_info.get('standard_name', '')
                
            # 3. 如果后续做脑电地形图 (Topoplot)，可以在这里额外提取物理坐标 coord
            self.channel_coords = {}
            for e_alias, e_info in details_dict.items():
                self.channel_coords[e_alias] = e_info.get('coord', (0, 0))

            # 4. 重置底层数据矩阵，并点亮配置完成标志
            self.reset_data()
            self.is_configured = True
            
            logger.info(f"EEG 处理器配置解析完毕！")
            logger.info(f"-> 有效通道数: {self.channel_num}")
            logger.info(f"-> 通道映射表: {self.eeg_montage}")
        else:
            logger.warning("下发的 EEG 配置中没有有效的通道，请检查配置！")

    def reset_data(self):
        """
        清空内部缓冲数据，根据新的通道数重新分配 NumPy 矩阵内存。
        有效防止动态增减通道导致的数组越界崩溃。
        """
        # 1. 原始 ADC 数据矩阵 (时间长度, 通道数量)
        self.raw = np.empty((0, self.channel_num))
        
        # 2. 时间戳矩阵
        self.time = np.empty((0,))
        
        # 3. 滤波后的干净信号矩阵 (预留)
        self.filtered = np.empty((0, self.channel_num))
        
        # 4. 阻抗值缓存 (如有阻抗测试功能)
        self.impedance = np.zeros(self.channel_num)

        logger.info(f"底层 EEG 数据矩阵已重置: 维度适配为 (N, {self.channel_num})")

    def process_packet(self, packet_id: int, raw_payload: list):
        """
        处理底层传来的 UDP 原始数据包
        :param packet_id: 协议解包后的包序号
        :param raw_payload: 剥离帧头后的有效数据字节流
        """
        if not self.is_configured or self.channel_num == 0:
            return
            
        # TODO: 1. 执行字节流拼接 (如 24位 或 16位 有符号补码转换)
        # TODO: 2. 将电压值 vstack 到 self.raw 中
        # TODO: 3. 执行巴特沃斯滤波 (例如 0.5-45Hz 频带)
        pass