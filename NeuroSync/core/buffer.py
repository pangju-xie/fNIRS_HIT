# core/buffer.py
from PyQt5.QtCore import QObject, pyqtSignal
from collections import defaultdict
import logging, os

from utils.stats import SensorTypes, WorkflowStates

logger = logging.getLogger(__name__)

class DataBufferManager(QObject):
    """
    全局数据流与缓存管理器 (Data Router & Patch Manager)
    职责：
    1. 根据连接的设备类型，动态实例化并持有各模态的 Processor。
    2. 接收网络层发来的原始包，按模态精准分发。
    3. 维护丢包记账本，处理补全逻辑。
    """
    # 告诉 Controller 当前批次的补包已经齐了，可以请求发下一批了
    signal_batch_patched_done = pyqtSignal() 
    # 通知 UI 刷新指定模态的波形 (可携带 SensorTypes 整数)
    signal_update_plot = pyqtSignal(int) 
    signal_quality_updated = pyqtSignal(SensorTypes, dict)
    
    signal_raw_stream = pyqtSignal(object, list)

    def __init__(self, system_state):
        super().__init__()
        self.system_state = system_state
        self.processors = {}
        self.missing_packets_dict = defaultdict(list)
        self.current_patching_batch = [] 
        self.op_mode = 0
        self.current_round_task_queue = []
    # ==========================================
    # 模块一：处理器生命周期管理
    # ==========================================
    def init_processors(self, sensor_mode: SensorTypes):
        """
        根据设备握手时确认的模态 (如 EEG_FNIRS)，动态实例化所需的数据处理器。
        Controller 稍后可以直接通过 self.processors[SensorTypes.xxx] 获取它们下发配置。
        """
        self.processors.clear()
        
        if sensor_mode.value & SensorTypes.FNIRS.value:
            from physioSignal.fnirs import fNIRSProcessor 
            self.processors[SensorTypes.FNIRS] = fNIRSProcessor()
            logger.info("fNIRS Processor 已挂载至 Buffer 总线。")
            
        if sensor_mode.value & SensorTypes.EEG.value:
            from physioSignal.eeg import EegProcessor 
            self.processors[SensorTypes.EEG] = EegProcessor()
            logger.info("EEG Processor 已挂载至 Buffer 总线。")
            
    def reset_all(self):
        """清空所有处理器的数据缓存和丢包账本"""
        for processor in self.processors.values():
            if hasattr(processor, 'reset_data'):
                processor.reset_data()
        self.missing_packets_dict.clear()
        self.current_patching_batch.clear()

    # ==========================================
    # 模块二：数据分发与丢包记账 (实时流)
    # ==========================================            
    def start_recording(self, save_dir: str, file_basename: str):
        self.op_mode = 4
        self.session_dir = save_dir
        self.file_basename = file_basename
        
        # 建立黑匣子文件，路径为 data/受试者前缀/文件名.bin
        log_path = os.path.join(save_dir, "raw_payload_backup.bin")
        self.raw_log_file = open(log_path, 'wb')
        
        for processor in self.processors.items():
            if hasattr(processor[1], 'reset_data'):
                processor[1].reset_data()
                
    def stop_recording(self):
        if hasattr(self, 'raw_log_file') and self.raw_log_file:
            self.raw_log_file.flush()
            self.raw_log_file.close()
            self.raw_log_file = None
        self.op_mode = 2
            
    def handle_normal_data(self, sensor_type_val: int, packet_id: int, raw_payload: list):
        """处理 UDP 实时推流数据，根据全局状态进行数据分流"""
        target_sensor = SensorTypes(sensor_type_val)
        
        if self.op_mode >= 3 and hasattr(self, 'raw_log_file') and self.raw_log_file:
            self.raw_log_file.write(bytes(raw_payload))

        if target_sensor not in self.processors:
            return 
        processor = self.processors[target_sensor]
        if not getattr(processor, 'is_configured', True):
            return 

        missing_ids, parsed_values, sci_results = processor.process_packet(packet_id, raw_payload, op_mode=self.op_mode)

        # ==========================================
        # 分流 A：推给 Quality UI 更新颜色
        # ==========================================
        if sci_results is not None:
            if self.system_state.workflow < WorkflowStates.ACQUIRED:
                if target_sensor == SensorTypes.FNIRS:
                    self.signal_quality_updated.emit(target_sensor, sci_results)
                elif target_sensor == SensorTypes.EEG:
                    self.signal_quality_updated.emit(target_sensor, sci_results)
        
        # ==========================================
        # 分流 B：推给波形图
        # ==========================================
        if parsed_values and self.system_state.workflow >= WorkflowStates.QUALIFIED:
            self.signal_raw_stream.emit(target_sensor, parsed_values)
                
        # ==========================================
        # 分流 C：正式记录阶段，才计入丢包账本
        # ==========================================
        if self.op_mode >= 3:
            if missing_ids:
                self.missing_packets_dict[target_sensor].extend(missing_ids)

    # ==========================================
    # 模块三：丢包修补与销账 (补包流)
    # ==========================================
    def handle_patched_data(self, sensor_type_val: int, packet_id: int, patched_data: list):
        """处理下位机重传的历史补全数据，精准插入并销账"""
        try:
            target_sensor = SensorTypes(sensor_type_val)
        except ValueError:
            return

        if target_sensor not in self.processors:
            return

        # 1. 算法层插入修补数据 (要求 Processor 实现 patch_packet 方法)
        processor = self.processors[target_sensor]
        if hasattr(processor, 'patch_packet'):
            processor.patch_packet(packet_id, patched_data)
            
        # 2. 定向销账
        if target_sensor in self.missing_packets_dict and packet_id in self.missing_packets_dict[target_sensor]:
            self.missing_packets_dict[target_sensor].remove(packet_id)
            
        if packet_id in self.current_patching_batch:
            self.current_patching_batch.remove(packet_id)

        # 3. 如果当前追踪的这一小批数据收齐了，发送信号通知 Controller
        if len(self.current_patching_batch) == 0:
            self.signal_batch_patched_done.emit()

    def get_total_missing_count(self) -> int:
        """获取所有模态总计丢失的包数量"""
        return sum(len(ids) for ids in self.missing_packets_dict.values())

    def prepare_patching_round(self):
        """
        将当前 missing_packets_dict 中所有未收到的包，按每组 50 个切分，加入本轮任务队列。
        """
        self.current_round_task_queue.clear()
        for s_type, ids in self.missing_packets_dict.items():
            if not ids: continue
            # 将该模态丢失的包按 50 个一组切片
            for i in range(0, len(ids), 50):
                batch = ids[i : i + 50]
                self.current_round_task_queue.append((s_type, batch))

    def pop_next_patch_batch(self) -> tuple:
        """从本轮任务队列中取出下一批，但不从总账本中删除"""
        if self.current_round_task_queue:
            s_type, batch = self.current_round_task_queue.pop(0)
            self.current_patching_batch = batch.copy()
            return s_type, batch
        return None, []

    def handle_patched_data_received(self, target_sensor, packet_id):
        """当收到补传包时调用此方法进行精细销账"""
        # 1. 从总账本中剔除（表示这个包永久找回了）
        if target_sensor in self.missing_packets_dict and packet_id in self.missing_packets_dict[target_sensor]:
            self.missing_packets_dict[target_sensor].remove(packet_id)
            
        # 2. 从当前等待的批次中剔除
        if packet_id in self.current_patching_batch:
            self.current_patching_batch.remove(packet_id)

        # 3. 如果这 50 个包全收齐了，提前触发下一批次
        if len(self.current_patching_batch) == 0:
            self.signal_batch_patched_done.emit()
    
    