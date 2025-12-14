/******************************************************************************
 * @file     utils.c
 * @brief    通用工具函数库实现文件
 * @version  V1.0
 * @date     2024/8/14
 * @author   刘有为 <458386139@qq.com>
 * @note     STM32项目通用工具函数实现，包括调试输出、CRC计算和延时函数
 ******************************************************************************/

#include "utils.h"
#include "main.h"
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <stdarg.h>
#include "stm32f4xx.h"
#include "stm32f4xx_hal.h"
#include "usart.h"

/******************************************************************************
 * 宏定义
 ******************************************************************************/

//#define DEBUG                              /**< 调试模式宏定义，启用调试输出功能 */

#define CRC8_POLYNOMIAL          0xD5      /**< CRC8多项式：0xD5 (x^8 + x^7 + x^6 + x^4 + x^2 + 1) */
#define CRC8_TABLE_SIZE          256       /**< CRC8查找表大小 */

#define UART_MSG_HEAD            0x2325    /**< UART消息头：0x23('#') 0x25('%') */
#define UART_MSG_TAIL            0x0D0A    /**< UART消息尾：0x0D(CR) 0x0A(LF) */
#define UART_CMD_DBG_REDIR       0xC1      /**< UART调试重定向命令码 */
#define UART_MSG_CRC_TAIL_LEN    3         /**< UART消息CRC和尾部长度 */

#define STM32_DBG_INFO_SIZE      128       /**< 调试信息缓冲区大小 */

DEBUG_RING_BUFFER g_debug_buffer = {0};

/******************************************************************************
 * 静态变量定义
 ******************************************************************************/

static uint8_t s_crc8_table[CRC8_TABLE_SIZE] = {0};  /**< CRC8快速计算查找表 */

/******************************************************************************
 * 全局变量定义
 ******************************************************************************/

volatile uint8_t g_debug_uart_tx_complete = 1;  /**< 调试UART发送完成标志 */

/******************************************************************************
 * 延时和时间函数实现
 ******************************************************************************/

/**
 * @brief 获取当前微秒计数器值
 * @return 当前微秒计数值
 * @note 结合SysTick定时器和系统时钟计算精确的微秒时间
 */
uint32_t get_microseconds(void)
{
    uint32_t us_ticks = HAL_RCC_GetSysClockFreq() / 1000000;  /* 计算每微秒的时钟节拍数 */
    uint32_t ms_counter, cycle_count;
    
    /* 确保读取过程中SysTick中断没有发生 */
    do {
        ms_counter = HAL_GetTick();       /* 获取毫秒计数器 */
        cycle_count = SysTick->VAL;       /* 获取SysTick当前值 */
    } while (ms_counter != HAL_GetTick()); /* 检查是否发生中断 */
    
    /* 计算总微秒数 = 毫秒数×1000 + 剩余微秒数 */
    return (ms_counter * 1000) + (us_ticks * 1000 - cycle_count) / us_ticks;
}

/**
 * @brief 微秒级延时函数（用户自定义实现）
 * @param microseconds 延时时间（微秒）
 * @note 使用get_microseconds()函数实现忙等待延时
 */
void user_delay_us(uint32_t microseconds)
{
    uint32_t start_time = get_microseconds();
    
    while (get_microseconds() - start_time < microseconds) {
        /* 忙等待 */
        __NOP();  /* 可选的空操作，避免编译器优化 */
    }
}

/**
 * @brief 微秒级延时函数（优化版本）
 * @param delay_us 延时时间（微秒）
 * @note 使用SysTick硬件定时器实现精确延时，减少CPU占用
 */
void delay_microseconds(uint32_t delay_us)
{
    uint32_t start_tick = HAL_GetTick();
    uint32_t wait_ticks = (delay_us + 500) / 1000;  // 向上取整到毫秒
    
    if(wait_ticks == 0)
    {
        // 小于1ms的延时使用忙等待
        uint32_t cycles = delay_us * (SystemCoreClock / 1000000 / 5);
        for(volatile uint32_t i = 0; i < cycles; i++);
    }
    else
    {
        // 大于等于1ms的延时使用HAL_Delay
        HAL_Delay(wait_ticks);
        
        // 微调剩余时间
        uint32_t elapsed = HAL_GetTick() - start_tick;
        uint32_t remaining_us = delay_us - (elapsed * 1000);
        
        if(remaining_us > 0)
        {
            uint32_t cycles = remaining_us * (SystemCoreClock / 1000000 / 5);
            for(volatile uint32_t i = 0; i < cycles; i++);
        }
    }
}

/**
 * @brief 微秒级延时函数（为兼容性保留的旧版本）
 * @param delay_us 延时时间（微秒）
 */
void Delay_us(uint32_t delay_us)
{
    delay_microseconds(delay_us);  /* 调用新版本函数 */
}

/******************************************************************************
 * CRC校验函数实现
 ******************************************************************************/

/**
 * @brief 计算8位CRC校验码（慢速方法，逐位计算）
 * @param data 数据数组指针
 * @param length 数据长度（字节数）
 * @return 8位CRC校验码
 * @note 使用多项式0xD5，适合小数据量或初始化时使用
 */
uint8_t calculate_crc8(uint8_t data[], uint8_t length)
{
    uint16_t crc = 0;  /* 使用16位存储中间结果 */
    uint8_t i, j;
    
    for (i = 0; i < length; i++) {
        crc ^= ((uint16_t)data[i] << 8);  /* 将数据字节移到高位 */
        
        for (j = 0; j < 8; j++) {
            if (crc & 0x8000) {
                /* 如果最高位为1，进行多项式异或 */
                crc ^= ((uint16_t)CRC8_POLYNOMIAL << 7);
            }
            crc <<= 1;  /* 左移一位 */
        }
    }
    
    return (uint8_t)((crc >> 8) & 0xFF);  /* 返回高8位作为CRC结果 */
}

/**
 * @brief 生成CRC8查找表（用于快速CRC计算）
 * @param polynomial CRC多项式
 * @note 调用此函数初始化查找表后，才能使用calculate_crc8_fast函数
 */
void generate_crc8_table(uint8_t polynomial)
{
    uint16_t i, j;
    uint8_t current_value;
    
    for (i = 0; i < CRC8_TABLE_SIZE; i++) {
        current_value = (uint8_t)i;
        
        for (j = 0; j < 8; j++) {
            if (current_value & 0x80) {
                /* 最高位为1，进行多项式异或 */
                current_value = (current_value << 1) ^ polynomial;
            } else {
                /* 最高位为0，仅左移 */
                current_value <<= 1;
            }
        }
        
        s_crc8_table[i] = current_value;  /* 存储到查找表 */
    }
}

/**
 * @brief 使用查找表计算8位CRC校验码（快速方法）
 * @param data 数据数组指针
 * @param length 数据长度（字节数）
 * @return 8位CRC校验码
 * @note 需要先调用generate_crc8_table初始化查找表
 */
uint8_t calculate_crc8_fast(uint8_t data[], int length)
{
    uint8_t crc = 0;
    int i;
    
    for (i = 0; i < length; i++) {
        crc = s_crc8_table[crc ^ data[i]];  /* 使用查找表快速计算 */
    }
    
    return crc;
}

/**
 * @brief 反转字节数组（可用于大小端转换）
 * @param data 数据数组指针
 * @param size 数据大小（字节数）
 */
void reverse_array(uint8_t *data, int size)
{
    int start = 0;
    int end = size - 1;
    
    while (start < end) {
        /* 交换起始和结束位置的字节 */
        uint8_t temp = data[start];
        data[start] = data[end];
        data[end] = temp;
        
        start++;
        end--;
    }
}

/**
 * @brief 反转字节数组（可用于大小端转换）
 * @param data 数据数组指针
 * @param size 数据大小（字节数）
 * @note 使用双指针原地交换算法，不占用额外空间
 *       时间复杂度：O(n/2)，空间复杂度：O(1)
 */
void reverseArray(uint8_t *data, int size)
{
    int start = 0;          /* 起始位置索引 */
    int end = size - 1;     /* 结束位置索引 */
    
    /* 使用双指针从两端向中间交换元素 */
    while (start < end) {
        /* 交换起始和结束位置的字节 */
        uint8_t temp = data[start];
        data[start] = data[end];
        data[end] = temp;
        
        /* 移动指针继续处理下一对元素 */
        start++;
        end--;
    }
}


/******************************************************************************
 * 调试输出函数实现
 ******************************************************************************/

/**
 * @brief 启动DMA传输
 */
void start_debug_dma_transfer(void)
{
    uint32_t bytes_available = (g_debug_buffer.write_index - g_debug_buffer.read_index) % DEBUG_BUFFER_SIZE;
    
    if (bytes_available == 0) {
        /* 没有数据需要发送 */
        return;
    }
    
    /* 计算本次传输的数据量（不超过DMA缓冲区大小） */
    uint32_t bytes_to_send = bytes_available;
    if (bytes_to_send > DEBUG_DMA_BUFFER_SIZE) {
        bytes_to_send = DEBUG_DMA_BUFFER_SIZE;
    }
    
    /* 从环形缓冲区复制数据到DMA缓冲区 */
    uint32_t read_idx = g_debug_buffer.read_index;
    
    if (read_idx + bytes_to_send <= DEBUG_BUFFER_SIZE) {
        /* 连续数据 */
        memcpy(g_debug_buffer.dma_buffer, &g_debug_buffer.buffer[read_idx], bytes_to_send);
        g_debug_buffer.read_index = (read_idx + bytes_to_send) % DEBUG_BUFFER_SIZE;
    } else {
        /* 分两段复制 */
        uint32_t first_part = DEBUG_BUFFER_SIZE - read_idx;
        memcpy(g_debug_buffer.dma_buffer, &g_debug_buffer.buffer[read_idx], first_part);
        memcpy(&g_debug_buffer.dma_buffer[first_part], g_debug_buffer.buffer, bytes_to_send - first_part);
        g_debug_buffer.read_index = bytes_to_send - first_part;
    }
    
    /* 设置DMA忙标志 */
    g_debug_buffer.dma_busy = 1;
    
    /* 启动DMA传输 */
    if (HAL_UART_Transmit_DMA(&DEBUG_UART, g_debug_buffer.dma_buffer, bytes_to_send) != HAL_OK) {
        g_debug_buffer.dma_busy = 0;  /* 传输失败，重置标志 */
    }
}

/**
 * @brief 格式化打印函数，重定向到调试UART
 * @param format 格式化字符串
 * @param ... 可变参数列表
 * @note 仅在DEBUG宏定义时启用调试输出
 */
void DebugPrintf(const char *format, ...)
{
#ifdef DEBUG
    va_list args;
    char temp_buffer[256];  /* 临时格式化缓冲区 */
    int formatted_length;
    uint32_t bytes_to_write;
    uint32_t available_space;
    uint32_t write_idx;
    
    /* 格式化字符串 */
    va_start(args, format);
    formatted_length = vsnprintf(temp_buffer, sizeof(temp_buffer), format, args);
    va_end(args);
    
    if (formatted_length <= 0) {
        return;
    }
    
    /* 计算实际需要写入的字节数（不包括结束符） */
    bytes_to_write = (uint32_t)formatted_length;
    if (bytes_to_write > sizeof(temp_buffer) - 1) {
        bytes_to_write = sizeof(temp_buffer) - 1;
    }
    
    /* 检查环形缓冲区是否有足够空间 */
    uint32_t bytes_in_buffer = (g_debug_buffer.write_index - g_debug_buffer.read_index) % DEBUG_BUFFER_SIZE;
    available_space = DEBUG_BUFFER_SIZE - bytes_in_buffer - 1;  /* 保留一个字节避免满空判断歧义 */
    
    if (bytes_to_write > available_space) {
        /* 缓冲区空间不足，丢弃部分数据或整个消息 */
        // 可以选择丢弃最旧的数据或当前消息
        if (bytes_to_write < DEBUG_BUFFER_SIZE / 2) {
            /* 丢弃最旧的若干字节数据 */
            g_debug_buffer.read_index = (g_debug_buffer.read_index + bytes_to_write) % DEBUG_BUFFER_SIZE;
        } else {
            /* 当前消息太长，直接丢弃 */
            return;
        }
    }
    
    /* 写入环形缓冲区 */
    write_idx = g_debug_buffer.write_index;
    
    if (write_idx + bytes_to_write <= DEBUG_BUFFER_SIZE) {
        /* 连续空间足够 */
        memcpy(&g_debug_buffer.buffer[write_idx], temp_buffer, bytes_to_write);
        g_debug_buffer.write_index = (write_idx + bytes_to_write) % DEBUG_BUFFER_SIZE;
    } else {
        /* 需要分两段写入（环形缓冲区末尾到开头） */
        uint32_t first_part = DEBUG_BUFFER_SIZE - write_idx;
        memcpy(&g_debug_buffer.buffer[write_idx], temp_buffer, first_part);
        memcpy(g_debug_buffer.buffer, &temp_buffer[first_part], bytes_to_write - first_part);
        g_debug_buffer.write_index = bytes_to_write - first_part;
    }
    
    /* 如果DMA空闲，启动传输 */
    if (!g_debug_buffer.dma_busy) {
        start_debug_dma_transfer();
    }
#endif /* DEBUG */
}

/**
 * @brief 重定向标准输出到调试UART
 * @param ch 要输出的字符
 * @param f 文件指针（未使用）
 * @return 输出的字符
 * @note 用于重定向printf输出到UART
 */
int fputc(int ch, FILE *f)
{
    (void)f;  /* 未使用参数 */
    
    /* 使用阻塞方式发送单个字符 */
    HAL_UART_Transmit(&DEBUG_UART, (uint8_t *)&ch, 1, 0xFFFF);
    
    return ch;
}

/**
 * @brief 重定向打印信息到ESP32串口
 * @param level 调试打印等级
 * @param format 格式化字符串
 * @param ... 可变参数列表
 * @note 格式化的消息通过特定协议发送到ESP32
 */
void print_redirect_to_esp32(DEBUG_LEVEL level, const char *format, ...)
{
#ifdef DEBUG
    uint8_t message_buffer[STM32_DBG_INFO_SIZE + 10] = {0};  /* 消息缓冲区 */
    uint16_t message_length = 0;
    uint8_t crc_value = 0;
    va_list args;
    
    /* 构建消息头 */
    message_buffer[0] = 0x23;  /* '#' */
    message_buffer[1] = 0x25;  /* '%' */
    message_buffer[2] = UART_CMD_DBG_REDIR;  /* 命令码 */
    
    /* 格式化消息内容 */
    va_start(args, format);
    message_length = vsnprintf((char *)&message_buffer[5], 
                              STM32_DBG_INFO_SIZE, format, args);
    va_end(args);
    
    if (message_length <= 0) {
        return;  /* 格式化失败 */
    }
    
    /* 设置消息长度和等级 */
    message_buffer[3] = (uint8_t)(message_length + 3);  /* 长度字段 */
    message_buffer[4] = (uint8_t)level;  /* 调试等级 */
    
    /* 计算CRC校验码 */
    crc_value = calculate_crc8_fast(&message_buffer[2], message_length + 3);
    
    /* 添加CRC和消息尾 */
    message_buffer[5 + message_length] = crc_value;  /* CRC */
    message_buffer[5 + message_length + 1] = 0x0D;   /* CR */
    message_buffer[5 + message_length + 2] = 0x0A;   /* LF */
    
    /* 发送完整消息 */
    uint16_t total_length = message_length + 8;  /* 总消息长度 */
    
    if (HAL_UART_Transmit(&DEBUG_UART, message_buffer, total_length, 100) != HAL_OK) {
        DebugPrintf("Failed to send debug message to ESP32\r\n");
    }
#endif /* DEBUG */
}

