import numpy as np
import pandas as pd
import os
import sys
import csv
from datetime import datetime
from PyQt5.QtWidgets import QFileDialog, QMessageBox
import subprocess

class Sensor:
    def __init__(self, id, type):
        self.id = id   # mac低3字节
        self.type = type  # 传感器类型
        self.first = True  # 是否为第一包数据
        self.first_res = np.array([])  # 第一包数据
        self.time = np.array([])
        self.raw = np.array([])  # fnirs/nirs: 光电信号 格式: [[packetId, Red, Ir]]
        self.OD = np.array([])  # fnirs/nirs: 光电信号对数 格式: [[packetId, od1, od2, ...]]
        self.resolved = np.array([])  # fnirs/nirs: 血氧数据 格式: [[packetId, hb, hbo2]]
        
        # 血氧计算矩阵 (DPF corrected extinction coefficient matrix)
        self.D = np.array([[ 0.91903065, -0.67310409],[-0.44996019,  1.36821268]])
        
        # 通道配置
        self.channel = []
        self.channel_len = 0
        self.sample_rate = 100  # 默认采样率
        
        # 数据质量监控
        self.data_quality = {
            'missing_packets': 0,
            'invalid_values': 0,
            'last_packet_id': None
        }

    def setChannel(self, channel):
        """设置通道配置"""
        self.channel = channel
        self.channel_len = len(self.channel) if self.channel is not None else 0
        print(f"Sensor {self.id}: Set channels to {self.channel}, length: {self.channel_len}")

    def setSampleRate(self, rate):
        """设置采样率"""
        self.sample_rate = rate
        print(f"Sensor {self.id}: Sample rate set to {rate} Hz")

    def ResetData(self):
        """重置数据缓冲区"""
        self.first = True
        self.first_res = np.array([])
        self.time = np.zeros([0])
        self.raw = np.zeros([0, 2, self.channel_len]) if self.channel_len > 0 else np.array([])
        self.OD = np.zeros([0, 2, self.channel_len]) if self.channel_len > 0 else np.array([])
        self.resolved = np.zeros([0, 2, self.channel_len]) if self.channel_len > 0 else np.array([])
        
        # 重置数据质量监控
        self.data_quality = {
            'missing_packets': 0,
            'invalid_values': 0,
            'last_packet_id': None
        }
        print(f"Sensor {self.id}: Data buffers reset")

    def Update(self, data):
        """更新传感器数据"""
        if self.type == 4:  # fNIRS传感器
            try:
                # 解析包ID
                packet_id = data[-1] | (data[-2] << 8) | (data[-3] << 16) | (data[-4] << 24)
                
                # 数据质量检查
                self._check_data_quality(packet_id)
                
                self.time = np.append(self.time, packet_id)
                
                # 初始化数据行
                dataline = np.zeros([1, self.channel_len * 2])
                
                # 处理每个通道的红光和红外光数据
                for i in range(self.channel_len * 2):
                    val = data[i*3+2] | (data[i*3+1] << 8) | (data[i*3+0] << 16)  # 24位补码
                    
                    # 计算数据值
                    if val > 0X7FFFFF:
                        val = 0XFFFFFF - val  # 负数转正数
                    if val == 0:
                        val = 1  # 避免log(0)
                        self.data_quality['invalid_values'] += 1
                    
                    val = val * 5000 / 0x780000  # 计算电压值, Vref=5V
                    dataline[0, i] = val
                
                # 重塑数据格式: [时间点, 光类型(红/红外), 通道]
                dataline = np.reshape(dataline, (1, -1, 2)).transpose(0, 2, 1)
                self.raw = np.concatenate((self.raw, dataline), axis=0)

                # 计算血氧数据
                self._calculate_hemoglobin(dataline)
                
            except Exception as e:
                print(f"Sensor {self.id}: Error updating data - {e}")
                self.data_quality['invalid_values'] += 1

    def _check_data_quality(self, packet_id):
        """检查数据质量"""
        if self.data_quality['last_packet_id'] is not None:
            expected_id = (self.data_quality['last_packet_id'] + 1) % (2**32)
            if packet_id != expected_id:
                self.data_quality['missing_packets'] += 1
                print(f"Sensor {self.id}: Missing packet detected. Expected {expected_id}, got {packet_id}")
        
        self.data_quality['last_packet_id'] = packet_id

    def _calculate_hemoglobin(self, dataline):
        """计算血红蛋白浓度"""
        try:
            # 计算光学密度
            od = np.log(dataline)
            self.OD = np.concatenate((self.OD, od), axis=0)
            
            # 使用改进的比尔-朗伯定律计算血红蛋白浓度
            # 矩阵 D 已经包含了消光系数和DPF校正
            oxy = np.expand_dims(np.dot(self.D, od.squeeze()), axis=0)
            
            # 基线校正 - 相对于第一个测量值
            if self.first:
                self.first = False
                self.first_res = oxy.copy()
            
            oxy = oxy - self.first_res
            self.resolved = np.concatenate((self.resolved, oxy), axis=0)
            
        except Exception as e:
            print(f"Sensor {self.id}: Error calculating hemoglobin - {e}")

    def getTimeWindow(self, window_seconds=30):
        """获取指定时间窗口的数据"""
        if len(self.time) == 0:
            return np.array([]), np.array([])
        
        # 计算时间窗口
        current_time = self.time[-1]
        time_threshold = current_time - window_seconds * self.sample_rate
        
        # 找到时间窗口内的数据索引
        valid_indices = self.time >= time_threshold
        
        return self.time[valid_indices], self.resolved[valid_indices]

    def getStatistics(self):
        """获取数据统计信息"""
        stats = {
            'total_samples': len(self.time),
            'channels': self.channel_len,
            'sample_rate': self.sample_rate,
            'duration_seconds': len(self.time) / self.sample_rate if self.sample_rate > 0 else 0,
            'data_quality': self.data_quality.copy()
        }
        
        if len(self.resolved) > 0:
            stats.update({
                'hb_mean': np.mean(self.resolved[:, 0, :], axis=0).tolist(),
                'hb_std': np.std(self.resolved[:, 0, :], axis=0).tolist(),
                'hbo2_mean': np.mean(self.resolved[:, 1, :], axis=0).tolist(),
                'hbo2_std': np.std(self.resolved[:, 1, :], axis=0).tolist()
            })
        
        return stats

    def exportData(self, file_path=None, data_type='all'):
        """导出数据到文件
        
        Args:
            file_path: 文件路径，如果为None则自动生成
            data_type: 数据类型 ('raw', 'resolved', 'all')
        """
        if len(self.time) == 0:
            raise ValueError("没有可导出的数据")
        
        # 自动生成文件路径
        if file_path is None:
            file_path = self._generate_filename()
        
        try:
            if data_type in ['all', 'resolved'] and len(self.resolved) > 0:
                self._save_resolved_data(file_path)
            
            if data_type in ['all', 'raw'] and len(self.raw) > 0:
                raw_path = file_path.replace('.csv', '_raw.csv')
                self._save_raw_data(raw_path)
            
            # 保存统计信息
            stats_path = file_path.replace('.csv', '_stats.json')
            self._save_statistics(stats_path)
            
            return file_path
            
        except Exception as e:
            print(f"Sensor {self.id}: Error exporting data - {e}")
            raise

    def SaveData(self, show_dialog=True):
        """保存数据到文件（兼容原始接口）"""
        try:
            file_path = self.exportData()
            
            if show_dialog:
                QMessageBox.information(None, "保存成功", f"数据已保存到: {file_path}", QMessageBox.Ok)
                self._open_file_location(file_path)
            
            return file_path
            
        except Exception as e:
            error_msg = f"保存数据失败: {str(e)}"
            print(f"Sensor {self.id}: {error_msg}")
            if show_dialog:
                QMessageBox.critical(None, "保存失败", error_msg, QMessageBox.Ok)
            raise

    def _generate_filename(self):
        """生成文件名"""
        base_dir = "saved_data"
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sensor_id_str = f"{self.id[0]:02X}{self.id[1]:02X}{self.id[2]:02X}" if isinstance(self.id, list) else str(self.id)
        filename = f"sensor_{sensor_id_str}_{timestamp}.csv"
        
        return os.path.join(base_dir, filename)

    def _save_resolved_data(self, file_path):
        """保存处理后的血氧数据"""
        n_time, n_type, n_channel = self.resolved.shape
        
        # 重塑数据: [时间点, Hb_ch1, HbO2_ch1, Hb_ch2, HbO2_ch2, ...]
        save_data = np.zeros((n_time, n_channel * 2))
        for ch in range(n_channel):
            save_data[:, ch*2] = self.resolved[:, 0, ch]      # Hb
            save_data[:, ch*2+1] = self.resolved[:, 1, ch]    # HbO2
        
        # 生成列名
        column_names = []
        for ch_idx, ch in enumerate(self.channel):
            column_names.extend([f"S{ch[0]}_D{ch[1]}_Hb", f"S{ch[0]}_D{ch[1]}_HbO2"])
        
        column_names = ["Time"] + column_names
        
        # 创建DataFrame并保存
        df = pd.DataFrame(np.column_stack([self.time, save_data]), columns=column_names)
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        print(f"Sensor {self.id}: Resolved data saved to {file_path}")

    def _save_raw_data(self, file_path):
        """保存原始光电信号数据"""
        n_time, n_type, n_channel = self.raw.shape
        
        # 重塑数据: [时间点, Red_ch1, IR_ch1, Red_ch2, IR_ch2, ...]
        save_data = self.raw.reshape(n_time, -1)
        
        # 生成列名
        column_names = []
        for ch in self.channel:
            column_names.extend([f"S{ch[0]}_D{ch[1]}_Red", f"S{ch[0]}_D{ch[1]}_IR"])
        
        column_names = ["Time"] + column_names
        
        # 创建DataFrame并保存
        df = pd.DataFrame(np.column_stack([self.time, save_data]), columns=column_names)
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        print(f"Sensor {self.id}: Raw data saved to {file_path}")

    def _save_statistics(self, file_path):
        """保存统计信息到JSON文件"""
        import json
        
        stats = self.getStatistics()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        print(f"Sensor {self.id}: Statistics saved to {file_path}")

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
            print(f"Sensor {self.id}: Error opening file location - {e}")

    def loadData(self, file_path):
        """从文件加载数据"""
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # 恢复时间数据
            self.time = df['Time'].values
            
            # 恢复通道配置（从列名推断）
            data_columns = [col for col in df.columns if col != 'Time']
            channels = []
            
            for col in data_columns:
                if '_Hb' in col or '_HbO2' in col:
                    parts = col.split('_')
                    if len(parts) >= 2:
                        s = int(parts[0][1:])  # Remove 'S' prefix
                        d = int(parts[1][1:])  # Remove 'D' prefix
                        if [s, d] not in channels:
                            channels.append([s, d])
            
            self.setChannel(channels)
            
            # 恢复数据
            n_time = len(self.time)
            n_channel = len(channels)
            
            self.resolved = np.zeros((n_time, 2, n_channel))
            
            for ch_idx, ch in enumerate(channels):
                hb_col = f"S{ch[0]}_D{ch[1]}_Hb"
                hbo2_col = f"S{ch[0]}_D{ch[1]}_HbO2"
                
                if hb_col in df.columns:
                    self.resolved[:, 0, ch_idx] = df[hb_col].values
                if hbo2_col in df.columns:
                    self.resolved[:, 1, ch_idx] = df[hbo2_col].values
            
            print(f"Sensor {self.id}: Data loaded from {file_path}")
            return True
            
        except Exception as e:
            print(f"Sensor {self.id}: Error loading data from {file_path} - {e}")
            return False

    def __str__(self):
        """字符串表示"""
        return f"Sensor(id={self.id}, type={self.type}, channels={self.channel_len}, samples={len(self.time)})"