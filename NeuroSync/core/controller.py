# core/controller.py
from PyQt5.QtCore import QObject, QTimer
from PyQt5.QtWidgets import QMessageBox
import os, datetime
import logging

# 引入状态模型与硬件配置模型
from utils.stats import SystemState, SensorTypes, Commands, WorkflowStates
from core.thread_udp import UdpThread
from core.process import DeviceProcessManager
from core.buffer import DataBufferManager

# 引入 UI 组件管家
from core.widget_manager.user import UserInfoManager
from core.widget_manager.channel import ChannelManager
from core.widget_manager.quality import QualityManager 
from core.widget_manager.display import DisplayManager

from utils.paths import DATA_DIR # 引入全局波形数据存储路径

logger = logging.getLogger(__name__)

# ==========================================
# 总司令：主控制器 (宏观业务控制与状态机流转)
# ==========================================
class AppController(QObject):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.system_state = SystemState() 
        
        self.current_patient = None
        
        # 1. 实例化底层基建
        self.udp_thread = UdpThread()
        self.process_manager = DeviceProcessManager(self.udp_thread)
        self.buffer_manager = DataBufferManager(self.system_state)
        
        # 2. 电量查询业务
        self.batTimer = QTimer()
        self.batTimer.setInterval(60000) # 1min查一次
        
        # 3. 子组件容器 (延迟按需加载)
        self.user_widget = None
        self.config_widget = None
        self.qualify_widget = None
        self.display_widget = None
        
        # 业务状态辅助变量
        self.timer_conn_timeout = QTimer()
        self.timer_conn_timeout.setSingleShot(True)
        self.timer_conn_timeout.timeout.connect(self._on_connection_timeout)
        self.is_patching_phase = False 
        self.last_round_missing_count = -1
        
        self.patch_timer = QTimer()
        self.patch_timer.setSingleShot(True)
        self.patch_timer.timeout.connect(self._on_patch_timeout)
        
        self.current_view_mode = "Heamo" 
        self.is_recording = False
        
        self._wire_signals()
        
        self.udp_thread.start()
        
        # 启动时加载基础组件，并执行初始的 UI 锁定
        # self._init_base_components()

    # ==========================================
    # 模块一：信号路由大串联
    # ==========================================
    def _wire_signals(self):
        """将底层信号与宏观业务逻辑进行绑定"""
        # UI 层操作
        self.ui.signal_connect_clicked.connect(self._handle_connection_toggle)
        self.ui.signal_close_requested.connect(self.shutdown_system)
        
        # 数据解析与网络层
        self.udp_thread.signal_data_received.connect(self.process_manager.process_raw_packet)
        self.process_manager.signal_device_connected.connect(self._handle_device_connected)
        self.process_manager.signal_device_disconnected.connect(self._handle_device_disconnected)
        self.process_manager.signal_command_ack.connect(self._handle_command_ack)
        self.process_manager.signal_battery_updated.connect(self.ui.update_battery_display)
        
        self.batTimer.timeout.connect(self._on_bat_timerout)
        
        # 缓存与补包层
        self.process_manager.signal_data_packet.connect(self.buffer_manager.handle_normal_data)
        self.process_manager.signal_data_patched.connect(self.buffer_manager.handle_patched_data)
        self.buffer_manager.signal_batch_patched_done.connect(self._process_next_patch_batch)
        
    
    # ==========================================
    # 模块二：连接与基础通信指令处理
    # ==========================================
    def _handle_connection_toggle(self, is_connect: bool):
        if is_connect:
            ip_parts = [int(x) for x in self.udp_thread.local_ip.split('.')]
            self.ui.btn_connect.set_action_state("Connecting...")
            self.ui.show_status("正在连接设备...", "#f39c12")
            self.process_manager.send_command(Commands.CONNECT, ip_parts) 
            self.timer_conn_timeout.start(5000) 
        else:
            reply = QMessageBox.warning(
                self.ui, # 传入主窗口作为父对象
                "断开连接确认",
                "确定要断开与下位机的连接吗？\n断开后当前工作区将被清空，未保存的记录可能会丢失。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No # 默认焦点放在 No 上，防止误触
            )
            
            if reply == QMessageBox.Yes:
                logger.info("用户确认断开，正在发送 DISCONNECT 指令...")
                self.ui.btn_connect.set_action_state("Disconnecting...")
                self.process_manager.send_command(Commands.DISCONNECT)
                self._handle_device_disconnected()

            else:
                logger.info("用户取消了断开操作。")
                return # 直接返回，什么都不做
            
            
    def _handle_device_connected(self, sensor_id: list, sensor_type: SensorTypes, device_ip: str):
        self.timer_conn_timeout.stop()
        self.current_sensor_type = sensor_type
        
        if self.process_manager.add_device(device_ip, sensor_id, sensor_type):
            logger.info(f"设备已接入: {sensor_id} @ {device_ip}")

        self.ui.set_connected_state(str(sensor_type.name))
        
        self.system_state.advance_workflow(WorkflowStates.CONNECTED)
        self.process_manager.send_command(Commands.BATTERY_QUERY)
        self.batTimer.start()
        self.buffer_manager.init_processors(sensor_type)
    
        # 设备连上后，动态加载配置页，并触发锁检查
        self._init_base_components()
        self._init_config_component(sensor_type)
        self._update_tab_locks()

    def _handle_device_disconnected(self):
        self.batTimer.stop()
        self.timer_conn_timeout.stop()
        self.process_manager.clear_devices()
        
        self.system_state.advance_workflow(WorkflowStates.DISCONNECTED)
        self.ui.set_disconnected_state()
        
        self._teardown_dynamic_components() # 卸载所有动态组件，回到初始状态
        self._update_tab_locks()
        
        self.ui.show_status("设备已断开连接。", "#e74c3c")

    def _on_connection_timeout(self):
        self.ui.set_disconnected_state()
        self.ui.show_error("连接失败", "未找到设备。")
        self.ui.show_status("连接超时，未找到设备。", "#e74c3c")

    def shutdown_system(self):
        logger.info("正在关闭系统...")
        self.batTimer.stop()
        if self.system_state.workflow > WorkflowStates.DISCONNECTED:
            self.process_manager.send_command(Commands.DISCONNECT)
        
        self.udp_thread.stop()
        self.process_manager.quit()

    # ==========================================
    # 模块三：补包引擎与指令 ACK 回调
    # ==========================================
    def _handle_command_ack(self, cmd: Commands, sensor_id: list, is_success: bool):
        self.process_manager.acknowledge_command(cmd, sensor_id)

        if cmd == Commands.STOP_SAMPLE and is_success:
            logger.info("下位机已确认停止采集。")
            
            if self.system_state.workflow <= WorkflowStates.QUALIFIED:
                logger.info("阻抗检测完成。")
                self.ui.show_status("阻抗检测完成。", "#4CAF50")
                return
                
            elif self.system_state.workflow >= WorkflowStates.ACQUIRED:
                if self.buffer_manager.op_mode >=3:
                    total_missing = self.buffer_manager.get_total_missing_count()
                    if total_missing > 0:
                        self.is_patching_phase = True
                        self.ui.show_status(f"准备补包，共计丢失 {total_missing} 包...", "#e67e22")
                        self._process_next_patch_batch() 
                    else:
                        logger.info("已停止记录，无丢包！")
                        self._finalize_and_save_data()
                else:
                    logger.info("已停止采集")
                    self.ui.show_status("已停止采集信号", "#7f8c8d")
                    self.system_state.advance_workflow(WorkflowStates.ACQUIRED)
                
        elif cmd == Commands.CHANNEL_CONFIG:
            if is_success:
                logger.info("通道配置成功！")
                self.ui.show_status("通道配置成功！", "#4CAF50")
            else:
                self.ui.show_error("配置失败", "下位机拒绝了通道配置")

        elif cmd == Commands.SAMPLE_RATE:
            if is_success:
                logger.info("采样率配置成功！")
                
                self._finalize_configuration()
                self.config_widget.btn_finish.setEnabled(True) # type: ignore # 只有采样率配置成功后，才允许用户点击完成按钮
            else:
                self.ui.show_error("配置失败", "下位机拒绝了采样率配置")
                
    def _finalize_configuration(self):
        """参数全部下发完毕后，提取字典更新给 Processor 并跳转"""
        # 1. 提取当前界面的拓扑参数和采样率
        if SensorTypes.FNIRS in self.buffer_manager.processors:
            fnirs_montage = self.config_widget.brain_manager.get_fnirs_montage_dict() # type: ignore
            fnirs_spr = int(self.config_widget.combo_fnirs_hz.currentText()) # type: ignore
            self.buffer_manager.processors[SensorTypes.FNIRS].set_config(fnirs_montage)
            self.buffer_manager.processors[SensorTypes.FNIRS].set_sample_rate(fnirs_spr)
            
        if SensorTypes.EEG in self.buffer_manager.processors:
            eeg_montage = self.config_widget.brain_manager.get_eeg_montage_dict() # type: ignore
            eeg_spr = int(self.config_widget.combo_eeg_hz.currentText()) # type: ignore
            self.buffer_manager.processors[SensorTypes.EEG].set_config(eeg_montage)
            self.buffer_manager.processors[SensorTypes.EEG].set_sample_rate(eeg_spr)
        
        self.ui.show_status("通道配置完成。准备进入测试阶段。", "#4CAF50")     
        
        self._init_quality_component() # 进入测试阶段时才加载质量评估组件，节省资源

    def _process_next_patch_batch(self):
        self.patch_timer.stop() # 进门先停表
        
        # 尝试获取本轮的下一批任务
        s_type, batch_ids = self.buffer_manager.pop_next_patch_batch()
        
        if s_type is not None and len(batch_ids) > 0:
            # 队列里还有任务，继续发送本轮的补包指令
            logger.info(f"请求 [{SensorTypes(s_type).name}] 的 {len(batch_ids)} 个补包数据...")
            patch_payload = [s_type]
            for m_id in batch_ids:
                patch_payload.extend([(m_id >> 24) & 0xFF, (m_id >> 16) & 0xFF, (m_id >> 8) & 0xFF, m_id & 0xFF])
                
            self.process_manager.send_command(Commands.DATA_PATCHING, data=patch_payload)
            self.patch_timer.start(1500) # 1.5 秒超时控制
            
        elif self.is_patching_phase:
            # === 本轮所有批次均已发送完毕，进行复盘评估 ===
            current_missing = self.buffer_manager.get_total_missing_count()
            
            if current_missing == 0:
                # 完美收官
                logger.info("所有丢失数据已全部补齐！")
                self.ui.show_status("补包完美完成，准备保存数据。", "#4CAF50")
                self.is_patching_phase = False
                self._finalize_and_save_data()
                
            elif current_missing == self.last_round_missing_count:
                # 毫无进展：一整轮问询下来，一个包都没补上。说明硬件已经丢弃了这些数据或彻底断流。
                logger.warning(f"本轮无新的补包！放弃剩余的 {current_missing} 个包，强制结束。")
                self.ui.show_status(f"补包不全。", "#e74c3c")
                self.is_patching_phase = False
                self._finalize_and_save_data()
                
            else:
                # 仍有丢包，但有进展：说明刚才那一轮确实捞回来了一些数据，值得再来一轮！
                logger.info(f"本轮补包结束，成功找回部分数据。仍剩余 {current_missing} 个包，开启下一轮轮询...")
                self.ui.show_status(f"补包进行中---", "#f39c12")
                
                # 更新参考值，重新装填队列，启动下一轮第一批
                self.last_round_missing_count = current_missing
                self.buffer_manager.prepare_patching_round()
                self._process_next_patch_batch()

    def _finalize_and_save_data(self):
        self.ui.show_status("正在保存文件...", "#f39c12")
        self.buffer_manager.stop_recording() 

        patient_info = self.current_patient.to_dict() if self.current_patient else {}
        # 触发生成 .snirf 和 .csv
        for s_type, processor in self.buffer_manager.processors.items():
            file_name = self.file_basename
            if hasattr(processor, 'export_snirf'):
                processor.export_snirf(self.current_session_dir, file_name, self.record_start_time, patient_info)

        self.ui.show_status(f"✅ 数据已成功存入: {os.path.basename(self.current_session_dir)}", "#4CAF50")
        
        if self.display_widget and hasattr(self.display_widget, 'ui'):
            self.display_widget.ui.btnStart.setEnabled(True)
            self.display_widget.ui.btnComplete.setEnabled(True)
        
        self.system_state.advance_workflow(WorkflowStates.ANALYZED)
        self._update_tab_locks()
        
        
    def _on_patch_timeout(self):
        """补包超时处理，放弃当前批次的等待，立刻请求本轮的下一批"""
        logger.warning("补包硬件响应超时，直接跳过，请求下一批...")
        self.buffer_manager.current_patching_batch.clear()
        self._process_next_patch_batch()
    
    def _on_bat_timerout(self):
        self.process_manager.send_command(Commands.BATTERY_QUERY)

    # ==========================================
    # 模块四：UI 组件初始化与动态加载
    # ==========================================
    def _init_base_components(self):
        """加载第一页 (患者信息)，并锁定后续所有页面"""
        if self.user_widget is not None:
            logger.info("用户组件已存在，跳过重复加载。")
            return
        
        self.user_widget = UserInfoManager()
        self.user_widget.onUserSet.connect(self._handle_user_set)
        self.ui.embed_widget_to_tab("home", self.user_widget)
        logger.info("用户界面加载完毕！")
        
        # 启动时强制锁定除 Home 页外的所有子窗口
        self._update_tab_locks()
            

    def _init_config_component(self, sensor_types: SensorTypes):
        """
        当设备成功连接后，动态加载并嵌入通道配置组件 (第二页)
        """
        if not self.config_widget:
            logger.info(f"正在加载通道配置界面，设备类型: {sensor_types.name}")
            
            # 1. 实例化通道配置
            self.config_widget = ChannelManager(sensor_types=sensor_types)
            
            # 2. 绑定 ChannelManager 发出的下发指令与完成信号
            self.config_widget.OnConfigSet.connect(self._handle_send_hardware_config)
            self.config_widget.OnConfigFinished.connect(self._handle_configuration_finished)
            self.config_widget.signal_status_msg.connect(self.ui.show_status)
            
            # 3. 嵌入 UI
            self.ui.embed_widget_to_tab("config", self.config_widget)
            logger.info("配置界面加载完毕！")
            
    def _init_quality_component(self):
        """当进入质量测试阶段时，动态实例化并加载第三页"""
        if not self.qualify_widget:
            logger.info("正在加载信号测试界面...")
            
            # 【核心修改】：接口非常干净，只传模态和脑电管家
            self.qualify_widget = QualityManager(
                sensor_types=self.current_sensor_type, 
                bmap_manager=self.config_widget.brain_manager # type: ignore
            )
            
            # 绑定启停测试与完成的信号槽
            self.qualify_widget.signal_request_start.connect(self._on_quality_start)
            self.qualify_widget.signal_request_stop.connect(self._on_quality_stop)
            self.qualify_widget.signal_qualify_finished.connect(self._handle_quality_finished)
            
            self.buffer_manager.signal_quality_updated.connect(self.qualify_widget.update_quality_data)
            
            # 嵌入第 3 个 Tab (假设标识符是 "qualify" 或根据你实际的 tab 名字)
            self.ui.embed_widget_to_tab("qualify", self.qualify_widget)
            logger.info("测试界面加载完毕！")
        
    def _init_display_component(self):
        """当阻抗测试完成时，动态实例化并加载第四页 (波形图)"""
        if not hasattr(self, 'display_widget') or not self.display_widget:
            logger.info("正在加载绘制界面...")
            
            # 1. 直接从底层的 Processor 实例中提取通道信息与采样率 (解耦 UI)
            fnirs_chs, eeg_chs = [], []
            fs_fnirs, fs_eeg = 10, 500
            
            if SensorTypes.FNIRS in self.buffer_manager.processors:
                f_processor = self.buffer_manager.processors[SensorTypes.FNIRS]
                fnirs_chs = f_processor.get_channels() if hasattr(f_processor, 'get_channels') else getattr(f_processor, 'channels', [])
                fs_fnirs = f_processor.get_sample_rate() if hasattr(f_processor, 'get_sample_rate') else getattr(f_processor, 'sample_rate', 10)
                
            if SensorTypes.EEG in self.buffer_manager.processors:
                e_processor = self.buffer_manager.processors[SensorTypes.EEG]
                # EEG 同理，做向下兼容处理
                if hasattr(e_processor, 'get_channels'):
                    eeg_chs = e_processor.get_channels()
                elif hasattr(e_processor, 'config'):
                    eeg_chs = e_processor.config.get('eeg_channels', [])
                else:
                    eeg_chs = getattr(e_processor, 'channels', [])
                    
                fs_eeg = e_processor.get_sample_rate() if hasattr(e_processor, 'get_sample_rate') else getattr(e_processor, 'sample_rate', 500)

            # 2. 实例化并注入真实的参数
            self.display_widget = DisplayManager(
                fnirs_channels=fnirs_chs, eeg_channels=eeg_chs, 
                fs_fnirs=fs_fnirs, fs_eeg=fs_eeg
            )

            # 3. 绑定 UI 操作指令 (启停、记录)
            self.display_widget.signal_request_start.connect(self._on_display_start)
            self.display_widget.signal_request_stop.connect(self._on_display_stop)
            self.display_widget.signal_request_record.connect(self._on_display_record)
            self.display_widget.signal_op_mode_changed.connect(self._handle_op_mode_change)
            self.display_widget.signal_mark_event.connect(self._handle_mark_event)
            
            # 4. 将 Buffer 吐出的高频数据流，精准路由到波形图画板上！
            if hasattr(self.buffer_manager, 'signal_raw_stream'):
                self.buffer_manager.signal_raw_stream.connect(self._route_raw_data_to_display)
            self.display_widget.signal_display_finished.connect(self._handle_display_finished)
            
            if hasattr(self.display_widget.ui, 'comboSigType_fnirs'):
                init_mode = self.display_widget.ui.comboSigType_fnirs.currentText() # type: ignore
                self._handle_op_mode_change(init_mode)
            
            # 5. 嵌入第 4 个 Tab (假设标识符是 "display" 或根据你实际 tab 名字调整)
            self.ui.embed_widget_to_tab("display", self.display_widget)
            logger.info("绘制界面加载完毕！")
    
    
    # ==========================================
    # 模块五：工作流与权限锁控制中心 (Workflow)
    # ==========================================
    def _update_tab_locks(self):
        """
        集中处理所有 Tab 的解锁与锁定逻辑 (业务规则中心)
        彻底修复“子窗口可随意乱点”的 Bug
        """
        if not hasattr(self.ui, 'tab_widget'): return
        
        # 状态提取
        has_patient = self.current_patient is not None
        is_connected = self.system_state.workflow >= WorkflowStates.CONNECTED
        is_configured = self.system_state.workflow >= WorkflowStates.CONFIGURED
        is_qualified = self.system_state.workflow >= WorkflowStates.QUALIFIED
        is_acquired = self.system_state.workflow >= WorkflowStates.ACQUIRED

        # 规则1：解锁【通道配置页】 (需：录入病人信息 + 设备已连接)
        can_config = has_patient and is_connected
        self.ui.tab_widget.setTabEnabled(1, can_config)
        
        # 规则2：解锁【阻抗测试页】 (需：配置已下发并完成)
        self.ui.tab_widget.setTabEnabled(2, is_configured)
        
        # 规则3：解锁【实时采集页】 (需：通过阻抗测试)
        self.ui.tab_widget.setTabEnabled(3, is_qualified)
        
        # 规则4：正式采集状态的特殊提示 (需：进入正式采集阶段)
        self.ui.tab_widget.setTabEnabled(4, is_acquired) # 只有测试通过了，才允许进入正式采集页
        
        # 动态更新主界面提示状态
        if not has_patient:
            # self.ui.show_status("请先在首页录入受试者信息。")
            pass
        elif not is_connected:
            self.ui.show_status("请点击右上角连接设备。")
        elif can_config and not is_configured:
            self.ui.show_status("请先完成通道配置和参数配置。", "#4caf50")

    def _handle_user_set(self, patient_data):
        """处理第一页传来的受试者锁定信号"""
        # 【修改】：直接存在 Controller 自己的属性里
        self.current_patient = patient_data
        logger.info(f"受试者已锁定: {patient_data.name} (PID: {patient_data.pid})")
        
        self._update_tab_locks()
        
        if self.ui.tab_widget.isTabEnabled(1):
            self.ui.tab_widget.setCurrentIndex(1)
            self.ui.show_status("进入通道配置阶段。", "#8e44ad")
            
    def _teardown_dynamic_components(self):
        """安全卸载并销毁所有动态加载的业务 UI 组件，防止内存泄漏"""
        logger.info("正在清理业务 UI 组件...")
        
        components_to_clean = [
            ('user_widget', "home"),
            ('config_widget', "config"),
            ('qualify_widget', "qualify"),
            ('display_widget', "display")
        ]
        
        for attr_name, tab_id in components_to_clean:
            widget = getattr(self, attr_name, None)
            if widget:
                # 1. 显式从 Tab 容器中物理移除
                if hasattr(self.ui, 'tab_widget'):
                    idx = self.ui.tab_widget.indexOf(widget)
                    if idx != -1:
                        self.ui.tab_widget.removeTab(idx)
                
                # 2. 掐断 Canvas 定时器防泄漏
                if attr_name == 'display_widget':
                    for canvas_attr in ['fnirs_canvas', 'eeg_canvas', 'semg_canvas']:
                        canvas = getattr(widget, canvas_attr, None)
                        if canvas and hasattr(canvas, 'render_timer'):
                            canvas.render_timer.stop()
                
                # 3. 释放组件
                widget.setParent(None)
                widget.deleteLater()
                setattr(self, attr_name, None)
                
        # 重置系统内部状态
        self.current_patient = None
        logger.info("业务 UI 组件已全部物理卸载，内存已释放。")
        
        
    # ==========================================
    # 模块六：通道配置对接与下发 (New Integration)
    # ==========================================
    def _handle_send_hardware_config(self, sr_order: list, config_order: list):
        """
        核心业务：接收字节流，发送给硬件
        """
        self.ui.show_status("正在进行参数配置...", "#f39c12")
        if config_order:
            self.process_manager.send_command(Commands.CHANNEL_CONFIG, data=config_order)
        if sr_order:
            self.process_manager.send_command(Commands.SAMPLE_RATE, data=sr_order)
            
    def _handle_configuration_finished(self):
        """
        用户点击“完成所有配置”后触发：推进全局状态机，自动跳转至下一页
        """
        logger.info("配置阶段完成。准备进入阻抗测试阶段。")
        self.system_state.advance_workflow(WorkflowStates.CONFIGURED)
        self._update_tab_locks()
        
        if self.ui.tab_widget.isTabEnabled(2):
            self.ui.tab_widget.setCurrentIndex(2)
            self.ui.show_status("进入阻抗测试阶段。", "#8e44ad")
            
    def _handle_quality_finished(self):
        logger.info("阻抗测试完成。准备进入正式数据采集阶段。")
        self.system_state.advance_workflow(WorkflowStates.QUALIFIED)
        self._update_tab_locks()
        
        self._init_display_component()
        
        if self.ui.tab_widget.isTabEnabled(3):
            self.ui.tab_widget.setCurrentIndex(3)
            self.ui.show_status("进入正式采集阶段。", "#4CAF50")
            
    def _route_raw_data_to_display(self, sensor_type: SensorTypes, raw_data: list):
        """高频数据路由路由器：按模态精准投喂给 DisplayManager"""
        if not self.display_widget or not self.display_widget.is_running:
            return
            
        if sensor_type == SensorTypes.FNIRS:
            self.display_widget.push_new_data(fnirs_raw=raw_data, eeg_raw=[])
        elif sensor_type == SensorTypes.EEG:
            self.display_widget.push_new_data(fnirs_raw=[], eeg_raw=raw_data)
            
    def _on_quality_start(self):
        """响应质量测试页的开始测试按钮，直接发开始指令给底层"""
        logger.info("用户请求开始质量测试，正在发送开始采集指令...")
        self.buffer_manager.op_mode = 0 # 进入质量测试模式
    
        if SensorTypes.FNIRS in self.buffer_manager.processors:
            self.buffer_manager.processors[SensorTypes.FNIRS].reset_quality_data()
        if SensorTypes.EEG in self.buffer_manager.processors:
            self.buffer_manager.processors[SensorTypes.EEG].reset_quality_data()
            
        self.ui.show_status("阻抗检测中...", "#f39c12")
        self.process_manager.send_command(Commands.START_SAMPLE)
        
    def _on_quality_stop(self):
        self.process_manager.send_command(Commands.STOP_SAMPLE)
    

    def _on_display_start(self):
        logger.info("开始采集...")
        self.system_state.advance_workflow(WorkflowStates.ACQUIRED)
        self.is_recording = False
        self._update_buffer_op_mode()
        self.process_manager.send_command(Commands.START_SAMPLE)
        self.ui.show_status("采集中... ", "#4CAF50")

    def _on_display_stop(self):
        logger.info("停止采集并进行补包检查...")
        self.is_recording = False
        # 发出停止指令后，下位机会回复 ACK，进而自动触发 _handle_command_ack 里的丢包检测和修补！
        self.process_manager.send_command(Commands.STOP_SAMPLE)

    def _on_display_record(self, is_recording: bool):
        """响应 Display 界面的记录按钮，直接控制底层数据管家的开关"""
        if is_recording:
            self.is_recording = True
            
            patient = self.current_patient
            dir_prefix = patient.get_dir_prefix() if patient else "Unknown"
            file_base = patient.get_file_prefix_base() if patient else "Unknown"
            
            self.record_start_time = datetime.datetime.now()
            time_str = self.record_start_time.strftime("%y%m%d_%H%M%S")
            
            self.file_basename = f"{file_base}_{time_str}"
            
            self.current_session_dir = os.path.join(DATA_DIR, dir_prefix)
            os.makedirs(self.current_session_dir, exist_ok=True)
            
            self.buffer_manager.start_recording(self.current_session_dir, self.file_basename)
            self._update_buffer_op_mode()
            self.ui.show_status(f"🔴 记录中... ", "#e74c3c")
        
    def _handle_op_mode_change(self, mode_str):
        """响应界面的下拉框，切换看原始光强还是血氧"""
        self.current_view_mode = "Raw" if "Raw" in mode_str else "Heamo"
        self._update_buffer_op_mode()
        logger.info(f"显示模式已切换为: {self.current_view_mode}")
        
    def _handle_mark_event(self, key_val):
        """响应界面传来的 0-9 按键，通知底层记录事件时间戳"""
        if self.is_recording and SensorTypes.FNIRS in self.buffer_manager.processors:
            self.buffer_manager.processors[SensorTypes.FNIRS].add_marker(key_val)

    def _update_buffer_op_mode(self):
        """集中管理底层 Buffer 吐数据的模式 (1/3:Raw, 2/4:Heamo)"""
        # 3/4 是落盘并展示，1/2 是只展示不落盘
        if self.is_recording:
            self.buffer_manager.op_mode = 3 if self.current_view_mode == "Raw" else 4
        else:
            self.buffer_manager.op_mode = 1 if self.current_view_mode == "Raw" else 2
            
    def _handle_display_finished(self):
        logger.info("波形监控与记录完成。")
        # 停止一切底层活动
        # self.process_manager.send_command(Commands.STOP_SAMPLE)
        self.system_state.advance_workflow(WorkflowStates.ACQUIRED)
        self._update_tab_locks()
        

    