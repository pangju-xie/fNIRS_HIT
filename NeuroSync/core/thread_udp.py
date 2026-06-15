# core/thread_udp.py
import socket
import psutil
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtNetwork import QUdpSocket, QHostAddress

logger = logging.getLogger(__name__)

# ==========================================
# 1. 纯后台工作者 (Worker) - 彻底生存在子线程
# ==========================================
class UdpWorker(QObject):
    """
    UDP 底层网络通信工作者类。
    
    职责：
        负责实际的 Socket 创建、绑定、数据读写以及网络信息获取。
        本类的所有实例方法均应在绑定的后台子线程中执行，严禁主线程直接调用。
        
    Attributes:
        signal_data_received (pyqtSignal): 收到数据包时触发，传递 (字节列表, 来源IP)。
        signal_network_error (pyqtSignal): 发生网络异常时触发，传递异常信息。
    """
    signal_data_received = pyqtSignal(list, str)
    signal_network_error = pyqtSignal(str)

    def __init__(self, local_port: int = 1227, remote_port: int = 2227):
        super().__init__()
        self.local_port = local_port
        self.remote_port = remote_port
        self.socket = None
        self.local_ip = "0.0.0.0"
        self.broadcast_ip = "255.255.255.255" # 改为全局广播特征码
        self.all_broadcast_ips = [] #用于保存所有网卡的广播地址

        self._get_network_info()
        
    @pyqtSlot()
    def start_socket(self):
        """初始化并绑定 UDP Socket"""
        try:
            self.socket = QUdpSocket(self) 
            if self.socket.bind(QHostAddress.Any, self.local_port, QUdpSocket.BindFlag.ReuseAddressHint):
                logger.info("UDP 绑定成功，端口：%s", self.local_port)
                self.socket.readyRead.connect(self._handle_ready_read)
            else:
                raise Exception("端口绑定失败，可能被占用。")
        except Exception as e:
            self.signal_network_error.emit(str(e))
            logger.error("UDP 初始化失败：%s", e)

    @pyqtSlot(bytes, str, int)
    def do_send(self, packet: bytes, ip: str, port: int):
        """发送数据 (自动识别全局广播并进行多网卡发送)"""
        if not self.socket: return
        
        # 【核心魔法】：当外界想要发广播包时 (CONNECT 指令)
        if ip == "255.255.255.255":
            # 1. 遍历本机所有网段进行精准广播
            for bip in self.all_broadcast_ips:
                self.socket.writeDatagram(packet, QHostAddress(bip), port)
            
            # 2. 补发一个 255.255.255.255 的物理层强行广播作为双重保险
            self.socket.writeDatagram(packet, QHostAddress.Broadcast, port)
        else:
            # 常规的数据包和指令 (点对点通信)
            self.socket.writeDatagram(packet, QHostAddress(ip), port)

    @pyqtSlot()
    def _handle_ready_read(self):
        """读取底层缓冲区到达的数据包，并发射给解析层。"""
        if not self.socket: return
        while self.socket.hasPendingDatagrams():
            size = self.socket.pendingDatagramSize()
            data, host, port = self.socket.readDatagram(size)
            if data:
                # hex_str = " ".join([f"{x:02X}" for x in data])
                # logger.info(f"🔥 [底层收到数据] 来源:{host.toString()}:{port} | 内容: {hex_str}") # type: ignore
                self.signal_data_received.emit(list(data), host.toString()) # type: ignore

    @pyqtSlot()
    def close_socket(self):
        """安全关闭 Socket 并释放资源。"""
        if self.socket:
            self.socket.close()
            self.socket = None
            logger.info("底层 UDP Socket 已安全关闭。")

    def _get_network_info(self):
        """获取所有可用网卡的广播地址，用于全网段设备发现"""
        self.all_broadcast_ips = []
        try:
            import ipaddress
            for interface, addrs in psutil.net_if_addrs().items():
                # 仅屏蔽最底层的环回口和绝对无用的虚拟接口
                if any(kw in interface.lower() for kw in ['loopback', 'wsl', 'veth']):
                    continue
                    
                for addr in addrs:
                    if addr.family == socket.AF_INET and addr.address != '127.0.0.1':
                        # 优先保留局域网 IP (192.x, 10.x, 172.x)
                        if self.local_ip == "0.0.0.0" or addr.address.startswith(('192.', '10.', '172.')):
                            self.local_ip = addr.address
                        try:
                            # 严谨计算每个网段的真实广播地址
                            network = ipaddress.IPv4Network(f"{addr.address}/{addr.netmask}", strict=False)
                            bcast = str(network.broadcast_address)
                            if bcast not in self.all_broadcast_ips:
                                self.all_broadcast_ips.append(bcast)
                        except Exception:
                            # 兜底计算
                            bcast = '.'.join(addr.address.split('.')[:-1] + ['255'])
                            if bcast not in self.all_broadcast_ips:
                                self.all_broadcast_ips.append(bcast)
            
            logger.info("已开启全网段广播探测，目标广播地址：%s", self.all_broadcast_ips)
            
        except Exception as e:
            logger.error("网络检测逻辑失败：%s", e)
            raise Exception(f"Network detection failed: {e}")
    
    def _calc_broadcast(self, ip: str, netmask: str):
        """计算局域网广播地址 (保留原版逻辑)"""
        try:
            import ipaddress
            network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
            self.broadcast_ip = str(network.broadcast_address)
        except:
            # Simple fallback
            self.broadcast_ip = '.'.join(ip.split('.')[:-1] + ['255'])


# ==========================================
# 2. 主线程代理层 (Proxy / Manager)
# ==========================================
class UdpThread(QObject):
    """
    UDP 网络线程管理器 (面向外部 Controller 的安全接口)。
    
    职责：
        基于 PyQt 的 Worker-Thread 模式，使用 moveToThread() 方法将网络收发操作
        彻底隔离在后台线程中，从而避免 QSocketNotifier 跨线程操作死锁的致命 Bug。
        外部 Controller 调用本类的方法时，实际上是通过信号安全地投递给子线程。
        
    """
    signal_data_received = pyqtSignal(list, str)    #透传子线程收到数据包的信号。
    signal_network_error = pyqtSignal(str)          #透传子线程网络异常的信号。
    
    # 私有跨线程通讯信号 (主线程 -> 子线程)
    _signal_send_request = pyqtSignal(bytes, str, int)
    _signal_start_worker = pyqtSignal()
    _signal_stop_worker = pyqtSignal()

    def __init__(self, local_port: int = 1227, remote_port: int = 2227):
        """初始化线程隔离壳及后台工作者。"""
        super().__init__()
        
        # 1. 创建物理后台线程
        self._thread = QThread()
        
        # 2. 实例化打工仔
        self.worker = UdpWorker(local_port, remote_port)
        
        # 3. 【核心隔离机制】将打工仔“流放”到物理后台线程中
        self.worker.moveToThread(self._thread)

        # 4. 建立跨线程的“信号桥梁”
        self._wire_signals()

    def _wire_signals(self):
        """绑定主线程与子线程之间的跨线程信号槽。"""
        # 主线程指使子线程干活
        self._signal_start_worker.connect(self.worker.start_socket)
        self._signal_stop_worker.connect(self.worker.close_socket)
        self._signal_send_request.connect(self.worker.do_send)

        # 子线程向主线程汇报工作
        self.worker.signal_data_received.connect(self.signal_data_received)
        self.worker.signal_network_error.connect(self.signal_network_error)

    def start(self):
        """
        启动网络服务。
        启动后台物理线程，并通知 Worker 初始化 Socket。
        """
        self._thread.start()
        self._signal_start_worker.emit()

    def send_raw_data(self, packet: bytes, ip: str, port: int) -> bool:
        """
        发送 UDP 数据 (线程安全)。
        该方法将发送任务包装为信号，放入后台线程的事件队列中排队执行。
        
        Args:
            packet (bytes): 封装好并带有 CRC 校验的原始字节流。
            ip (str): 目标 IPv4 地址。
            port (int): 目标端口号。
            
        Returns:
            bool: 始终返回 True (代表任务投递成功)。
        """
        self._signal_send_request.emit(packet, ip, port)
        return True

    def stop(self):
        """
        停止网络服务。
        通知 Worker 安全销毁 Socket，并优雅地关闭后台线程。
        """
        self._signal_stop_worker.emit()
        self._thread.quit()
        self._thread.wait()

    # ==========================================
    # 属性透传 (伪装为原本的 UdpThread)
    # ==========================================
    @property
    def local_ip(self) -> str:
        """str: 本机网卡 IPv4 地址"""
        return self.worker.local_ip
        
    @property
    def broadcast_ip(self) -> str:
        """str: 局域网广播地址"""
        return self.worker.broadcast_ip
        
    @property
    def remote_port(self) -> int:
        """int: 目标端口号"""
        return self.worker.remote_port
        
    @property
    def local_port(self) -> int:
        """int: 本地监听端口号"""
        return self.worker.local_port
