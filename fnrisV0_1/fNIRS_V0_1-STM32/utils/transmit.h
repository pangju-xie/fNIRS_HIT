#ifndef __TRANSMIT_H
#define __TRANSMIT_H

/******************************************************************************
 * @file     transmit.h
 * @brief    数据传输模块头文件
 * @version  V1.0
 * @note     负责SPI和UART通信接口的定义和管理，包括数据帧格式、命令定义和通信控制
 ******************************************************************************/

#include <stdio.h>
#include <stdint.h>
#include "usart.h"
#include "spi.h"

/******************************************************************************
 * 硬件接口定义
 ******************************************************************************/

#define T_SPI                    hspi2      /**< 传输使用的SPI接口句柄 (SPI2) */
#define T_UART                   huart3     /**< 传输使用的UART接口句柄 (UART3) */

/******************************************************************************
 * UART控制宏定义
 ******************************************************************************/

/** @brief 使能UART空闲中断 */
#define UART_ENABLE_IDLE_IT(uart)    __HAL_UART_ENABLE_IT(&(uart), UART_IT_IDLE)

/** @brief 禁用UART空闲中断 */
#define UART_DISABLE_IDLE_IT(uart)   __HAL_UART_DISABLE_IT(&(uart), UART_IT_IDLE)

/******************************************************************************
 * SPI控制宏定义
 ******************************************************************************/

/** @brief 设置SPI片选信号为低电平（使能） */
#define SPI_CS_ENABLE()              HAL_GPIO_WritePin(WIFI_CS_GPIO_Port, WIFI_CS_Pin, GPIO_PIN_RESET)

/** @brief 设置SPI片选信号为高电平（禁用） */
#define SPI_CS_DISABLE()             HAL_GPIO_WritePin(WIFI_CS_GPIO_Port, WIFI_CS_Pin, GPIO_PIN_SET)

/******************************************************************************
 * CRC校验配置
 ******************************************************************************/

#define CRC16_POLYNOMIAL            0x1021   /**< CRC16多项式: 0x1021 (x^16 + x^12 + x^5 + 1) */

/******************************************************************************
 * 数据帧头部定义
 ******************************************************************************/

#define FRAME_HEADER_DOWNLINK       0xABAB   /**< 下行数据帧头部标识 (设备→主机) */
#define FRAME_HEADER_UPLINK         0xBABA   /**< 上行数据帧头部标识 (主机→设备) */

/******************************************************************************
 * 缓冲区大小定义
 ******************************************************************************/

#define TX_BUFFER_SIZE              1024     /**< 发送缓冲区大小 (字节) */
#define RX_BUFFER_SIZE              256      /**< 接收缓冲区大小 (字节) */

/******************************************************************************
 * 数据帧结构定义
 ******************************************************************************/

#define FRAME_CMD_POSITION          6        /**< 命令字段在数据帧中的位置 */
#define FRAME_LEN_POSITION          7        /**< 长度字段在数据帧中的位置 */
#define FRAME_DATA_POSITION         9        /**< 数据字段在数据帧中的位置 */
#define FRAME_FIXED_HEADER_LENGTH   11       /**< 数据帧固定头部长度 (不含实际数据) */

/******************************************************************************
 * 传感器类型枚举
 ******************************************************************************/

/** @brief 传感器类型枚举，支持多种传感器组合模式 */
typedef enum {
    SENSOR_EEG = 1,                 /**< 脑电图传感器 */
    SENSOR_EMG = 2,                 /**< 肌电图传感器 */
    SENSOR_EEG_EMG = 3,             /**< 脑电+肌电传感器 */
    SENSOR_FNIRS = 4,               /**< 功能性近红外光谱传感器 */
    SENSOR_EEG_FNIRS = 5,           /**< 脑电+fNIRS传感器 */
    SENSOR_EEG_FNIRS_EMG = 7,       /**< 脑电+fNIRS+肌电传感器 (组合模式) */
    SENSOR_NIRS = 8,                /**< 近红外光谱传感器 */
} SENSOR_TYPE;

/******************************************************************************
 * 命令类型枚举
 ******************************************************************************/

/** @brief 通信命令枚举，定义设备与主机之间的控制命令 */
typedef enum {
    CMD_CONNECT = 0xB0,             /**< 连接命令 */
    CMD_DISCONNECT = 0xB1,          /**< 断开连接命令 */
    CMD_START = 0xC0,               /**< 开始采集命令 */
    CMD_STOP = 0xC1,                /**< 停止采集命令 */
    CMD_BATTERY_VOLTAGE = 0xC2,     /**< 查询电池电压命令 */
    CMD_SAMPLE_RATE = 0xC3,         /**< 设置采样率命令 */
    
    CMD_CONFIG_CHANNEL = 0xA0,      /**< 配置通道命令 */
    CMD_DATA_TRANSMISSION = 0xA1,   /**< 数据传输命令 */
    CMD_SUPPLEMENTARY = 0xA2,       /**< 补充命令/应答命令 */
} TRANSMIT_COMMAND;

/******************************************************************************
 * 采样率配置结构体
 ******************************************************************************/

/** @brief 采样率配置结构体 */
typedef struct {
    uint8_t sensor_type;            /**< 传感器类型 (SENSOR_TYPE) */
    uint8_t sample_rate;            /**< 采样率值 */
} SAMPLE_RATE_CONFIG;

/******************************************************************************
 * UART接收缓冲区结构体
 ******************************************************************************/

/** @brief UART接收缓冲区管理结构体 */
typedef struct {
    uint8_t buffer[RX_BUFFER_SIZE]; /**< 接收数据缓冲区 */
    int     write_index;            /**< 缓冲区写入位置索引 */
    uint8_t data_ready_flag;        /**< 数据就绪标志: 0=未就绪, 1=就绪 */
} UART_RX_BUFFER;

/******************************************************************************
 * 全局变量声明
 ******************************************************************************/

extern UART_RX_BUFFER g_uart_rx_buffer;  /**< 全局UART接收缓冲区实例 */

/******************************************************************************
 * 通信接口函数声明
 ******************************************************************************/

/**
 * @brief 通过UART DMA方式发送数据
 * @param data 待发送数据指针
 * @param length 数据长度 (字节)
 * @param timeout 超时时间 (毫秒)
 * @return HAL_StatusTypeDef HAL库状态码
 */
HAL_StatusTypeDef uart_transmit_dma(uint8_t *data, uint32_t length, uint32_t timeout);

/**
 * @brief 通过SPI DMA方式发送数据
 * @param data 待发送数据指针
 * @param length 数据长度 (字节)
 * @param timeout 超时时间 (毫秒)
 * @return HAL_StatusTypeDef HAL库状态码
 */
HAL_StatusTypeDef spi_transmit_dma(uint8_t *data, uint32_t length, uint32_t timeout);

/******************************************************************************
 * 设备信息函数声明
 ******************************************************************************/

/**
 * @brief 获取传感器ID信息
 * @note 读取并返回设备的传感器配置和标识信息
 */
void get_sensor_id(void);

/******************************************************************************
 * 数据帧处理函数声明
 ******************************************************************************/

/**
 * @brief 初始化数据帧缓冲区
 * @param buffer 数据帧缓冲区指针
 * @param sensor_type 传感器类型
 * @param command 命令类型
 * @param data_length 数据部分长度 (字节)
 */
void init_data_frame(uint8_t *buffer, SENSOR_TYPE sensor_type, 
                     TRANSMIT_COMMAND command, uint16_t data_length);

/**
 * @brief 切换数据帧中的命令字段
 * @param buffer 数据帧缓冲区指针
 * @param new_command 新的命令值
 */
void change_frame_command(uint8_t *buffer, TRANSMIT_COMMAND new_command);

/**
 * @brief 初始化数据帧模块
 * @note 设置默认的通信参数和初始化相关资源
 */
void init_data_frame_module(void);

/**
 * @brief 解码接收到的命令
 * @param data 接收到的数据指针
 * @param length 数据长度 (字节)
 * @note 解析命令并执行相应的操作
 */
void decode_received_command(uint8_t *data, int length);

/**
 * @brief 编码要发送的命令
 * @param command 命令类型
 * @param parameter 命令参数
 * @note 将命令和参数编码为传输格式
 */
void encode_command_to_send(TRANSMIT_COMMAND command, uint8_t parameter);

/**
 * @brief 编码数据到数据帧
 * @param source_data 源数据指针
 * @param frame_buffer 数据帧缓冲区指针
 * @param data_length 数据长度 (字节)
 * @note 将源数据编码到数据帧的指定位置
 */
void encode_data_to_frame(uint8_t *source_data, uint8_t *frame_buffer, uint8_t data_length);

/******************************************************************************
 * 状态检查函数声明
 ******************************************************************************/

/**
 * @brief 检查接收是否就绪
 * @return 接收状态: 0=未就绪, 1=就绪
 */
int is_receive_ready(void);

/******************************************************************************
 * CRC校验函数声明
 ******************************************************************************/

/**
 * @brief 生成CRC16查找表
 * @param polynomial CRC16多项式
 * @note 初始化CRC16快速计算查找表
 */
void generate_crc16_table(uint16_t polynomial);

/**
 * @brief 计算CRC16校验码
 * @param data 待校验数据指针
 * @param length 数据长度 (字节)
 * @return 16位CRC校验码
 */
uint16_t calculate_crc16(uint8_t *data, uint16_t length);

#endif /* __TRANSMIT_H */