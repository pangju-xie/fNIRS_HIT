import numpy as np
import pandas as pd
import os
import csv
from datetime import datetime
from PyQt5.QtWidgets import QFileDialog, QMessageBox
import subprocess
class Sensor:
    def __init__(self, id, type):
        self.id = id   # mac低3字节
        self.type = type  # 传感器类型
        # self.channel = []  # 传感器通道
        # self.channel_len = 0  # 通道长度
        self.first = True  # 是否为第一包数据
        self.first_res = np.array([])  # 第一包数据
        self.time = np.array([])
        self.raw = np.array([])  # fnirs/nirs: 光电信号 格式: [[packetId, Red, Ir]]
        self.OD = np.array([])  # fnirs/nirs: 光电信号对数 格式: [[packetId, od1, od2, ...]]
        self.resolved = np.array([])  # fnirs/nirs: 血氧数据 格式: [[packetId, hb, hbo2]]
        self.D = np.array([[ 0.91903065, -0.67310409],[-0.44996019,  1.36821268]])
        
    def setChannel(self, channel):
        self.channel = channel
        self.channel_len = len(self.channel) if self.channel is not None else 0

    def ResetData(self):
        self.first = True
        self.first_res = np.array([])  # 第一包数据
        # print("reset data buf size: ", self.channel_len)
        self.time = np.zeros([0])
        self.raw = np.zeros([0, 2, self.channel_len])
        self.OD = np.zeros([0, 2, self.channel_len])
        self.resolved = np.zeros([0, 2, self.channel_len])

    def Update(self, data):
        if self.type == 4:
            packet_id = data[-1] | (data[-2] << 8) | (data[-3] << 16) | (data[-4] << 24)
            self.time = np.append(self.time, packet_id)
            dataline = np.zeros([1,self.channel_len * 2]) # 初始化数据行, 包含packet_id和每个通道的红光和红外光数据
            for i in range(self.channel_len * 2):  # 遍历数据: ch1-red, ch1-ir, ch2-red, ...  每段数据3个字节
                val = data[i*3+2] | (data[i*3+1] << 8) | (data[i*3+0] << 16)    #24位补码
                # 计算数据值，手册P25
                if(val > 0X7FFFFF):
                    val = 0XFFFFFF - val    # val为负数，转为正数
                if val == 0:
                    val = 1
                val = val * 5000 / 0x780000   # 计算电压值, Vref=5V, val ~[0, 1.06*Vref]
                dataline[0, i] = val  # 将计算后的值存入数据行
            dataline = np.reshape(dataline, (1, -1, 2)).transpose(0,2,1)  # 转置为2行, 每行对应一个通道的红光和红外光数据
            # print("dataline:", dataline)
            # print("dataline shape:", dataline.shape, "raw shape:", self.raw.shape)
            self.raw = np.concatenate((self.raw, dataline), axis=0)

            # 计算血氧数据
            od = np.log(dataline)
            self.OD = np.concatenate((self.OD, od), axis=0 )  # 将对数数据添加到OD数组
            # od = np.log(self.raw[0,1:]) - np.log(dataline[0, 1:])
            # 750 / 850
            # Hb 1405.24 518
            # HbO2 691.32 1058
            # DPF 1.02 0.91 (*6.32)
            # 距离d暂未加入, 因此计算得到的是相对数值
            
            oxy = np.expand_dims(np.dot(self.D, od.squeeze()), axis = 0)  # 计算血氧数据
            if self.first:
                self.first = False
                self.first_res = oxy.copy()
                # print("first res shape:", self.first_res.shape)
            oxy = oxy-self.first_res
                
            # print("oxy shape:", oxy.shape, "resolved shape:", self.resolved.shape)
            self.resolved = np.concatenate((self.resolved, oxy), axis=0)
            
    def SaveData(self):
        # 保存数据到文件
        # 1. 指定基础保存路径（可自定义或让用户选择）
        base_dir = "saved_data"  # 默认文件夹名称
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)  # 自动创建文件夹
        
        # 2. 生成时间戳文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data_{timestamp}.csv"
        save_path = os.path.join(base_dir, filename)
        
        # 3. 获取要保存的数据（假设 self.data 是你要保存的NumPy数组/Pandas DataFrame/列表）
        # 示例数据格式（替换为你的实际数据）：
        n_time, n_type, n_channel = self.raw.shape
        if n_time == 0:
            raise ValueError("没有可保存的数据")
        else:
            save_data = self.raw.reshape(n_time, -1)    # 展平为二维数组，行数为时间点数，列数为数据类型*通道数
            save_ch_name = [f"S{ch[0]}_D{ch[1]}_Red" for ch in self.channel] + [f"S{ch[0]}_D{ch[1]}_Ir" for ch in self.channel  ]  # 生成列名
            save_ch_name = ["Time"] + save_ch_name  # 添加时间列名
            
            save_pd = pd.DataFrame(np.column_stack([self.time, save_data]), columns=save_ch_name)
        
        # 4. 写入CSV文件
        save_pd.to_csv(save_path, index=False, encoding='utf-8-sig')  # 使用utf-8-sig编码以支持中文

        # 5. 弹出保存成功提示
        QMessageBox.information(None, "保存成功", f"数据已保存到: {save_path}", QMessageBox.Ok)
        
        # 6. 打开文件所在文件夹
        folder_path = os.path.dirname(save_path)
        if os.name == 'nt':  # Windows
            subprocess.Popen(f'explorer "{folder_path}"')
        elif os.name == 'posix':  # macOS/Linux
            if sys.platform == 'darwin':
                subprocess.Popen(['open', folder_path])
            else:
                subprocess.Popen(['xdg-open', folder_path])
            



# import numpy as np

# a = np.array([
#     [1405.24 * 1.02, 691.32 * 1.02],
#     [518 * 0.91, 1058 * 0.91]
# ])

# a_inv = np.linalg.inv(a) * 1000

# print(a_inv)
