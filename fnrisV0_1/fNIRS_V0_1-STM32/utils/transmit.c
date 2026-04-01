#include "transmit.h"
#include "main.h"
#include "usart.h"
#include "spi.h"
#include <string.h>
#include "utils.h"
#include "BAT_ADC.h"
#include "fnirs.h"
#include "sdio.h"
#include "led.h"
#include <math.h>

/******************************************************************************
 * 外部变量声明
 ******************************************************************************/

extern DMA_HandleTypeDef hdma_spi2_tx;      /**< SPI2发送DMA句柄 */
extern DMA_HandleTypeDef hdma_usart3_rx;   /**< USART3接收DMA句柄 */

/******************************************************************************
 * 全局变量定义
 ******************************************************************************/

uint16_t g_crc16_table[256] = {0};          /**< CRC16快速计算查找表 */

uint8_t g_uart_rx_buffer_raw[RX_BUFFER_SIZE] = {0};  /**< UART原始接收缓冲区 */
UART_RX_BUFFER g_uart_rx_buffer = {0};               /**< UART接收缓冲区管理结构 */

uint8_t g_sensor_id[6] = {0};               /**< 传感器设备ID (MAC地址) */
uint8_t g_response_frame[12] = {0};         /**< 命令响应帧缓冲区 */

volatile uint8_t g_spi_tx_complete = 1;     /**< SPI发送完成标志 */
volatile uint8_t g_uart_tx_complete = 1;    /**< UART发送完成标志 */

/******************************************************************************
 * SPI发送完成回调函数
 ******************************************************************************/

/**
 * @brief SPI发送完成中断回调函数
 * @param hspi SPI句柄指针
 * @note SPI DMA传输完成后自动调用，设置发送完成标志并释放片选
 */
void HAL_SPI_TxCpltCallback(SPI_HandleTypeDef *hspi)
{
    if (hspi->Instance == T_SPI.Instance) {
        g_spi_tx_complete = 1;      /* 设置SPI发送完成标志 */
        SPI_CS_DISABLE();           /* 释放片选信号 */
    }
}

/******************************************************************************
 * UART发送完成回调函数
 ******************************************************************************/

/**
 * @brief UART发送完成中断回调函数
 * @param huart UART句柄指针
 * @note UART DMA传输完成后自动调用，设置发送完成标志
 */
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == T_UART.Instance) {
        g_uart_tx_complete = 1;     /* 设置UART发送完成标志 */
    } 
    
    else if (huart->Instance == DEBUG_UART.Instance) {
        g_debug_buffer.dma_busy = 0;  /* 清除DMA忙标志 */
        
        /* 检查是否还有数据需要发送 */
        uint32_t bytes_available = (g_debug_buffer.write_index - g_debug_buffer.read_index) % DEBUG_BUFFER_SIZE;
        if (bytes_available > 0) {
            /* 继续发送剩余数据 */
            start_debug_dma_transfer();
        } else {
            /* 所有数据发送完成 */
            g_debug_uart_tx_complete = 1;
        }
    }
}

/******************************************************************************
 * UART接收空闲回调函数
 ******************************************************************************/

/**
 * @brief UART接收空闲中断回调函数
 * @param huart UART句柄指针
 * @note 检测到UART接收空闲时自动调用，处理接收完成的数据
 */
void HAL_UART_RxIdleCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == T_UART.Instance) {
        if (__HAL_UART_GET_FLAG(&T_UART, UART_FLAG_IDLE)) {
            /* 清除空闲中断标志位 */
            __HAL_UART_CLEAR_IDLEFLAG(&T_UART);
            
            /* 停止DMA接收 */
            HAL_UART_DMAStop(&T_UART);
            
            /* 计算接收到的数据长度 */
            g_uart_rx_buffer.write_index = RX_BUFFER_SIZE - 
                                          __HAL_DMA_GET_COUNTER(&hdma_usart3_rx);
            
            /* 设置数据就绪标志 */
            g_uart_rx_buffer.data_ready_flag = 1;
            
            /* 复制数据到管理缓冲区 */
            memcpy(g_uart_rx_buffer.buffer, g_uart_rx_buffer_raw, 
                   g_uart_rx_buffer.write_index);
            
            /* 清空原始接收缓冲区 */
            memset(g_uart_rx_buffer_raw, 0, sizeof(g_uart_rx_buffer_raw));
            
            /* 重新启动DMA接收 */
            HAL_UART_Receive_DMA(&T_UART, g_uart_rx_buffer_raw, RX_BUFFER_SIZE);
            
            DebugPrintf("UART received %d bytes\r\n", 
                       g_uart_rx_buffer.write_index);
        }
    }
}

/******************************************************************************
 * SPI通信函数
 ******************************************************************************/

/**
 * @brief 通过SPI DMA方式发送数据
 * @param data 待发送数据指针
 * @param length 数据长度 (字节)
 * @param timeout 超时时间 (毫秒)
 * @return HAL_StatusTypeDef HAL库状态码
 * @note ESP32端接收时可能会覆盖前4个字节，因此额外发送4个空字节
 */
HAL_StatusTypeDef spi_transmit_dma(uint8_t *data, uint32_t length, uint32_t timeout)
{
    HAL_StatusTypeDef result = HAL_ERROR;
    uint32_t retry_count = 0;
    
    /* 带超时和重试机制的SPI发送 */
    while (retry_count < timeout) {
        if (g_spi_tx_complete) {
            g_spi_tx_complete = 0;      /* 清除发送完成标志 */
            SPI_CS_ENABLE();            /* 使能片选信号 */
            
            /* ESP32接收时可能会覆盖前4个字节，因此额外发送4个空字节 */
            result = HAL_SPI_Transmit_DMA(&T_SPI, data, length + 4);
            
            if (result == HAL_OK) {
                DebugPrintf("SPI transmit started: %lu bytes. ", 
                           (unsigned long)length + 4);
                return result;          /* 发送成功启动 */
            }
        }
        
        retry_count++;
        delay_microseconds(100);        /* 短暂延时后重试 */
    }
    
    DebugPrintf("SPI transmit timeout after %lu retries", 
               (unsigned long)retry_count);
    return result;
}

/******************************************************************************
 * UART通信函数
 ******************************************************************************/

/**
 * @brief 通过UART DMA方式发送数据
 * @param data 待发送数据指针
 * @param length 数据长度 (字节)
 * @param timeout 超时时间 (毫秒)
 * @return HAL_StatusTypeDef HAL库状态码
 */
HAL_StatusTypeDef uart_transmit_dma(uint8_t *data, uint32_t length, uint32_t timeout)
{
    HAL_StatusTypeDef result = HAL_ERROR;
    uint32_t retry_count = 0;
    
    /* 带超时和重试机制的UART发送 */
    while (retry_count < timeout) {
        if (g_uart_tx_complete) {
            g_uart_tx_complete = 0;     /* 清除发送完成标志 */
            
            result = HAL_UART_Transmit_DMA(&T_UART, data, length);
            
            if (result == HAL_OK) {
                DebugPrintf("UART transmit started: %lu bytes\r\n", 
                           (unsigned long)length);
                return result;          /* 发送成功启动 */
            }
        }
        
        retry_count++;
        delay_microseconds(100);        /* 短暂延时后重试 */
    }
    
    DebugPrintf("UART transmit timeout after %lu retries", 
               (unsigned long)retry_count);
    return result;
}

/******************************************************************************
 * CRC校验函数
 ******************************************************************************/

/**
 * @brief 生成CRC16查找表
 * @param polynomial CRC16多项式
 * @note 初始化CRC16快速计算查找表，使用多项式0x1021
 */
void generate_crc16_table(uint16_t polynomial)
{
    uint16_t remainder;
    int i, j;
    
    for (i = 0; i < 256; i++) {
        remainder = i << 8;  /* 将字节移到高位 */
        
        for (j = 0; j < 8; j++) {
            if (remainder & 0x8000) {
                /* 如果最高位为1，进行多项式异或 */
                remainder = (remainder << 1) ^ polynomial;
            } else {
                /* 如果最高位为0，仅左移 */
                remainder = remainder << 1;
            }
        }
        
        g_crc16_table[i] = remainder;  /* 存储到查找表 */
    }
    
    DebugPrintf("CRC16 table generated with polynomial 0x%04X", polynomial);
}

/**
 * @brief 计算CRC16校验码（快速方法）
 * @param data 待校验数据指针
 * @param length 数据长度 (字节)
 * @return 16位CRC校验码
 * @note 使用预先生成的查找表进行快速计算
 */
uint16_t calculate_crc16(uint8_t *data, uint16_t length)
{
    uint16_t crc = 0;
    uint16_t i;
    
    for (i = 0; i < length; i++) {
        uint8_t table_index = (uint8_t)((crc >> 8) ^ data[i]);
        crc = (crc << 8) ^ g_crc16_table[table_index];
    }
    
    return crc;
}

/******************************************************************************
 * 设备ID获取函数
 ******************************************************************************/

/**
 * @brief 获取ESP32的MAC地址作为设备ID
 * @note 等待接收ESP32发送的设备ID数据包
 *       数据帧格式：0xBB 0xBB ID[0] ID[1] ID[2] ID[3] ID[4] ID[5]
 */
void get_sensor_id(void)
{
    const uint32_t MAX_WAIT_TIME = 4000;  /* 最大等待时间4秒 */
    uint32_t wait_count = 0;
    
    DebugPrintf("Waiting for ESP32 device ID...\r\n");
    
    while (wait_count < MAX_WAIT_TIME) {
        if (g_uart_rx_buffer.data_ready_flag) {
            g_uart_rx_buffer.data_ready_flag = 0;  /* 清除数据就绪标志 */
            
            /* 检查接收到的数据是否符合设备ID帧格式 */
            if (g_uart_rx_buffer.write_index == 8 && 
                g_uart_rx_buffer.buffer[0] == 0xBB && 
                g_uart_rx_buffer.buffer[1] == 0xBB) {
                
                /* 提取设备ID */
                memcpy(g_sensor_id, g_uart_rx_buffer.buffer + 2, 6);
                
                /* 反转字节顺序（大小端转换） */
                reverse_array(g_sensor_id, 6);
                
                /* 清空接收缓冲区 */
                memset(g_uart_rx_buffer.buffer, 0, 8);
                g_uart_rx_buffer.write_index = 0;
                
                DebugPrintf("Device ID received: %02X:%02X:%02X:%02X:%02X:%02X\r\n",
                           g_sensor_id[0], g_sensor_id[1], g_sensor_id[2],
                           g_sensor_id[3], g_sensor_id[4], g_sensor_id[5]);
                break;  /* 成功获取设备ID */
            }
        }
        
        wait_count++;
        HAL_Delay(1);  /* 等待1毫秒后重试 */
    }
    
    if (wait_count >= MAX_WAIT_TIME) {
        DebugPrintf("Timeout: Failed to get device ID\r\n");
    }
}

/******************************************************************************
 * 数据帧初始化函数
 ******************************************************************************/

/**
 * @brief 初始化数据帧缓冲区
 * @param buffer 数据帧缓冲区指针
 * @param sensor_type 传感器类型
 * @param command 命令类型
 * @param data_length 数据部分长度 (字节)
 */
void init_data_frame(uint8_t *buffer, SENSOR_TYPE sensor_type, 
                     TRANSMIT_COMMAND command, uint16_t data_length)
{
    /* 设置帧头 (上行帧头) */
    *(uint16_t *)(buffer) = ENDIAN_SWAP_16B(FRAME_HEADER_UPLINK);
    
    /* 设置传感器ID (使用低3字节) */
    memcpy(buffer + 2, g_sensor_id, 3);
    
    /* 设置设备类型 */
    buffer[5] = (uint8_t)sensor_type;
    
    /* 设置命令类型 */
    buffer[FRAME_CMD_POSITION] = (uint8_t)command;
    
    /* 设置数据长度 (大端格式) */
    *(uint16_t *)(buffer + FRAME_LEN_POSITION) = ENDIAN_SWAP_16B(data_length);
    
    DebugPrintf("Data frame initialized: type=%d, cmd=0x%02X, len=%d\r\n",
               sensor_type, command, data_length);
}

/**
 * @brief 初始化数据传输模块
 * @note 配置通信接口、初始化CRC表、启动接收等
 */
void init_data_frame_module(void)
{
    SENSOR_TYPE current_sensor_type = SENSOR_FNIRS;  /* 当前设备类型为fNIRS */
    
    /* 生成CRC16查找表 */
    generate_crc16_table(CRC16_POLYNOMIAL);
    
    /* 使能UART空闲中断 */
    UART_ENABLE_IDLE_IT(T_UART);
    
    /* 启动UART DMA接收 */
    HAL_UART_Receive_DMA(&T_UART, g_uart_rx_buffer_raw, RX_BUFFER_SIZE);
    
    /* 链接SPI DMA通道 */
    __HAL_LINKDMA(&T_SPI, hdmatx, hdma_spi2_tx);
    __HAL_DMA_ENABLE_IT(&hdma_spi2_tx, DMA_IT_TC);
    
    /* 获取设备ID (可选，如果需要从ESP32获取) */
    // get_sensor_id();
    
    /* 初始化响应帧缓冲区 */
    *(uint16_t *)(g_response_frame) = ENDIAN_SWAP_16B(FRAME_HEADER_UPLINK);
    // memcpy(g_response_frame + 2, g_sensor_id + 3, 3);  /* 如果需要使用设备ID */
    g_response_frame[5] = (uint8_t)current_sensor_type;  /* 设备类型 */
    *(uint16_t *)(g_response_frame + FRAME_LEN_POSITION) = ENDIAN_SWAP_16B(1);  /* 固定长度1 */
    
    DebugPrintf("Data frame module initialized successfully\r\n");
}

/******************************************************************************
 * 命令处理函数
 ******************************************************************************/

/**
 * @brief 处理采样率设置命令
 * @param data 命令数据指针
 * @param sensor_type 传感器类型掩码
 * @param data_length 数据长度
 * @return 处理结果：0=失败，1=成功
 */
uint8_t handle_sample_rate_command(uint8_t *data, SENSOR_TYPE sensor_type, uint16_t data_length)
{
    uint8_t result = 0;
    uint8_t sensor_count = 0;
    uint8_t i;
    
    /* 统计传感器数量 */
    for (i = 0; i < 4; i++) {
        if (GET_BIT(sensor_type, i)) {
            sensor_count++;
        }
    }
    
    /* 验证数据长度: 每个传感器需要2字节 (类型 + 采样率) */
    if (sensor_count * 2 != data_length) {
        DebugPrintf("Sample rate command error: Invalid data length\r\n");
        return 0;
    }
    
    /* 处理每个传感器的采样率设置 */
    for (i = 0; i < sensor_count; i++) {
        SENSOR_TYPE current_sensor = (SENSOR_TYPE)data[i * 2];
        uint8_t sample_rate = data[i * 2 + 1];
        
        /* 验证传感器类型 */
        if ((current_sensor <= 8) && (sensor_type & current_sensor)) {
            switch (current_sensor) {
                case SENSOR_EEG:
                    /* EEG采样率设置 */
                    result = 1;
                    break;
                    
                case SENSOR_EMG:
                    /* EMG采样率设置 */
                    result = 1;
                    break;
                    
                case SENSOR_FNIRS:
                    /* fNIRS采样率设置 */
                    result = nirs_set_sample_rate(sample_rate);
                    DebugPrintf("fNIRS sample rate set to: %d\r\n", sample_rate);
                    break;
                    
                case SENSOR_NIRS:
                    /* NIRS采样率设置 */
                    result = 1;
                    break;
                    
                default:
                    DebugPrintf("Unknown sensor type: %d\r\n", current_sensor);
                    break;
            }
        } else {
            DebugPrintf("Invalid sensor type in sample rate command: %d\r\n", current_sensor);
        }
    }
    
    return result;
}

/**
 * @brief 处理通道配置命令
 * @param data 命令数据指针
 * @param sensor_type 传感器类型掩码
 * @param data_length 数据长度
 * @return 处理结果：0=失败，1=成功
 */
uint8_t handle_channel_config_command(uint8_t *data, SENSOR_TYPE sensor_type, uint16_t data_length)
{
    uint8_t result = 0;
    uint8_t sensor_count = 0;
    uint8_t data_offset = 0;
    uint8_t i;
    
    /* 统计传感器数量 */
    for (i = 0; i < 4; i++) {
        if (GET_BIT(sensor_type, i)) {
            sensor_count++;
        }
    }
    
    /* 遍历每个传感器的配置数据 */
    for (i = 0; i < sensor_count; i++) {
        SENSOR_TYPE current_sensor = (SENSOR_TYPE)data[data_offset];
        
        /* 验证传感器类型 */
        if (current_sensor > 8 || !(sensor_type & current_sensor)) {
            DebugPrintf("Config command error: Invalid sensor type %d\r\n", current_sensor);
            return 0;
        }
        
        /* 根据传感器类型处理配置 */
        if (current_sensor == SENSOR_EEG || current_sensor == SENSOR_EMG) {
            /* EEG/EMG配置：类型(1) + 通道数(1) + 通道掩码(ceil(通道数/8)) */
            uint8_t channel_count = data[data_offset + 1];
            uint8_t config_length = 2 + (uint8_t)ceil(channel_count / 8.0);
            data_offset += config_length;
            
        } else if (current_sensor == SENSOR_FNIRS || current_sensor == SENSOR_NIRS) {
            /* fNIRS/NIRS配置：类型(1) + 光源数(1) + 探测器数(1) + 配置数据 */
            uint8_t source_count = data[data_offset + 1];
            uint8_t detector_count = data[data_offset + 2];
            uint8_t bytes_per_source = (uint8_t)ceil(detector_count / 8.0);
            uint8_t config_length = 3 + source_count * bytes_per_source;
            
            /* 调用fNIRS配置函数 */
            result = nirs_config(data + data_offset + 1, bytes_per_source);
            data_offset += config_length;
        }
    }
    
    
    return result;
}

/**
 * @brief 处理数据补充请求
 * @param sensor_type 传感器类型
 * @param package_number 数据包编号
 */
void handle_data_supplement_request(SENSOR_TYPE sensor_type, uint32_t package_number)
{
    switch (sensor_type) {
        case SENSOR_EEG:
            /* EEG数据补充处理 */
            break;
            
        case SENSOR_EMG:
            /* EMG数据补充处理 */
            break;
            
        case SENSOR_FNIRS:
            /* fNIRS数据补充处理：从SD卡读取指定数据包 */
            sd_read_nirs(package_number);
            break;
            
        case SENSOR_NIRS:
            /* NIRS数据补充处理 */
            break;
            
        default:
            DebugPrintf("Unknown sensor type for data supplement: %d\r\n", sensor_type);
            break;
    }
}

/**
 * @brief 编码命令响应并发送
 * @param command 命令类型
 * @param response_data 响应数据
 */
void encode_command_response(TRANSMIT_COMMAND command, uint8_t response_data)
{
    /* 更新响应帧的命令和响应数据 */
    g_response_frame[FRAME_CMD_POSITION] = (uint8_t)command;
    g_response_frame[FRAME_DATA_POSITION] = response_data;
    
    /* 计算CRC校验码 */
    uint16_t crc_value = calculate_crc16(g_response_frame, 10);
    
    /* 添加CRC校验码 (大端格式) */
    *(uint16_t *)(g_response_frame + 10) = ENDIAN_SWAP_16B(crc_value);
    
    /* 发送响应帧 */
    if (uart_transmit_dma(g_response_frame, 12, 100) == HAL_OK) {
        set_led_color('g');  /* 设置绿色LED指示发送成功 */
        DebugPrintf("Command response sent successfully\r\n");
    }
}

/**
 * @brief 解码接收到的命令并执行相应操作
 * @param data 接收到的数据指针
 * @param length 数据长度 (字节)
 */
void decode_received_command(uint8_t *data, int length)
{
    //static uint8_t is_initialized = 0;  /* 初始化状态标志 */
    uint32_t package_number = 0;
    uint8_t response = 0;
    SENSOR_TYPE sub_sensor_type = 0;
    
//    /* 去除开头的0x00数据 */
//    int valid_start_index = 0;
//    while (valid_start_index < length && data[valid_start_index] == 0x00) {
//        valid_start_index++;
//    }
//    
//    /* 如果全部是0x00，直接返回 */
//    if (valid_start_index >= length) {
//        set_led_color('g');
//        return;
//    }
//    
//    /* 如果有效数据在中间，需要调整指针和数据长度 */
//    if (valid_start_index > 0) {
//        data = &data[valid_start_index];
//        length = length - valid_start_index;
//        
//        DebugPrintf("Trimmed %d leading 0x00 bytes, new length: %d\r\n", 
//                   valid_start_index, length);
//    }
    
    /* 检查最小数据长度 */
    if (length < FRAME_FIXED_HEADER_LENGTH) {
        DebugPrintf("Command decode error: Data too short (%d bytes)\r\n", length);
        return;
    }
    
    /* 解析数据帧各字段 */
    uint16_t frame_header = (uint16_t)((data[0] << 8) | data[1]);
    SENSOR_TYPE sensor_type = (SENSOR_TYPE)data[5];
    TRANSMIT_COMMAND command = (TRANSMIT_COMMAND)data[FRAME_CMD_POSITION];
    uint16_t data_length = (uint16_t)((data[FRAME_LEN_POSITION] << 8) | 
                                     data[FRAME_LEN_POSITION + 1]);
    
    /* 验证帧头 */
    if (frame_header != FRAME_HEADER_DOWNLINK) {
        DebugPrintf("Command decode error: Invalid frame header 0x%04X\r\n", frame_header);
        return;
    }
    
    /* 验证设备ID (可选) */
    // if (memcmp(data + 2, g_sensor_id + 3, 3) != 0) {
    //     DebugPrintf("Command decode error: Invalid device ID\r\n");
    //     return;
    // }
    
    /* 计算并验证CRC校验码 */
    uint16_t received_crc = (uint16_t)((data[length - 2] << 8) | data[length - 1]);
    uint16_t calculated_crc = calculate_crc16(data, length - 2);
    
    if (received_crc != calculated_crc) {
        DebugPrintf("Command decode error: CRC mismatch (got:0x%04X, calc:0x%04X)\r\n",
                   received_crc, calculated_crc);
        // return;  /* 根据需求决定是否严格校验 */
    }
    
    /* 首次接收命令时初始化设备ID */
//    if (!is_initialized) {
//        is_initialized = 1;
//        memcpy(g_sensor_id, data + 2, 3);  /* 从命令中获取设备ID */
//        memcpy(g_response_frame + 2, data + 2, 3);  /* 更新响应帧的设备ID */
//        fnirs_struct_init();  /* 初始化fNIRS数据结构 */
//        DebugPrintf("Device initialized with ID from first command\r\n");
//    }
    
    DebugPrintf("Command received: type=%d, cmd=0x%02X, len=%d\r\n",
               sensor_type, command, data_length);
    
    /* 根据命令类型执行相应操作 */
    switch (command) {
        case CMD_CONNECT:
            memcpy(g_sensor_id, data + 2, 3);  /* 从命令中获取设备ID */
            memcpy(g_response_frame + 2, data + 2, 3);  /* 更新响应帧的设备ID */
            fnirs_struct_init();  /* 初始化fNIRS数据结构 */
            DebugPrintf("Device initialized with ID from first command\r\n");
            response = 1;
            break;
        case CMD_START:
            response = 1;
            break;
            
        case CMD_STOP:
            response = nirs_stop();
            get_battery_status();  /* 停止采集时检测电池状态 */
            break;
            
        case CMD_BATTERY_VOLTAGE:
            response = get_battery_percentage();
            break;
            
        case CMD_SAMPLE_RATE:
            response = handle_sample_rate_command(data + FRAME_DATA_POSITION, 
                                                sensor_type, data_length);
            break;
            
        case CMD_CONFIG_CHANNEL:
            response = handle_channel_config_command(data + FRAME_DATA_POSITION, 
                                                   sensor_type, data_length);
            break;
            
        case CMD_SUPPLEMENTARY:
            /* 提取数据包编号并反转字节序 */
            sub_sensor_type = data[FRAME_DATA_POSITION];
            for(uint8_t i = 1; i< data_length; i+=4){
              memcpy((uint8_t *)&package_number, data + FRAME_DATA_POSITION + i, 4);
              reverse_array((uint8_t *)&package_number, 4);
              handle_data_supplement_request(sub_sensor_type, package_number);
            }
            break;
            
        default:
            DebugPrintf("Unknown command: 0x%02X\r\n", command);
            break;
    }
    
    /* 发送命令响应 (补充命令不需要响应) */
    if (command != CMD_SUPPLEMENTARY) {
        encode_command_response(command, response);
    }
    
    if(command == CMD_START){
      nirs_start();
    }
}
