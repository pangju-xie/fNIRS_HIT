import numpy as np
import pandas as pd
import os
import sys
import h5py
from datetime import datetime
from PyQt5.QtWidgets import QFileDialog, QMessageBox
import subprocess
import logging
import mne
import mne_nirs
import scipy.signal as signal
import scipy.interpolate as interpolate

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class fNIRS_Struct:
    def __init__(self, Wavelength=[750, 850], DPF=[3.0, 3.0]):
        if len(Wavelength) < 2:
            raise ValueError("At least two wavelengths are required for fNIRS calculations.")
        
        if len(DPF) != len(Wavelength):
            self.DPF = np.array([3.0] * len(Wavelength))  # 默认DPF值
        else:
            self.DPF = np.array(DPF)
            
        self.Wavelength = np.array(Wavelength)
        self.coef = np.zeros((len(Wavelength), 2))  # 消光系数矩阵
        
        if not os.path.exists('extinction_coefficients.csv'):
            raise FileNotFoundError("Extinction coefficients file 'extinction_coefficients.csv' not found.")
            
        self.ext_coef = pd.read_csv('extinction_coefficients.csv')
        for i, wl in enumerate(Wavelength):
            row = self.ext_coef[self.ext_coef['wavelength_nm'] == wl]
            if not row.empty:
                self.coef[i, 0] = row['Hb'].values[0]
                self.coef[i, 1] = row['HbO2'].values[0]
            else:
                raise ValueError(f"Extinction coefficients for wavelength {wl} nm not found.")
        self._calculate_D_matrix()
    
    def _calculate_D_matrix(self):
        """计算血氧计算矩阵 D""" 
        # 使用改进的比尔-朗伯定律计算矩阵 D
        Mat_A = np.dot(self.coef, np.diag(self.DPF))
        self.Mat_D = np.dot(np.linalg.pinv(Mat_A), np.eye(2))
        # return self.Mat_D
    
    def get_D_matrix(self):
        """返回血氧计算矩阵 D"""
        return self.Mat_D


class fNIRS:
    def __init__(self, subject_info, Wavelength=[750, 850], DPF=[3.0, 3.0], sample_rate=10):
        
        
        self.struct = fNIRS_Struct(Wavelength, DPF)
        
        # fNIRS Montage 配置
        self.source_num = 0
        self.detector_num = 0
        self.Source_Montage = {}  # 光源定位{'S1':(x,y,z), ...}
        self.Detector_Montage = {} # 探测器定位{'D1':(x,y,z), ...}
        self.channels = []      # 通道配置 ['S1-D1', 'S1-D2', ...]
        self.long_channel_mask = []  # 长距离通道索引 [1, 1, 0, ...]
        self.channel_num = 0
        
        self.sample_rate = sample_rate  # 采样率
        self.set_done = False
        
        self.time = np.array([])
        self.raw = np.array([]).reshape(0, 0, 0)  # [time, wavelength, channel]
        self.OD = np.array([]).reshape(0, 0, 0)   # [time, wavelength, channel]
        self.hemoglobin = np.array([]).reshape(0, 0, 0)  # [time, chromophore, channel]
        self.get_packet = np.array([])
        
        # SNIRF相关属性
        self.subject_info = subject_info    
        self.measurement_info = {}
        
    def getSampleRate(self):
        """获取采样率"""
        return self.sample_rate
    
    def setSampleRate(self, rate):
        """设置采样率"""
        self.sample_rate = rate
        logger.info(f"fnirs set sample rate: {rate}.")
    
    def get_channels(self):
        """获取通道配置"""
        return self.channels.copy()
    
    def getSources(self):
        """获取光源信息
        
        Returns:
            dict: 光源位置信息 {'S1': (x, y, z), 'S2': (x, y, z), ...}
        """
        return self.Source_Montage.copy()
    
    def getDetectors(self):
        """获取探测器信息
        
        Returns:
            dict: 探测器位置信息 {'D1': (x, y, z), 'D2': (x, y, z), ...}
        """
        return self.Detector_Montage.copy()
    
    def getChannels(self):
        """获取通道信息
        
        Returns:
            dict: 包含通道详细信息的字典
        """
        channels_info = {
            'channels': self.channels.copy(),
            'channel_num': self.channel_num,
            'wavelengths': self.struct.Wavelength.copy(),
            'long_channel_mask': self.long_channel_mask.copy()
        }
        
        return channels_info
    
    def setMontage(self, montage):
        """设置蒙太奇配置
        
        Args:
            sources: 光源位置字典 {'S1': (x, y, z), ...}
            detectors: 探测器位置字典 {'D1': (x, y, z), ...}
            channels: 通道配置列表 [('S1', 'D1'), ('S1', 'D2'), ...]
        """
        s_num = montage[0]
        d_num = montage[1]
        sources = montage[2]
        detectors = montage[3]
        channels = montage[4]

        self.Source_Montage = sources.copy()
        self.Detector_Montage = detectors.copy()
        self.source_num = s_num
        self.detector_num = d_num
        self.channels = channels.copy()
        self.channel_num = len(channels)
        
        self.set_done = True
        
        logger.info(f"fnirs set montage done. valid channel number:{self.channel_num}.")
        # 初始化数据数组
        self.raw = np.array([]).reshape(0, len(self.struct.Wavelength), self.channel_num)
        self.OD = np.array([]).reshape(0, len(self.struct.Wavelength), self.channel_num)
        self.hemoglobin = np.array([]).reshape(0, 2, self.channel_num)  # 2 for Hb and HbO2

    def CleanData(self):
        self.raw = np.array([]).reshape(0, len(self.struct.Wavelength), self.channel_num)
        self.OD = np.array([]).reshape(0, len(self.struct.Wavelength), self.channel_num)
        self.hemoglobin = np.array([]).reshape(0, 2, self.channel_num)
        
    def updateData(self, packet_id, data):
        """更新传感器数据
        
        Args:
            data: 原始数据包 (字节数组)
        """
        if not self.set_done:
            raise RuntimeError("Channel configuration not set.")
        
        try:
            # 解析包ID
            self.get_packet = np.append(self.get_packet, packet_id)
            times = (packet_id - self.get_packet[0]) / self.sample_rate
            self.time = np.append(self.time, times) # type: ignore
            
            # 初始化数据行
            dataline = np.zeros((1, len(self.struct.Wavelength), self.channel_num))
            
            # 处理每个通道的红光和红外光数据
            for ch_idx in range(self.channel_num):
                for wl_idx in range(len(self.struct.Wavelength)):
                    data_idx = ch_idx * len(self.struct.Wavelength) + wl_idx
                    val = data[data_idx*3+2] | (data[data_idx*3+1] << 8) | (data[data_idx*3+0] << 16)  # 24位补码
                    
                    # 计算数据值
                    if val > 0X7FFFFF:
                        val = 0XFFFFFF - val  # 负数转正数
                    if val == 0:
                        val = 1  # 避免log(0)
                    
                    val = val * 3300 / 0x780000  # 计算电压值(mV), Vref=3.3V
                    dataline[0, wl_idx, ch_idx] = val

            self._calculate_fnirs_data(dataline)
            
        except Exception as e:
            logger.error(f"Error updating data: {e}")

    def _calculate_strength(self):  # 获取一段时间内的平均原始光强
        if self.raw.shape[0] < 10:
            return np.zeros(self.channel_num)
        vol = np.zeros(self.channel_num)
        for ch_idx in range(self.channel_num):
            vol[ch_idx] = np.min(np.mean(self.raw[-10:, :, ch_idx], axis=0))
        return vol  # todo: 数据为空时返回空ndarray可能报错, 改为直接补0; 若检测过程中断会发送先前数据, 此处需进行检测改发0

    def _calculate_sci(self):  # 获取头皮耦合指数
        # 使用最近的40个数据进行计算, 不足40则全返回0
        # print(f"_calculate_sci raw.shape: {self.raw.shape}")
        # print(f"_calculate_sci raw: {self.raw}")

        if self.raw.shape[0] < 40:
            return np.zeros(self.channel_num)
        sci = np.zeros(self.channel_num)
        t = self.time[-40:]
        for ch_idx in range(self.channel_num):
            raw_750 = self.raw[-40:, 0, ch_idx]
            raw_850 = self.raw[-40:, 1, ch_idx]
            # 等间距插值
            t_new = np.linspace(t[0], t[-1], 40)
            raw_750 = np.interp(t_new, t, raw_750)
            raw_850 = np.interp(t_new, t, raw_850)
            # 计算od
            od_750 = -np.log(raw_750 / np.mean(raw_750))
            od_850 = -np.log(raw_850 / np.mean(raw_850))
            # 替换nan为0
            od_750[np.isnan(od_750)] = 0
            od_850[np.isnan(od_850)] = 0
            # 0.5~2.5Hz滤波
            fil = signal.butter(4, [0.5, 2.5], 'bandpass', fs=self.sample_rate)
            od_750 = signal.filtfilt(fil[0], fil[1], od_750)
            od_850 = signal.filtfilt(fil[0], fil[1], od_850)
            # 计算SCI
            sci[ch_idx] = np.corrcoef(od_750, od_850)[0, 1]
        return sci
        
    def get_quality(self, method_index):
        """获取用于信号质量评估的参数"""
        if method_index == 0:
            return self._calculate_strength()
        elif method_index == 1:
            return self._calculate_sci()
        else:
            raise ValueError("Invalid method index")

    def _calculate_fnirs_data(self, dataline):
        """计算fNIRS数据"""
        # 添加原始数据
        self.raw = np.concatenate((self.raw, dataline), axis=0)
        
        # 计算光学密度
        OD = -np.log(dataline)
        self.OD = np.concatenate((self.OD, OD), axis=0)
        
        # 计算血红蛋白浓度
        hemoglobin = np.zeros((1, 2, self.channel_num))
        for ch_idx in range(self.channel_num):
            od_channel = OD[0, :, ch_idx]
            hb_values = np.dot(self.struct.get_D_matrix(), od_channel)
            hemoglobin[0, :, ch_idx] = hb_values
        
        self.hemoglobin = np.concatenate((self.hemoglobin, hemoglobin), axis=0)
    
    def exportData(self, subfileix='XFW', file_path=None, data_type='snirf'):
        """导出数据到文件
        
        Args:
            subfileix: 子文件夹名称
            file_path: 文件路径，如果为None则自动生成
            data_type: 数据类型 ('snirf', 'csv', 'all')
        """
        if len(self.time) == 0: # type: ignore
            raise ValueError("没有可导出的数据")
        
        # 自动生成文件路径
        if file_path is None:
            file_path = self._generate_filename(subfileix, data_type)
        
        try:
            if data_type in ['snirf', 'all']:
                snirf_path = file_path if file_path.endswith('.snirf') else file_path.replace('.csv', '.snirf')
                self._save_snirf_data(snirf_path)
            
            if data_type in ['csv', 'all']:
                csv_path = file_path if file_path.endswith('.csv') else file_path.replace('.snirf', '.csv')
                self._save_csv_data(csv_path)
            
            return file_path
            
        except Exception as e:
            print(f"fNIRS Error exporting data - {e}")
            raise

    def SaveData(self, username, show_dialog=True, data_type='snirf'):
        """保存数据到文件（兼容原始接口）"""
        try:
            file_path = self.exportData(username, data_type=data_type)
            
            if show_dialog:
                QMessageBox.information(None, "保存成功", f"数据已保存到: {file_path}", QMessageBox.Ok)
                self._open_file_location(file_path)
            
            return file_path
            
        except Exception as e:
            error_msg = f"保存数据失败: {str(e)}"
            print(f"fNIRS: {error_msg}")
            if show_dialog:
                QMessageBox.critical(None, "保存失败", error_msg, QMessageBox.Ok)
            raise

    def loadSnirfData(self, file_path):
        """从SNIRF文件加载数据
        
        Args:
            file_path: SNIRF文件路径
        """
        try:
            with h5py.File(file_path, 'r') as f:
                # 读取基本信息
                if 'formatVersion' in f:
                    format_version = f['formatVersion'][()].decode() if isinstance(f['formatVersion'][()], bytes) else f['formatVersion'][()] # type: ignore
                    print(f"SNIRF Format Version: {format_version}")
                
                # 读取数据
                if 'nirs/data1/dataTimeSeries' in f:
                    data = f['nirs/data1/dataTimeSeries'][()] # type: ignore
                    time = f['nirs/data1/time'][()] # type: ignore
                    
                    # 重塑数据格式 [time, wavelength, channel]
                    n_time, n_data_points = data.shape # type: ignore
                    n_wavelengths = len(self.struct.Wavelength)
                    n_channels = n_data_points // n_wavelengths
                    
                    self.raw = data.reshape(n_time, n_wavelengths, n_channels) # type: ignore
                    self.time = time
                    
                    # 重新计算OD和血红蛋白
                    self.OD = -np.log(self.raw)
                    self._recalculate_hemoglobin()
                
                # 读取蒙太奇信息
                if 'nirs/probe' in f:
                    self._load_montage_from_snirf(f['nirs/probe'])
            
            print(f"Successfully loaded data from {file_path}")
            
        except Exception as e:
            print(f"Error loading SNIRF data: {e}")
            raise

    def _save_snirf_data(self, file_path):
        """保存数据为SNIRF格式"""
        try:
            with h5py.File(file_path, 'w') as f:
                # 基本信息
                f.create_dataset('formatVersion', data='1.0')
                
                # 创建nirs组
                nirs_group = f.create_group('nirs')
                data_group = nirs_group.create_group('data1')
                
                # 保存时间序列数据
                # 重塑数据: [time, wavelength*channel]
                reshaped_data = self.raw.reshape(len(self.time), -1) # type: ignore
                data_group.create_dataset('dataTimeSeries', data=reshaped_data)
                data_group.create_dataset('time', data=self.time)
                
                # 测量列表
                measurement_list = []
                for ch_name in self.channels:
                    node = ch_name.split('-')
                    src_idx = int(node[0][1:])
                    det_idx = int(node[1][1:])
                    for wl_idx, wavelength in enumerate(self.struct.Wavelength):
                        measurement_list.append([
                            src_idx,  # sourceIndex (1-based)
                            det_idx,  # detectorIndex (1-based)
                            1,        # wavelengthIndex
                            1,        # dataType (1 for intensity)
                            1         # dataTypeIndex
                        ])
                
                data_group.create_dataset('measurementList', data=measurement_list)
                
                # 探针信息
                probe_group = nirs_group.create_group('probe')
                
                # 波长
                probe_group.create_dataset('wavelengths', data=self.struct.Wavelength)
                
                # 源位置
                source_pos = np.array([list(pos) for pos in self.Source_Montage.values()])
                if len(source_pos) > 0:
                    probe_group.create_dataset('sourcePos3D', data=source_pos)
                
                # 探测器位置
                detector_pos = np.array([list(pos) for pos in self.Detector_Montage.values()])
                if len(detector_pos) > 0:
                    probe_group.create_dataset('detectorPos3D', data=detector_pos)
                
                # 受试者信息
                if self.subject_info:
                    subject_group = nirs_group.create_group('metaDataTags')
                    for key, value in self.subject_info.items():
                        if isinstance(value, str):
                            subject_group.create_dataset(key, data=value.encode('utf-8'))
                        else:
                            subject_group.create_dataset(key, data=value)
            
            print(f"SNIRF data saved to {file_path}")
            
        except Exception as e:
            print(f"Error saving SNIRF data: {e}")
            raise

    def _save_csv_data(self, file_path):
        """保存数据为CSV格式（兼容性）"""
        # 保存血红蛋白数据
        save_data = self.hemoglobin.reshape(-1, 2*self.channel_num)
        
        # 生成列名
        column_names = [f"{ch}_Hb" for ch in self.channels] + [f"{ch}_HbO2" for ch in self.channels]
        column_names = ["Time"] + column_names
        
        # 创建DataFrame并保存
        if self.time.shape[0] != save_data.shape[0]: # type: ignore
            raise ValueError("时间数据和血氧数据长度不匹配。")
        
        df = pd.DataFrame(np.column_stack([self.time, save_data]), columns=column_names) # type: ignore
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        print(f"CSV data saved to {file_path}")

    def _recalculate_hemoglobin(self):
        """重新计算血红蛋白浓度"""
        n_time = self.OD.shape[0]
        self.hemoglobin = np.zeros((n_time, 2, self.channel_num))
        
        for t in range(n_time):
            for ch_idx in range(self.channel_num):
                od_channel = self.OD[t, :, ch_idx]
                hb_values = np.dot(self.struct.get_D_matrix(), od_channel)
                self.hemoglobin[t, :, ch_idx] = hb_values

    def _load_montage_from_snirf(self, probe_group):
        """从SNIRF文件加载蒙太奇信息"""
        try:
            if 'sourcePos3D' in probe_group:
                source_pos = probe_group['sourcePos3D'][()]
                self.Source_Montage = {f'S{i+1}': tuple(pos) for i, pos in enumerate(source_pos)}
                self.source_num = len(source_pos)
            
            if 'detectorPos3D' in probe_group:
                detector_pos = probe_group['detectorPos3D'][()]
                self.Detector_Montage = {f'D{i+1}': tuple(pos) for i, pos in enumerate(detector_pos)}
                self.detector_num = len(detector_pos)
            
        except Exception as e:
            print(f"Error loading montage from SNIRF: {e}")

    def _generate_filename(self, subfileix="", data_type='snirf'):
        """生成文件名"""
        base_dir = f"saved_data/{subfileix}" if subfileix else "saved_data"
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if data_type == 'snirf':
            filename = f"fNIRS_{timestamp}.snirf"
        else:
            filename = f"fNIRS_{timestamp}.csv"
            
        return os.path.join(base_dir, filename)

    def _open_file_location(self, file_path):
        """打开文件所在文件夹"""
        try:
            folder_path = os.path.dirname(file_path)
            if os.name == 'nt':  # Windows
                subprocess.Popen(f'explorer "{folder_path}"')
            elif os.name == 'posix':  # macOS/Linux
                if sys.platform == 'darwin':
                    subprocess.Popen(['open', folder_path])
                else:
                    subprocess.Popen(['xdg-open', folder_path])
        except Exception as e:
            print(f"fNIRS: Error opening file location - {e}")

    def setSubjectInfo(self, subject_info):
        """设置受试者信息"""
        self.subject_info = subject_info.copy()

    def getSubjectInfo(self):
        """获取受试者信息"""
        return self.subject_info.copy()

    def __str__(self):
        """字符串表示"""
        return f"fNIRS(channels={self.channel_num}, samples={len(self.time)}, sources={self.source_num}, detectors={self.detector_num})" # type: ignore