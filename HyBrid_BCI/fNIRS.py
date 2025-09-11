import numpy as np
import pandas as pd
import os
import sys
import csv
from datetime import datetime
from PyQt5.QtWidgets import QFileDialog, QMessageBox
import subprocess
import logging
import mne, mne_nirs


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class fNIRS_Struct:
    def __init__(self, Wavelength = [750, 850], DPF = [3.0, 3.0]):
        if len(Wavelength) < 2:
            raise ValueError("At least two wavelengths are required for fNIRS calculations.")
        
        if len(DPF) != len(Wavelength):
            self.DPF = np.array([3.0] * len(Wavelength))  # 默认DPF值
            
        self.Wavelength = Wavelength
        self.coef = np.zeros((len(Wavelength), 2))  # 消光系数矩阵
        
        if not os.path.exists('extinction_coefficients.csv'):
            raise FileNotFoundError("Extinction coefficients file 'extinction_coefficients.csv' not found.")
            
        self.ext_coef = pd.read_csv('extinction_coefficients.csv')
        for i, wl in enumerate(Wavelength):
            row = self.ext_coef[self.ext_coef['Wavelength'] == wl]
            if not row.empty:
                self.coef[i, 0] = row['Hb'].values[0]
                self.coef[i, 1] = row['HbO2'].values[0]
            else:
                raise ValueError(f"Extinction coefficients for wavelength {wl} nm not found.")
        self._calculate_D_matrix()
    
    def _calculate_D_matrix(self):
        """计算血氧计算矩阵 D""" 
        
        # 使用改进的比尔-朗伯定律计算矩阵 D
        Mat_A = np.dot(self.coef, self.DPF.T)
        self.Mat_D = np.dot(np.linalg.inv(np.dot(Mat_A.T, Mat_A)), Mat_A)
        
        return self.Mat_D
    
    def get_D_matrix(self):
        """返回血氧计算矩阵 D"""
        return self.Mat_D
    

class fNIRS:
    def _init__(self, Wavelength = [750, 850], DPF = [3.0, 3.0], sample_rate = 10):
        self.struct = fNIRS_Struct(Wavelength, DPF)
        
        #fnirs Monatage 配置
        self.source_num = 0
        self.detector_num = 0
        self.Source_Montage = {}  # 光源定位{'S1':(x,y,z）, ...}
        self.Detector_Montage = {} # 探测器定位{'D1':(x,y,z), ...}
        self.channel_name = []      # 通道配置 ['S1-D1', 'S1-D2, ...]
        self.channel_config = []    # 有效通道配置 []
        self.long_channel_mask = []  # 长距离通道索引 [1, 1, 0]
        self.channel_num = 0
        
        self.sample_rate = sample_rate  # 采样率
        self.set_done = False
        
        self.time = np.array([])
        self.raw = np.array([])
        self.OD = np.array([])
        self.hemoglobin = np.array([])
        self.get_packet = np.array([])
        
    def getSampleRate(self):
        return self.sample_rate
    
    def setSampleRate(self, rate):
        self.sample_rate = rate
    
    def loadMontage(self, MontageFile):
        """加载通道定位文件
        
        Args:
            MontageFile: 定位文件路径 (CSV格式)
        """
        if not os.path.exists(MontageFile):
            raise FileNotFoundError(f"Montage file '{MontageFile}' not found.")
        
        try:
            df = pd.read_csv(MontageFile)
            if 'Type' not in df.columns or 'ID' not in df.columns or 'X' not in df.columns or 'Y' not in df.columns or 'Z' not in df.columns:
                raise ValueError("Montage file must contain 'Type', 'ID', 'X', 'Y', and 'Z' columns.")
            
            self.Source_Montage.clear()
            self.Detector_Montage.clear()
            
            for _, row in df.iterrows():
                if row['Type'] == 'S':
                    self.Source_Montage[row['ID']] = (row['X'], row['Y'], row['Z'])
                elif row['Type'] == 'D':
                    self.Detector_Montage[row['ID']] = (row['X'], row['Y'], row['Z'])
            
            self.source_num = len(self.Source_Montage)
            self.detector_num = len(self.Detector_Montage)
            
            logger.info(f"Loaded montage with {self.source_num} sources and {self.detector_num} detectors.")
            
        except Exception as e:
            logger.error(f"Error loading montage: {e}")
            raise
        
    def saveMontage(self, MontageFile):
        """保存通道定位文件
        
        Args:
            MontageFile: 定位文件路径 (CSV格式)
        """
        try:
            data = []
            for id, (x, y, z) in self.Source_Montage.items():
                data.append({'Type': 'S', 'ID': id, 'X': x, 'Y': y, 'Z': z})
            for id, (x, y, z) in self.Detector_Montage.items():
                data.append({'Type': 'D', 'ID': id, 'X': x, 'Y': y, 'Z': z})
            
            df = pd.DataFrame(data)
            df.to_csv(MontageFile, index=False)
            logger.info(f"Montage saved to '{MontageFile}'.")
            
        except Exception as e:
            logger.error(f"Error saving montage: {e}")
            raise
    
    def _set_effective_channels(self, long_distance=3.0, short_distance=1.0):
        """根据定位计算有效通道
        
        Args:
            long_distance: 长距离阈值 (cm)
            short_distance: 短距离阈值 (cm)
        """
        if not self.Source_Montage or not self.Detector_Montage:
            raise ValueError("Source and Detector montages must be loaded before calculating channels.")
        
        self.channel_config.clear()
        self.long_channel_mask.clear()
        
        for s_id, s_pos in self.Source_Montage.items():
            self.channel_config.append(0)
            for d_id, d_pos in self.Detector_Montage.items():
                dist = np.sqrt((s_pos[0] - d_pos[0])**2 + (s_pos[1] - d_pos[1])**2 + (s_pos[2] - d_pos[2])**2)
                if long_distance + 0.5 >= dist >= long_distance - 0.5:
                    self.channel_config[s_id] |= (1 << d_id)
                    self.channel_name.append(f"S{s_id+1}-D{d_id+1}")
                    # self.channel_config.append([s_id, d_id])
                    self.long_channel_mask.append(1)
                elif short_distance + 0.2 >= dist >= short_distance - 0.2:
                    self.channel_config[s_id] |= (1 << d_id)
                    self.channel_name.append(f"S{s_id+1}-D{d_id+1}")
                    self.long_channel_mask.append(0)
        
        self.channel_num = len(self.channel_config)
        logger.info(f"Found {self.channel_num} effective channels.")
    
    def get_channel_config(self):
        return self.channel_config
    
        
    def updataData(self, data):
        """更新传感器数据
        
        Args:
            data: 原始数据包 (字节数组)
        """
        if not self.set_done:
            raise RuntimeError("Channel configuration not set.")
        
        try:
            # 解析包ID
            packet_id = data[-1] | (data[-2] << 8) | (data[-3] << 16) | (data[-4] << 24)
            self.get_packet = np.append(self.get_packet, packet_id)
            times = (packet_id - self.get_packet[0]) / self.sample_rate
            self.time = np.append(self.time, times)
            
            # 初始化数据行
            dataline = np.zeros([1, self.channel_num * 2])
            
            # 处理每个通道的红光和红外光数据
            for i in range(self.channel_num * 2):
                val = data[i*3+2] | (data[i*3+1] << 8) | (data[i*3+0] << 16)  # 24位补码
                
                # 计算数据值
                if val > 0X7FFFFF:
                    val = 0XFFFFFF - val  # 负数转正数
                if val == 0:
                    val = 1  # 避免log(0)
                
                val = val * 5000 / 0x780000  # 计算电压值, Vref=5V
                dataline[0, i] = val
            
            self._calculate_fnirs_data(dataline)
            
        except Exception as e:
            logger.error(f"Error updating data: {e}")
            
    def _calculate_fnirs_data(self, dataline):
         # 重塑数据格式: [时间点, 光类型(红/红外), 通道]
        dataline = np.reshape(dataline, (1, -1, 2)).transpose(0, 2, 1)
        self.raw = np.concatenate((self.raw, dataline), axis=0)
        
        # 计算光学密度
        OD = np.log(dataline)
        self.OD = np.concatenate((self.OD, OD), axis=0)
        
        # 计算血红蛋白浓度
        hemoglobin = np.expand_dims(np.dot(self.struct.get_D_matrix(), OD.squeeze()), axis=0)
        self.hemoglobin = np.concatenate((self.hemoglobin, hemoglobin), axis=0)
        
        
    def exportData(self, subfileix = 'XFW', file_path=None, data_type='all'):
        """导出数据到文件
        
        Args:
            file_path: 文件路径，如果为None则自动生成
            data_type: 数据类型 ('raw', 'hemoglobin', 'all')
        """
        if len(self.time) == 0:
            raise ValueError("没有可导出的数据")
        
        # 自动生成文件路径
        if file_path is None:
            file_path = self._generate_filename(subfileix)
        
        try:
            if data_type in ['all', 'hemoglobin'] and len(self.hemoglobin) > 0:
                self._save_hemoglobin_data(file_path)
            
            if data_type in ['all', 'raw'] and len(self.raw) > 0:
                raw_path = file_path.replace('.csv', '_raw.csv')
                self._save_raw_data(raw_path)
            
            
            return file_path
            
        except Exception as e:
            print(f"fNIRS Error exporting data - {e}")
            raise

    def SaveData(self, username, show_dialog=True):
        """保存数据到文件（兼容原始接口）"""
        try:
            file_path = self.exportData(username)
            
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

    def _generate_filename(self, subfileix=""):
        """生成文件名"""
        base_dir = "saved_data/" + subfileix
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fNIRS_{timestamp}.csv"
        return os.path.join(base_dir, filename)

    def _save_hemoglobin_data(self, file_path):
        """保存处理后的血氧数据"""
        # 重塑数据: [时间点, Hb_ch1, Hb_ch2, Hb_ch3, ..., HbO2_ch1, HbO2_ch2, ...]
        save_data = self.hemoglobin.reshape(-1, 2*self.channel_num)
        
        # 生成列名
        column_names = [s+'_Hb' for s in self.channel_name] + [s+'_HbO2' for s in self.channel_name]
        column_names = ["Time"] + column_names
        
        # 创建DataFrame并保存
        if self.time.shape[0] != save_data.shape[0]:
            raise ValueError("时间数据和血氧数据长度不匹配。")
        else:
            df = pd.DataFrame(np.column_stack([self.time, save_data]), columns=column_names)
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
            print(f"fNIRS hemoglobin data saved to {file_path}")

    def _save_raw_data(self, file_path):
        """保存原始光电信号数据"""
        # 重塑数据: [时间点, Red_ch1, IR_ch1, Red_ch2, IR_ch2, ...]
        save_data = self.raw.reshape(-1, 2*self.channel_num)
        
        # 生成列名
        column_names = [s+'_Red' for s in self.channel_name] + [s+'_IR' for s in self.channel_name]
        column_names = ["Time"] + column_names
        
        # 创建DataFrame并保存
        if self.time.shape[0] != save_data.shape[0]:
            raise ValueError("时间数据和血氧数据长度不匹配。")
        else:
            df = pd.DataFrame(np.column_stack([self.time, save_data]), columns=column_names)
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
            print(f"fNIRS Raw data saved to {file_path}")

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

    def __str__(self):
        """字符串表示"""
        return f"Sensor(fNIRS, channels={self.channel_num}, samples={len(self.time)})"
        
        
        
        



        
        
        
        
        
        
        
        
