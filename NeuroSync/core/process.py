import time
import logging
from collections import deque
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer
from models.stats import SensorTypes, Commands, Device, PendingCommand
from utils import crc

logger = logging.getLogger(__name__)

class DeviceProcessManager(QThread):
    """
    设备与数据综合处理总线 (Merged Manager)
    职责：
    1. 管理已连接设备列表 (白名单)
    2. 指令组装、CRC校验、打包下发与超时重传
    3. 接收底层 UDP 数据、拆包、鉴权、业务事件分发
    """
    # 业务信号分离
    signal_device_connected = pyqtSignal(list, object, str) # id, type_enum, ip
    signal_device_disconnected = pyqtSignal(list)
    signal_data_packet = pyqtSignal(int, int, list) # type, packet_id, data
    signal_data_patched = pyqtSignal(int, int, list) # type, packet_id, data
    signal_command_ack = pyqtSignal(object, list, bool)   # command_enum, sensor_id
    signal_battery_updated = pyqtSignal(int)
    
    def __init__(self, udp_thread):
        super().__init__()
        self.udp_thread = udp_thread
        self.crc_calculator = crc.Crc(0x1021)
        self.devices = {} 
        
        self.command_queue = deque()  # 正规的待发送队列
        self.active_command = None    # 当前正在死等 ACK 的指令
        
        self.cmd_timer = QTimer()
        self.cmd_timer.setSingleShot(True) # 必须为单次触发
        self.cmd_timer.timeout.connect(self._handle_cmd_timeout)

    # ==========================================
    # 模块一：设备白名单管理
    # ==========================================
    def add_device(self, device_ip: str, sensor_id: list, sensor_type: SensorTypes) -> bool:
        """注册新设备进入白名单 (限制最大1个合法设备)"""
        dev_tuple = tuple(sensor_id)
        
        # 如果系统中已经有连接的设备，且试图注册的不是当前设备，则拒绝
        if len(self.devices) > 0 and dev_tuple not in self.devices:
            logger.warning(f"系统已被占用，拒绝新设备注册: ID={sensor_id}")
            return False
            
        if dev_tuple not in self.devices:
            self.devices[dev_tuple] = Device(
                ip=device_ip, id=sensor_id, type=sensor_type, port=self.udp_thread.remote_port
            )
            return True
        return False

    def clear_devices(self):
        """清空设备与重传队列"""
        self.devices.clear()
        self.command_queue.clear()
        self.active_command = None
        self.cmd_timer.stop()

    # ==========================================
    # 模块二：指令打包、发送与重传机制
    # ==========================================
    def send_command(self, command: Commands, data: list = None, target_device: Device = None): # type: ignore
        """核心打包发包逻辑，并将指令压入队列或直接发送"""
        payload = data if data else []
        header = [0xAB, 0xAB]
        
        # 1. 组装头部基础信息
        if command == Commands.CONNECT:
            # 广播连接请求：ID 必须全 0，请求所有类型
            sensor_id = [0x00, 0x00, 0x00]
            sensor_type = [SensorTypes.NotInit.value] 
            target_ip = self.udp_thread.broadcast_ip
        else:
            if not target_device:
                # 遍历发送给所有白名单内的设备
                for dev in self.devices.values():
                    self.send_command(command, payload, dev)
                return
            sensor_id = target_device.id
            sensor_type = [target_device.type.value]
            target_ip = target_device.ip

        data_len = len(payload)
        len_bytes = [(data_len >> 8) & 0xFF, data_len & 0xFF]
        packet = header + sensor_id + sensor_type + [command.value] + len_bytes + payload
        crc_val = self.crc_calculator.crc16(packet, len(packet))
        packet.extend([crc_val >> 8, crc_val & 0xFF])
        packet_bytes = bytes(packet)
        
        bypass_cmds = [Commands.DISCONNECT, Commands.BATTERY_QUERY, Commands.DATA_PATCHING]
        
        if command in bypass_cmds:
            self.udp_thread.send_raw_data(packet_bytes, target_ip, self.udp_thread.remote_port)
        else:
            task = {
                'command': command,
                'packet_bytes': packet_bytes,
                'target_ip': target_ip,
                'sensor_id': sensor_id,
                'retry_count': 0
            }
            self.command_queue.append(task)
            self._pump_queue() # 尝试驱动队列
            
        return True
        
    def _pump_queue(self):
        """驱动引擎：如果当前空闲，弹出一发子弹射出！"""
        if self.active_command is not None or not self.command_queue:
            return # 前面的指令还在等 ACK，乖乖排队, 或者队列打空了
            
        # 从队列最左侧取出一个任务，设为激活状态
        self.active_command = self.command_queue.popleft()
        
        # 物理发送，并启动 1 秒的超时秒表
        self.udp_thread.send_raw_data(
            self.active_command['packet_bytes'], 
            self.active_command['target_ip'], 
            self.udp_thread.remote_port
        )
        self.cmd_timer.start(1000) 
        logger.info(f"队列发出指令: {self.active_command['command'].name}")

    def _handle_cmd_timeout(self):
        """秒表到期：处理重传或放弃"""
        if not self.active_command: return
        
        if self.active_command['retry_count'] < 3:
            self.active_command['retry_count'] += 1
            logger.warning(f"指令 {self.active_command['command'].name} 未收到ACK，第 {self.active_command['retry_count']} 次重传...")
            
            self.udp_thread.send_raw_data(
                self.active_command['packet_bytes'], 
                self.active_command['target_ip'], 
                self.udp_thread.remote_port
            )
            self.cmd_timer.start(1000) # 重新倒数 1 秒
        else:
            logger.error(f"❌ 硬件失联！指令 {self.active_command['command'].name} 重传 3 次失败。")
            failed_cmd = self.active_command['command']
            sensor_id = self.active_command['sensor_id']
            
            self.active_command = None
            self.command_queue.clear()
            
            self.signal_command_ack.emit(failed_cmd, sensor_id, False)
            
    def acknowledge_command(self, cmd: Commands, sensor_id: list):
        """收到下位机反馈，销账并立刻发射下一发"""
        if self.active_command and self.active_command['command'] == cmd:
            self.cmd_timer.stop()
            self.active_command = None
            self._pump_queue() # 无缝衔接发送队列中的下一个
  

    # ==========================================
    # 模块三：数据解包、校验与业务分发
    # ==========================================
    def process_raw_packet(self, packet: list, host_ip: str):
        """核心解包解析逻辑，接收下位机 0xBA 0xBA 开头的数据帧"""
        try:
            if len(packet) < 11 or packet[0] != 0xBA or packet[1] != 0xBA:
                logger.warning(f"数据包格式错误或过短，丢弃: {packet}")
                return # 包太短或帧头不对

            sensor_id = packet[2:5]
            sensor_type_val = packet[5]
            command = Commands(packet[6])
            data_len = (packet[7] << 8) | packet[8]
            
            if len(packet) < 11 + data_len: 
                logger.warning(f"数据包不完整，数据长度：{len(packet)}, 预期至少 {11 + data_len}，丢弃:")
                return
            
            payload = packet[9 : 9 + data_len]
            crc_recv = (packet[9+data_len] << 8) | packet[10+data_len]
            
            # CRC 校验
            crc_calc = self.crc_calculator.crc16(packet, len(packet) - 2)
            if crc_calc != crc_recv:
                logger.warning(f"数据包 CRC 校验失败 (IP: {host_ip})")
                return
            
            # 校验无误，转入业务分发
            self._dispatch_command(command, sensor_id, sensor_type_val, payload, host_ip)
            
        except Exception as e:
            logger.error(f"解析下位机数据包出错: {e}", exc_info=True)

    def _dispatch_command(self, cmd: Commands, sensor_id: list, sensor_type: int, data: list, ip: str):
        """提取具体数据，严格拦截异常设备 (单设备限制)"""
        dev_id_tuple = tuple(sensor_id)

        # 1. 严格的设备白名单校验墙
        if cmd == Commands.CONNECT:
            # 收到连接请求：如果当前已有设备在线，且不是本设备发来的，直接静默丢弃
            if len(self.devices) > 0 and dev_id_tuple not in self.devices:
                logger.warning(f"已有设备在线，忽略其他设备的连接请求: ID={sensor_id}")
                return
        elif cmd == Commands.DISCONNECT:
            # 在用户点击断开的一瞬间，就已经把设备从 self.devices 里移除了。
            pass
        else:
            # 其他数据/控制指令：必须在白名单内
            if dev_id_tuple not in self.devices:
                logger.warning(f"收到未注册设备的数据，丢弃: ID={sensor_id}")
                return
            
            # 使用按位相与(&)校验模态是否匹配
            registered_type = self.devices[dev_id_tuple].type.value
            if (registered_type & sensor_type) == 0:
                logger.warning(f"SensorType 不匹配，丢弃: 收:{sensor_type}, 存:{registered_type}")
                return

        # 2. 销账逻辑：无论收到什么包，只要能过校验墙，说明连通性正常，执行自动确认
        is_success = False
        if data and len(data) > 0:
            is_success = (data[0] == 1)
        if cmd in [Commands.CONNECT, Commands.DISCONNECT, Commands.DATA_RECEIVE, Commands.DATA_PATCHING]:
            is_success = True 
            
        self.acknowledge_command(cmd, sensor_id)
        self.signal_command_ack.emit(cmd, sensor_id, is_success)
        
        # 3. 业务事件分发
        if cmd == Commands.CONNECT:
            device_ip = f"{data[0]}.{data[1]}.{data[2]}.{data[3]}" if len(data) >= 4 else ip
            logger.info(f"设备连接成功: ID={sensor_id}, Type={SensorTypes(sensor_type).name}, IP={device_ip}")
            self.signal_device_connected.emit(sensor_id, SensorTypes(sensor_type), device_ip)
            
        elif cmd == Commands.DISCONNECT and is_success:
            self.devices.pop(dev_id_tuple, None) # 注销当前设备，释放坑位
            logger.info(f"设备断开连接: ID={sensor_id}")
            self.signal_device_disconnected.emit(sensor_id)
            
        elif cmd == Commands.DATA_RECEIVE and len(data) >= 4:
            packet_id = (data[-4] << 24) | (data[-3] << 16) | (data[-2] << 8) | data[-1]
            logger.debug(f"收到数据包: SensorType={SensorTypes(sensor_type).name}, PacketID={packet_id}, DataLen={len(data)-4}")
            self.signal_data_packet.emit(sensor_type, packet_id, data[:-4])
        
        elif cmd == Commands.DATA_PATCHING and len(data) >= 4:
            packet_id = (data[-4] << 24) | (data[-3] << 16) | (data[-2] << 8) | data[-1]
            logger.info(f"收到补包: SensorType={SensorTypes(sensor_type).name}, PacketID={packet_id}, DataLen={len(data)-4}")
            self.signal_data_patched.emit(sensor_type, packet_id, data[:-4])
                
        elif cmd == Commands.BATTERY_QUERY and data:
            self.signal_battery_updated.emit(data[0])




