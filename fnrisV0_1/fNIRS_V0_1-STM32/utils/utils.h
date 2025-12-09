#ifndef __UTILS_H__
#define __UTILS_H__

/******************************************************************************
 * @file     utils.h
 * @brief    通用工具函数库头文件
 * @version  V1.0
 * @date     2024/8/14
 * @author   刘有为 <458386139@qq.com>
 * @note     STM32项目通用工具函数，包括调试输出、位操作、字节序转换和延时函数
 ******************************************************************************/

#include "main.h"
#include <stdio.h>
#include <stdarg.h>

/******************************************************************************
 * 配置常量定义
 ******************************************************************************/

#define DEBUG_UART   huart2      /**< 调试输出使用的UART句柄 */

/******************************************************************************
 * 类型定义
 ******************************************************************************/

/** @brief 简化的类型别名，使代码更简洁 */
typedef uint8_t  u8;     /**< 8位无符号整数 */
typedef uint16_t u16;    /**< 16位无符号整数 */
typedef uint32_t u32;    /**< 32位无符号整数 */

/** @brief 调试消息等级枚举 */
typedef enum {
    DBG_LEVEL_INFO = 0,  /**< 信息级别消息 */
    DBG_LEVEL_ERROR = 1, /**< 错误级别消息 */
    DBG_LEVEL_DEBUG = 2, /**< 调试级别消息（包含函数和行号信息） */
} DEBUG_LEVEL;

/**
 * @brief 调试信息环形缓冲区管理
 */
#define DEBUG_BUFFER_SIZE     1024  /* 增大缓冲区大小 */
#define DEBUG_DMA_BUFFER_SIZE 256   /* DMA传输缓冲区大小 */

typedef struct {
    uint8_t buffer[DEBUG_BUFFER_SIZE];
    volatile uint32_t write_index;
    volatile uint32_t read_index;
    volatile uint8_t dma_busy;
    uint8_t dma_buffer[DEBUG_DMA_BUFFER_SIZE];
} DEBUG_RING_BUFFER;

/******************************************************************************
 * 调试打印宏定义
 ******************************************************************************/

/**
 * @brief 向ESP32打印信息级别消息
 */
#define INFO_PRINT(fmt, ...)     print_redirect_to_esp32(DBG_LEVEL_INFO, fmt, ##__VA_ARGS__)

/**
 * @brief 向ESP32打印调试消息，包含函数名和行号信息
 */
#define DBG_PRINT(fmt, ...)      print_redirect_to_esp32(DBG_LEVEL_DEBUG, "(%s:%d) " fmt, \
                                                         __func__, __LINE__, ##__VA_ARGS__)

/**
 * @brief 向ESP32打印错误消息，包含函数名和行号信息
 */
#define ERR_PRINT(fmt, ...)      print_redirect_to_esp32(DBG_LEVEL_ERROR, "ERROR(%s:%d) " fmt, \
                                                         __func__, __LINE__, ##__VA_ARGS__)

/******************************************************************************
 * 位操作宏定义
 ******************************************************************************/

/** @brief 左移宏（注意：原宏名为R_SHIFT，但实际上执行左移操作） */
#define BIT_SHIFT_LEFT(val, bits)    ((val) << (bits))

/** @brief 从寄存器中获取特定位的值 */
#define GET_BIT(reg, bit)            (((reg) >> (bit)) & 0x01U)

/** @brief 切换寄存器中的特定位（0变1，1变0） */
#define TOGGLE_BIT(reg, bit)         ((reg) ^= (1U << (bit)))

/** @brief 检查寄存器中的特定位是否被设置 */
#define IS_BIT_SET(reg, bit)         (((reg) & (1U << (bit))) != 0)

/** @brief 使用掩码设置多个位 */
#define SET_BITS(reg, mask)          ((reg) |= (mask))

/** @brief 使用掩码清除多个位 */
#define CLEAR_BITS(reg, mask)        ((reg) &= ~(mask))

/** @brief 修改寄存器中的特定位域 */
#define MODIFY_BITS(reg, mask, value) ((reg) = ((reg) & ~(mask)) | ((value) & (mask)))

/******************************************************************************
 * 字节序转换宏定义
 ******************************************************************************/

/** @brief 交换16位值的字节序（大端?小端转换） */
#define ENDIAN_SWAP_16B(x)         ((((uint16_t)(x) & 0xFF00U) >> 8U) | \
                                      (((uint16_t)(x) & 0x00FFU) << 8U))

/** @brief 交换32位值的字节序（大端?小端转换） */
#define ENDIAN_SWAP_32B(x)         ((((uint32_t)(x) & 0xFF000000UL) >> 24U) | \
                                      (((uint32_t)(x) & 0x00FF0000UL) >> 8U)  | \
                                      (((uint32_t)(x) & 0x0000FF00UL) << 8U)  | \
                                      (((uint32_t)(x) & 0x000000FFUL) << 24U))

/******************************************************************************
 * 字节访问宏定义
 ******************************************************************************/

/** @brief 访问32位值的第0字节（最低有效字节） */
#define BYTE_0(value)                (*((uint8_t *)(&(value))))

/** @brief 访问32位值的第1字节 */
#define BYTE_1(value)                (*((uint8_t *)(&(value)) + 1))

/** @brief 访问32位值的第2字节 */
#define BYTE_2(value)                (*((uint8_t *)(&(value)) + 2))

/** @brief 访问32位值的第3字节（最高有效字节） */
#define BYTE_3(value)                (*((uint8_t *)(&(value)) + 3))

/******************************************************************************
 * 函数声明 - 时间和延时
 ******************************************************************************/

/**
 * @brief 获取当前微秒计数器值
 * @return 当前微秒计数值
 */
uint32_t get_microseconds(void);

/**
 * @brief 微秒级延时函数
 * @param microseconds 延时时间（微秒）
 */
void delay_microseconds(uint32_t microseconds);

/**
 * @brief 微秒级延时函数（为兼容性保留的旧版本）
 * @param delay_us 延时时间（微秒）
 */
void Delay_us(uint32_t delay_us);

/******************************************************************************
 * 函数声明 - CRC校验计算
 ******************************************************************************/

/**
 * @brief 计算8位CRC校验码（慢速方法，逐位计算）
 * @param data 数据数组指针
 * @param length 数据长度（字节数）
 * @return 8位CRC校验码
 */
uint8_t calculate_crc8(uint8_t data[], uint8_t length);

/**
 * @brief 使用查找表计算8位CRC校验码（快速方法）
 * @param data 数据数组指针
 * @param length 数据长度（字节数）
 * @return 8位CRC校验码
 */
uint8_t calculate_crc8_fast(uint8_t data[], int length);

/**
 * @brief 生成CRC8查找表（用于快速CRC计算）
 * @param poly CRC多项式
 */
void generate_crc8_table(uint8_t poly);

/**
 * @brief 反转字节数组（可用于大小端转换）
 * @param data 数据数组指针
 * @param size 数据大小（字节数）
 */
void reverse_array(uint8_t *data, int size);

/**
 * @brief 反转字节数组（可用于大小端转换）
 * @param data 数据数组指针
 * @param size 数据大小（字节数）
 * @note 使用双指针原地交换算法，不占用额外空间
 *       时间复杂度：O(n/2)，空间复杂度：O(1)
 */
void reverseArray(uint8_t *data, int size);

/******************************************************************************
 * 函数声明 - 调试输出
 ******************************************************************************/

/**
 * @brief 启动DMA传输
 */
void start_debug_dma_transfer(void);

/**
 * @brief 格式化打印函数，重定向到ESP32串口
 * @param format 格式化字符串
 * @param ... 可变参数列表
 */
void DebugPrintf(const char *format, ...);

/**
 * @brief 重定向打印信息到ESP32串口
 * @param level 调试打印等级
 * @param format 格式化字符串
 * @param ... 可变参数列表
 */
void print_redirect_to_esp32(DEBUG_LEVEL level, const char *format, ...);

/**
 * @brief 标准输出重定向函数（用于printf）
 * @param ch 要输出的字符
 * @param f 文件指针
 * @return 输出的字符
 */
int fputc(int ch, FILE *f);

/******************************************************************************
 * 外部变量声明
 ******************************************************************************/

extern volatile uint8_t g_debug_uart_tx_complete; /**< 调试UART发送完成标志 */
extern DEBUG_RING_BUFFER g_debug_buffer;
#endif /* __UTILS_H__ */