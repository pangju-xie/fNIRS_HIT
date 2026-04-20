# physioSignal/fnirs.py
import numpy as np
import pandas as pd
import os, h5py
import logging
import mne
from scipy.signal import butter, filtfilt
from utils.paths import get_resource_path

logger = logging.getLogger(__name__)

class fNIRS_Struct:
    """光学生理参数与比尔-朗伯定律转换矩阵"""
    def __init__(self, wavelengths=[750, 850], dpf=[3.0, 3.0]):
        if len(wavelengths) < 2:
            raise ValueError("至少需要两种波长才能计算血氧。")
        
        self.wavelengths = np.array(wavelengths)
        self.dpf = np.array(dpf) if len(dpf) == len(wavelengths) else np.array([3.0] * len(wavelengths))
        self.coef = np.zeros((len(wavelengths), 2))
        
        # 建议：将 extinction_coefficients.csv 放到 assets 目录下
        ext_path = get_resource_path(os.path.join('assets', 'extinction_coefficients.csv'))
        if not os.path.exists(ext_path):
            raise FileNotFoundError(f"找不到消光系数文件: {ext_path}")
            
        self.ext_coef = pd.read_csv(ext_path)
        for i, wl in enumerate(wavelengths):
            row = self.ext_coef[self.ext_coef['wavelength_nm'] == wl]
            if not row.empty:
                self.coef[i, 0] = row['Hb'].values[0]
                self.coef[i, 1] = row['HbO2'].values[0]
            else:
                raise ValueError(f"未找到波长 {wl} nm 的消光系数。")
                
        self._calculate_d_matrix()
    
    def _calculate_d_matrix(self):
        Mat_A = np.dot(self.coef, np.diag(self.dpf))
        self.Mat_D = np.dot(np.linalg.pinv(Mat_A), np.eye(2))
    
    def get_d_matrix(self):
        return self.Mat_D

class fNIRSProcessor:
    """
    纯粹的 fNIRS 信号处理与缓存容器
    """
    def __init__(self, sample_rate=10, wavelengths=[750, 850], dpf=[3.0, 3.0]):
        self.struct = fNIRS_Struct(wavelengths, dpf)
        self.sample_rate = sample_rate
        
        # 蒙太奇配置
        self.channels = []
        self.channel_num = 0
        self.source_num = 0
        self.detector_num = 0
        self.source_montage = {}
        self.detector_montage = {}
        self.is_configured = False
        
        # 数据缓存 (使用动态追加的 numpy 数组，后期数据量大可优化为 deque 或预分配内存)
        self.time = np.array([])
        self.packet_ids = np.array([])
        self.raw = np.array([]).reshape(0, 0, 0)
        # self.base_hemo = np.array([]).reshape(0, 0, 0)
        
        self.stim_events = []

    def add_marker(self, key_val: int):
        """记录按键刺激时间戳 (相对于开始记录的秒数)"""
        if self.current_idx > 0:
            relative_time = self.current_idx / self.sample_rate
            self.stim_events.append((relative_time, key_val))
            logger.info(f"底层已记录 打标事件 {key_val} 于 {relative_time:.2f}s")
    
    def get_channels(self) -> list:
        """获取当前已配置的 fNIRS 通道对列表 (如 ['S1-D1', 'S1-D2'])"""
        # self.channels 在 set_config 时就已经解析并保存好了
        return self.channels
        
    def get_sample_rate(self) -> int:
        """获取当前 fNIRS 的采样率"""
        return self.sample_rate
    
    def set_sample_rate(self, sample_rate: int):
        """动态更新采样率，并重置可能依赖采样率的滤波器"""
        self.sample_rate = sample_rate
        logger.info(f"fNIRS 处理器采样率已更新为: {self.sample_rate} Hz")
        # 如果你后续有带通滤波器，可以在这里根据新的 sample_rate 重新设计滤波器系数
        
    def set_config(self, montage_dict: dict):
        """
        根据上位机下发的字典动态解析 fNIRS 通道配置
        """
        self.montage = montage_dict
        
        # 1. 基础数量与通道对解析
        self.channels = montage_dict.get('fnirs_pairs', [])
        self.channel_num = len(self.channels)
        self.source_num = montage_dict.get('source_num', 0)
        self.detector_num = montage_dict.get('detector_num', 0)
        
        self.source_montage.clear()
        self.detector_montage.clear()
        self.is_configured = False

        if self.channel_num > 0:
            # 2. 解析光源和探测器的具体键值对 (格式如 'S1': 'FC1')
            sources_dict = montage_dict.get('sources', {})
            for s_alias, s_info in sources_dict.items():
                self.source_montage[s_alias] = s_info.get('standard_name', '')
                
            detectors_dict = montage_dict.get('detectors', {})
            for d_alias, d_info in detectors_dict.items():
                self.detector_montage[d_alias] = d_info.get('standard_name', '')
                
            # 3. 提取通道物理距离 (为血氧浓度 MBLL 定律计算做准备)
            self.channel_info = []
            for pair in self.channels:
                try:
                    s_alias, d_alias = pair.split('-')
                    s_coord = sources_dict.get(s_alias, {}).get('coord', (0, 0))
                    d_coord = detectors_dict.get(d_alias, {}).get('coord', (0, 0))
                    
                    # 近似计算标准头模下的物理光程 (单位: mm)
                    dx = s_coord[0] - d_coord[0]
                    dy = s_coord[1] - d_coord[1]
                    dist_mm = (dx**2 + dy**2)**0.5 * 100 
                    
                    self.channel_info.append({
                        'name': pair,
                        'source_name': s_alias,
                        'detector_name': d_alias,
                        'distance_mm': dist_mm
                    })
                except Exception as e:
                    logger.warning(f"解析通道 {pair} 物理信息时出错: {e}")

            # 4. 重置底层数据矩阵，并点亮配置完成标志
            if hasattr(self, 'reset_data'):
                self.reset_data()
            self.is_configured = True
            
            logger.info(f"fNIRS 处理器配置解析完毕！")
            logger.info(f"-> 包含 {self.source_num} 个光源, {self.detector_num} 个探测器")
            logger.info(f"-> 有效通道数: {self.channel_num}")
            logger.info(f"-> 通道列表: {self.channels}")
        else:
            logger.warning("下发的 fNIRS 配置中没有有效的通道连接，请检查配置！")
            
    def reset_data(self):
        """清空并预分配数据矩阵"""
        self.max_capacity = self.sample_rate * 3600  # 1 小时的采样点数上限  
        self.current_idx = 0       # 核心游标指针
        
        # 使用 np.full 直接分配好固定大小的内存，初始值全部用 NaN 或 -1 占位
        self.time = np.full(self.max_capacity, np.nan)
        self.packet_ids = np.full(self.max_capacity, -1, dtype=np.int32)
        
        # 分配原始光强矩阵
        wl_num = len(self.struct.wavelengths)
        ch_num = self.channel_num
        self.raw = np.full((self.max_capacity, wl_num, ch_num), np.nan)
        
        self.stim_events = []
        
    def reset_quality_data(self):
        """
        进入或退出 Quality 阶段时调用此方法。
        初始化滑窗并清空缓存，绝不保存到硬盘。
        """
        # 5秒窗口，1秒步长
        self.quality_window_size = int(5 * self.sample_rate)
        self.quality_step_size = int(1 * self.sample_rate)

        self.quality_buffer = np.zeros((self.quality_window_size, len(self.struct.wavelengths), self.channel_num))
        
        self.quality_count = 0        # 用于计步（每满 1 秒触发一次）
        self.quality_ready = False    # 标记是否已经积攒了最初的 5 秒数据
        
    def _expand_capacity(self):
        """当预分配内存即将用尽时，将所有矩阵容量翻倍"""
        logging.info(f"触发内存矩阵自动扩容，当前容量: {self.max_capacity}...")
        old_capacity = self.max_capacity
        self.max_capacity *= 2
        
        # 利用 np.pad 在尾部追加 NaN
        pad_width = (0, self.max_capacity - old_capacity)
        self.time = np.pad(self.time, pad_width, constant_values=np.nan)
        self.packet_ids = np.pad(self.packet_ids, pad_width, constant_values=-1)
        
        # 多维矩阵的 pad: (前置追加, 后置追加)
        pad_multi = ((0, self.max_capacity - old_capacity), (0, 0), (0, 0))
        self.raw = np.pad(self.raw, pad_multi, constant_values=np.nan)
        

    def process_packet(self, packet_id: int, data_bytes: list, op_mode: int = 0):
        """
        统一的数据解包入口。
        :param op_mode: 0: Quality, 1: 仅看Raw, 2: 仅看Hemo, 3: 采Raw+看Raw, 4: 采Raw+看Hemo
        :return: (missing_ids, parsed_values, sci_results)
        """
        if not self.is_configured:
            return [], [], None

        # 1. 解析 24 位字节流，获得 shape 为 (1, wls, chs) 的 dataline
        dataline = self._decode_24bit_bytes(data_bytes)

        missing_ids = []
        sci_results = None
        parsed_values = []

        # ==========================================
        # 状态 0: Quality 阶段 (实时 SCI 节流更新，不落盘)
        # ==========================================
        if op_mode == 0:
            self.quality_buffer[:-1] = self.quality_buffer[1:]
            self.quality_buffer[-1] = dataline[0]
            self.quality_count += 1
            
            if not self.quality_ready:
                if self.quality_count >= self.quality_window_size:
                    self.quality_ready = True
                    self.quality_count = 0  
                    sci_results = self._calculate_sci()
            else:
                if self.quality_count >= self.quality_step_size:
                    self.quality_count = 0
                    sci_results = self._calculate_sci()
                    
            return missing_ids, parsed_values, sci_results

        # ==========================================
        # 状态 3, 4: 正式记录阶段 (填补丢包，【仅落盘原始光强 raw】)
        # ==========================================
        if op_mode in [3, 4]:
            if self.current_idx >= self.max_capacity - 5000:
                self._expand_capacity()

            if self.current_idx > 0:
                last_id = int(self.packet_ids[self.current_idx - 1])
                if packet_id > last_id + 1:
                    missing_count = packet_id - (last_id + 1)
                    if missing_count > 5000:
                        missing_count = 10
                        
                    missing_ids = list(range(last_id + 1, last_id + 1 + missing_count))
                    
                    start_idx = self.current_idx
                    end_idx = self.current_idx + missing_count
                    
                    # 仅复制并填补 raw 矩阵的数据，不再处理 od 和 hemoglobin
                    self.raw[start_idx:end_idx] = self.raw[self.current_idx - 1]
                    
                    for i, m_id in enumerate(missing_ids):
                        self.packet_ids[start_idx + i] = m_id
                        self.time[start_idx + i] = m_id / self.sample_rate

                    self.current_idx += missing_count

            self.time[self.current_idx] = packet_id / self.sample_rate
            self.packet_ids[self.current_idx] = packet_id
            self.raw[self.current_idx] = dataline[0]
            
            # 游标步进 (去除了 _calculate_mbll，彻底不存血氧)
            self.current_idx += 1

        # ==========================================
        # UI 数据“定制化”组装：发 Raw 还是现算 Heamo
        # ==========================================
        if op_mode in [1, 3]:  
            # Display Raw: 组装红光和红外光发给前端
            for ch_idx in range(self.channel_num):
                for wl_idx in range(len(self.struct.wavelengths)):
                    parsed_values.append(float(dataline[0, wl_idx, ch_idx]))
                    
        elif op_mode in [2, 4]:  
            safe_dataline = np.maximum(dataline[0], 1e-6)
            od_val = -np.log(safe_dataline)
            
            hemo_val = np.zeros((2, self.channel_num))
            for ch in range(self.channel_num):
                hemo_val[:, ch] = np.dot(self.struct.get_d_matrix(), od_val[:, ch]) * 100
                
            # self.base_hemo = hemo_val.copy() 
            # hemo_val = hemo_val - self.base_hemo

            # 组装格式依然保持一维列表，前端画布直接画，毫无察觉
            for ch_idx in range(self.channel_num):
                parsed_values.append(float(hemo_val[0, ch_idx])) # HbO
                parsed_values.append(float(hemo_val[1, ch_idx])) # HbR

        return missing_ids, parsed_values, sci_results


    def patch_packet(self, packet_id: int, data_bytes: list):
        """
        处理下位机发回来的补传数据 (修补之前留下的占位符)
        """
        # 查找这个 packet_id 当时在数组中被占位时的索引 (Index)
        indices = np.where(self.packet_ids == packet_id)[0]
        if len(indices) == 0:
            logger.debug(f"收到过期的补包 ID: {packet_id}，直接丢弃。")
            return
            
        target_idx = indices[0]
        
        # 解析真实的 24位 数据
        real_dataline = self._decode_24bit_bytes(data_bytes)
        self.raw[target_idx:target_idx+1, :, :] = real_dataline
        logger.info(f"Packet ID {packet_id} 补包数据已成功嵌入矩阵！")
    
    def _decode_24bit_bytes(self, data_bytes):
        """24位解包纯逻辑，返回 shape 为 (1, wls, chs) 的 ndarray"""
        dataline = np.zeros((1, len(self.struct.wavelengths), self.channel_num))
        for ch_idx in range(self.channel_num):
            for wl_idx in range(len(self.struct.wavelengths)):
                byte_idx = ch_idx * len(self.struct.wavelengths) + wl_idx
                # 拼接 24 位
                val = data_bytes[byte_idx*3+2] | (data_bytes[byte_idx*3+1] << 8) | (data_bytes[byte_idx*3+0] << 16)
                
                if val > 0X7FFFFF: val = 0XFFFFFF - val # 负数处理
                if val == 0: val = 1 # 防 log(0) 崩溃
                
                # 转化为电压 (Vref = 5.0V)
                dataline[0, wl_idx, ch_idx] = val * 5000 / 0x780000 
        return dataline
    
    def _calculate_sci(self):
        """
        提取 Red 和 IR 的心跳波段 (0.5~2.5Hz) 并计算皮尔逊相关系数。
        :return: 返回一个质量字典，如 {"S1-D1": 0.95, "S1-D2": 0.82}
        """
        import numpy as np
        from scipy.signal import butter, filtfilt
        
        sci_dict = {}  
        
        # 提取当前滑窗内的红光和红外光数据，shape: (window_size, channels)
        red_data = self.quality_buffer[:, 0, :]
        ir_data = self.quality_buffer[:, 1, :]
        
        # 构造带通滤波器 (0.5 - 2.5 Hz)，针对心跳频段
        nyq = 0.5 * self.sample_rate
        low = 0.5 / nyq
        high = 2.5 / nyq
        
        b, a = butter(2, [low, high], btype='band') # type: ignore
        # 沿时间轴(axis=0)进行滤波
        red_filtered = filtfilt(b, a, red_data, axis=0)
        ir_filtered = filtfilt(b, a, ir_data, axis=0)

        
        # 逐通道计算皮尔逊相关系数
        for ch in range(self.channel_num):
            ch_name = self.channels[ch]
            
            x = red_filtered[:, ch]
            y = ir_filtered[:, ch]
            
            std_x = np.std(x)
            std_y = np.std(y)
            
            # 防御性编程：避免除以 0
            if std_x == 0 or std_y == 0:
                sci_dict[ch_name] = 0.0
                continue
                
            cov = np.mean((x - np.mean(x)) * (y - np.mean(y)))
            r = cov / (std_x * std_y)
            
            sci_dict[ch_name] = np.abs(np.round(r, 2)) # 取绝对值，越接近 1 越好
            
        return sci_dict
        
    def export_snirf(self, save_dir: str, file_basename: str, start_time, patient_info: dict = None): # type: ignore
        """导出为国际标准的 .snirf 文件 (带患者详细信息与事件打标)"""
        if self.current_idx == 0:
            logging.warning("没有采集到任何数据，跳过导出 SNIRF。")
            return

        snirf_path = os.path.join(save_dir, f"{file_basename}.snirf")
        
        # 1. 极速切片剥离 NaN
        valid_time = self.time[:self.current_idx]
        valid_raw = self.raw[:self.current_idx] # shape: (time, wls, chs)
        
        try:
            with h5py.File(snirf_path, 'w') as f:
                # 根节点必须叫 /nirs
                nirs = f.create_group('nirs')
                
                # ==========================================
                # --- 1. MetaData 节点 (整合临床信息) ---
                # ==========================================
                meta = nirs.create_group('metaDataTags')
                
                # 【修改点】：若有详细字典则取真实姓名，否则用文件前缀兜底
                subject_id = file_basename.split('_')[0]
                if patient_info and "姓名" in patient_info:
                    subject_id = patient_info["姓名"]
                    
                meta.create_dataset('SubjectID', data=subject_id.encode('utf-8'))
                
                date_str = start_time.strftime('%Y-%m-%d')
                time_str = start_time.strftime('%H:%M:%S.000Z')
                meta.create_dataset('MeasurementDate', data=date_str.encode('utf-8'))
                meta.create_dataset('MeasurementTime', data=time_str.encode('utf-8'))
                
                meta.create_dataset('LengthUnit', data=b'cm')
                meta.create_dataset('TimeUnit', data=b's')
                meta.create_dataset('FrequencyUnit', data=b'Hz')
                
                # 👇【核心新增】：将患者字典里的所有临床特征遍历写入 HDF5
                if patient_info:
                    for key, val in patient_info.items():
                        # 过滤掉系统内部用的 UID 和访问时间，防冗余
                        if key not in ["UID", "最后访问"] and val != "":
                            meta.create_dataset(key, data=str(val).encode('utf-8'))
                
                # ==========================================
                # --- 2. Data 节点 (原封不动) ---
                # ==========================================
                data1 = nirs.create_group('data1')
                data1.create_dataset('time', data=valid_time)
                reshaped_raw = valid_raw.reshape((self.current_idx, -1))
                data1.create_dataset('dataTimeSeries', data=reshaped_raw)
                
                col_idx = 1
                max_src_idx = 1
                max_det_idx = 1
                for ch_name in self.channels:
                    parts = ch_name.split('-')
                    src_idx = int(parts[0].replace('S', ''))
                    det_idx = int(parts[1].replace('D', ''))
                    max_src_idx = max(max_src_idx, src_idx)
                    max_det_idx = max(max_det_idx, det_idx)
                        
                    for wl_idx, wl_val in enumerate(self.struct.wavelengths):
                        ml = data1.create_group(f'measurementList{col_idx}')
                        ml.create_dataset('sourceIndex', data=src_idx)   
                        ml.create_dataset('detectorIndex', data=det_idx) 
                        ml.create_dataset('wavelengthIndex', data=wl_idx+1)
                        ml.create_dataset('dataType', data=1) 
                        ml.create_dataset('dataTypeIndex', data=1)
                        col_idx += 1
                        
                # ==========================================
                # --- 3. Probe 节点 (原封不动) ---
                # ==========================================
                probe = nirs.create_group('probe')
                probe.create_dataset('wavelengths', data=self.struct.wavelengths) 
                src_pos = np.zeros((max_src_idx, 3)) 
                det_pos = np.zeros((max_det_idx, 3))
                probe.create_dataset('sourcePos3D', data=src_pos)
                probe.create_dataset('detectorPos3D', data=det_pos)

                # ==========================================
                # --- 4. Stimulus 节点 (打标事件落盘) ---
                # ==========================================
                if hasattr(self, 'stim_events') and len(self.stim_events) > 0:
                    from collections import defaultdict
                    # 将事件按照按键数值(0-9)进行分组
                    stims_grouped = defaultdict(list)
                    for t, val in self.stim_events:
                        # 国际标准: [onset_time, duration, value]
                        stims_grouped[val].append([t, 1.0, val]) 
                        
                    stim_idx = 1
                    for val, events in stims_grouped.items():
                        stim_group = nirs.create_group(f'stim{stim_idx}')
                        # 命名如 Event_1, Event_2
                        stim_group.create_dataset('name', data=f"Event_{val}".encode('utf-8'))
                        stim_group.create_dataset('data', data=np.array(events, dtype=np.float64))
                        stim_idx += 1
                
            logging.info(f"✅ SNIRF 格式数据已成功导出至: {snirf_path}")
            
        except Exception as e:
            logging.error(f"导出 SNIRF 文件失败: {e}", exc_info=True)