/**
 * @file circular_buffer.h
 * @brief 循环缓冲区实现头文件
 * @version 1.0
 * @date 2024
 */

#ifndef CIRCULAR_BUFFER_H
#define CIRCULAR_BUFFER_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FRAME_HEADER_1      0xBA    // 帧头第一个字节
#define FRAME_HEADER_2      0xBA    // 帧头第二个字节
#define MIN_FRAME_SIZE      11      // 最小帧长度
#define MAX_FRAME_SIZE      30    // 最大帧长度
/**
 * @brief 默认循环缓冲区大小
 */
#define CIRCULAR_BUFFER_DEFAULT_SIZE    4096

/**
 * @brief 循环缓冲区结构体
 */
typedef struct {
    uint8_t *buffer;                /**< 数据缓冲区指针 */
    uint32_t buffer_size;           /**< 缓冲区总大小 */
    volatile uint32_t write_pos;    /**< 写入位置 */
    volatile uint32_t read_pos;     /**< 读取位置 */
    volatile uint32_t data_len;     /**< 当前数据长度 */
    bool allocated;                 /**< 是否为动态分配的缓冲区 */
} circular_buffer_t;

/**
 * @brief 错误代码定义
 */
typedef enum {
    CIRC_BUF_OK = 0,                /**< 操作成功 */
    CIRC_BUF_ERROR_NULL_POINTER,    /**< 空指针错误 */
    CIRC_BUF_ERROR_INVALID_SIZE,    /**< 无效大小 */
    CIRC_BUF_ERROR_NO_MEMORY,       /**< 内存分配失败 */
    CIRC_BUF_ERROR_BUFFER_FULL,     /**< 缓冲区已满 */
    CIRC_BUF_ERROR_BUFFER_EMPTY,    /**< 缓冲区为空 */
    CIRC_BUF_ERROR_INVALID_PARAM    /**< 无效参数 */
} circ_buf_result_t;

/**
 * @brief 初始化循环缓冲区（使用动态分配）
 * @param cb 循环缓冲区指针
 * @param size 缓冲区大小
 * @return 操作结果
 */
circ_buf_result_t circular_buffer_init(circular_buffer_t *cb, uint32_t size);

/**
 * @brief 使用静态缓冲区初始化循环缓冲区
 * @param cb 循环缓冲区指针
 * @param buffer 静态缓冲区指针
 * @param size 缓冲区大小
 * @return 操作结果
 */
circ_buf_result_t circular_buffer_init_static(circular_buffer_t *cb, uint8_t *buffer, uint32_t size);

/**
 * @brief 释放循环缓冲区资源
 * @param cb 循环缓冲区指针
 * @return 操作结果
 */
circ_buf_result_t circular_buffer_deinit(circular_buffer_t *cb);

/**
 * @brief 重置循环缓冲区（清空所有数据）
 * @param cb 循环缓冲区指针
 * @return 操作结果
 */
circ_buf_result_t circular_buffer_reset(circular_buffer_t *cb);

/**
 * @brief 向循环缓冲区写入数据
 * @param cb 循环缓冲区指针
 * @param data 要写入的数据缓冲区
 * @param len 数据长度
 * @return 实际写入的字节数，负值表示错误
 */
int32_t circular_buffer_write(circular_buffer_t *cb, const uint8_t *data, uint32_t len);

/**
 * @brief 向循环缓冲区强制写入数据（覆盖旧数据）
 * @param cb 循环缓冲区指针
 * @param data 要写入的数据缓冲区
 * @param len 数据长度
 * @return 实际写入的字节数，负值表示错误
 */
int32_t circular_buffer_write_force(circular_buffer_t *cb, const uint8_t *data, uint32_t len);

/**
 * @brief 从循环缓冲区读取数据
 * @param cb 循环缓冲区指针
 * @param data 目标缓冲区
 * @param len 要读取的字节数
 * @return 实际读取的字节数，负值表示错误
 */
int32_t circular_buffer_read(circular_buffer_t *cb, uint8_t *data, uint32_t len);

/**
 * @brief 从循环缓冲区的指定位置查看字节（不移动读取位置）
 * @param cb 循环缓冲区指针
 * @param offset 相对于读取位置的偏移量
 * @param data 存储查看结果的指针
 * @return 操作结果
 */
circ_buf_result_t circular_buffer_peek(circular_buffer_t *cb, uint32_t offset, uint8_t *data);

/**
 * @brief 从循环缓冲区丢弃指定数量的字节
 * @param cb 循环缓冲区指针
 * @param len 要丢弃的字节数
 * @return 实际丢弃的字节数，负值表示错误
 */
int32_t circular_buffer_discard(circular_buffer_t *cb, uint32_t len);

/**
 * @brief 在循环缓冲区中查找指定字节序列
 * @param cb 循环缓冲区指针
 * @param pattern 要查找的字节序列
 * @param pattern_len 序列长度
 * @param start_offset 开始查找的偏移量
 * @return 找到的位置偏移量，-1表示未找到，负值表示错误
 */
int32_t circular_buffer_find(circular_buffer_t *cb, const uint8_t *pattern, uint32_t pattern_len, uint32_t start_offset);

/**
 * @brief 获取循环缓冲区中可用数据长度
 * @param cb 循环缓冲区指针
 * @return 可用数据长度，负值表示错误
 */
int32_t circular_buffer_get_data_len(circular_buffer_t *cb);

/**
 * @brief 获取循环缓冲区剩余空间大小
 * @param cb 循环缓冲区指针
 * @return 剩余空间大小，负值表示错误
 */
int32_t circular_buffer_get_free_space(circular_buffer_t *cb);

/**
 * @brief 检查循环缓冲区是否为空
 * @param cb 循环缓冲区指针
 * @return true表示为空，false表示非空或错误
 */
bool circular_buffer_is_empty(circular_buffer_t *cb);

/**
 * @brief 检查循环缓冲区是否已满
 * @param cb 循环缓冲区指针
 * @return true表示已满，false表示未满或错误
 */
bool circular_buffer_is_full(circular_buffer_t *cb);

/**
 * @brief 获取错误码对应的字符串描述
 * @param result 错误码
 * @return 错误描述字符串
 */
const char* circular_buffer_get_error_string(circ_buf_result_t result);

/**
 * @brief 处理接收缓冲区中的所有完整帧
 * @param cb 循环缓冲区指针
 */
void process_all_frames(circular_buffer_t *cb);

#ifdef __cplusplus
}
#endif

#endif /* CIRCULAR_BUFFER_H */