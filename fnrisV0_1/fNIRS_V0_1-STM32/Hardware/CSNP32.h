#ifndef __CSNP32_H
#define __CSNP32_H

/******************************************************************************
 * CSNP32 - SD卡存储模块
 * 功能：提供SD卡读写接口，支持大容量数据存储
 * 特别针对fNIRS系统的数据存储需求设计
 ******************************************************************************/

#include "main.h"
#include "sdio.h"

/******************************************************************************
 * SD卡配置常量定义
 ******************************************************************************/

#define BLOCK_START_ADDR         0       /**< SD卡起始块地址 */
#define DEFAULT_NUM_OF_BLOCKS    1       /**< 默认块数量 */
#define BLOCK_SIZE_BYTES         512     /**< 每个块的字节数 */

/* 计算缓冲区大小（以32位字为单位） */
#define BUFFER_WORDS_SIZE        ((BLOCK_SIZE_BYTES * DEFAULT_NUM_OF_BLOCKS) >> 2)

/******************************************************************************
 * SD卡缓冲区结构体定义
 ******************************************************************************/

/**
 * @brief SD卡单个块缓冲区结构体
 * @note 对应SD卡的一个扇区（512字节）
 */
typedef struct {
    uint8_t buffer[BLOCK_SIZE_BYTES];    /**< 512字节缓冲区 */
} SD_BLOCK_BUFFER;

/**
 * @brief SD卡管理结构体
 * @note 管理SD卡的读写缓冲区和状态信息
 */
typedef struct {
    uint32_t sd_base_address;            /**< SD卡基地址（块地址） */
    uint16_t buffer_size;          /**< 总缓冲区大小（字节） */
    uint8_t  batches_per_block;          /**< 每个块包含的数据包批次数 */
    uint8_t  blocks_to_write;            /**< 每次写入的块数 */
    uint8_t  buffer_idx;         /**< 当前激活的缓冲区索引（0-2） */
    SD_BLOCK_BUFFER tx_buffer[3];        /**< 三重缓冲区，用于乒乓操作 */
} SD_CARD_STRUCT;

/******************************************************************************
 * 宏定义 - 缓冲区操作
 ******************************************************************************/

/**
 * @brief 获取当前激活的发送缓冲区
 */
#define SD_GET_CURRENT_TX_BUFFER(sd_struct) \
    ((sd_struct)->tx_buffer[(sd_struct)->current_buffer_idx].buffer)

/**
 * @brief 获取下一个发送缓冲区
 */
#define SD_GET_NEXT_TX_BUFFER(sd_struct) \
    ((sd_struct)->tx_buffer[((sd_struct)->current_buffer_idx + 1) % 3].buffer)

/**
 * @brief 获取备用读取缓冲区（索引2）
 */
#define SD_GET_READ_BUFFER(sd_struct) \
    ((sd_struct)->tx_buffer[2].buffer)

/**
 * @brief 切换当前缓冲区索引
 */
#define SD_TOGGLE_BUFFER_IDX(sd_struct) \
    do { \
        (sd_struct)->current_buffer_idx = ((sd_struct)->current_buffer_idx + 1) % 3; \
    } while(0)

/******************************************************************************
 * 函数声明 - SD卡驱动接口
 ******************************************************************************/

/**
 * @brief 初始化SD卡接口
 * @note 配置SDIO硬件接口，初始化SD卡
 *       必须在调用其他SD卡函数之前执行
 */
void sdio_init(void);

/**
 * @brief 从SD卡读取数据
 * @param read_buffer  读取数据缓冲区指针
 * @param block_addr   起始块地址
 * @param block_count  要读取的块数量
 * @return HAL_StatusTypeDef HAL库状态码
 *         HAL_OK      : 读取成功
 *         HAL_ERROR   : 读取失败
 *         HAL_BUSY    : SD卡忙
 *         HAL_TIMEOUT : 操作超时
 * @note 支持多块连续读取，最大块数受缓冲区限制
 */
HAL_StatusTypeDef sdio_read(uint8_t* read_buffer, 
                           uint32_t block_addr, 
                           uint8_t block_count);

/**
 * @brief 向SD卡写入数据
 * @param write_buffer 写入数据缓冲区指针
 * @param block_addr   起始块地址
 * @param block_count  要写入的块数量
 * @return HAL_StatusTypeDef HAL库状态码
 *         HAL_OK      : 写入成功
 *         HAL_ERROR   : 写入失败
 *         HAL_BUSY    : SD卡忙
 *         HAL_TIMEOUT : 操作超时
 * @note 支持多块连续写入，数据必须按块对齐（512字节边界）
 */
HAL_StatusTypeDef sdio_write(uint8_t* write_buffer, 
                            uint32_t block_addr, 
                            uint8_t block_count);

/******************************************************************************
 * 函数声明 - 高级SD卡操作（可选，根据需求添加）
 ******************************************************************************/

/**
 * @brief 检查SD卡状态
 * @return uint8_t 状态码
 *         0: SD卡正常
 *         1: SD卡未初始化
 *         2: SD卡读写错误
 *         3: SD卡容量已满
 */
uint8_t sdio_check_status(void);

/**
 * @brief 获取SD卡容量信息
 * @param[out] total_blocks  总块数
 * @param[out] free_blocks   空闲块数
 * @return HAL_StatusTypeDef HAL库状态码
 */
HAL_StatusTypeDef sdio_get_capacity(uint32_t* total_blocks, 
                                   uint32_t* free_blocks);

/**
 * @brief 格式化SD卡（谨慎使用）
 * @param quick_format 快速格式化标志：1=快速，0=完整
 * @return HAL_StatusTypeDef HAL库状态码
 * @warning 此操作会删除SD卡上所有数据
 */
HAL_StatusTypeDef sdio_format(uint8_t quick_format);

/**
 * @brief SD卡读写性能测试
 * @param test_size_kb 测试数据大小（KB）
 * @param[out] write_speed 写入速度（KB/s）
 * @param[out] read_speed  读取速度（KB/s）
 * @return HAL_StatusTypeDef HAL库状态码
 */
HAL_StatusTypeDef sdio_performance_test(uint32_t test_size_kb,
                                       float* write_speed,
                                       float* read_speed);

/******************************************************************************
 * 错误码定义
 ******************************************************************************/

#define SDIO_ERROR_NONE          0x00    /**< 无错误 */
#define SDIO_ERROR_INIT_FAILED   0x01    /**< 初始化失败 */
#define SDIO_ERROR_READ_FAILED   0x02    /**< 读取失败 */
#define SDIO_ERROR_WRITE_FAILED  0x03    /**< 写入失败 */
#define SDIO_ERROR_TIMEOUT       0x04    /**< 操作超时 */
#define SDIO_ERROR_BUSY          0x05    /**< 设备忙 */
#define SDIO_ERROR_CARD_NOT_PRESENT 0x06 /**< SD卡不存在 */
#define SDIO_ERROR_CARD_LOCKED   0x07    /**< SD卡写保护 */
#define SDIO_ERROR_INVALID_PARAM 0x08    /**< 参数无效 */

/******************************************************************************
 * SD卡类型定义
 ******************************************************************************/

typedef enum {
    SD_CARD_TYPE_UNKNOWN = 0,      /**< 未知类型 */
    SD_CARD_TYPE_V1 = 1,           /**< SD卡V1.0 */
    SD_CARD_TYPE_V2 = 2,           /**< SD卡V2.0 */
    SD_CARD_TYPE_SDHC = 3,         /**< SDHC卡（2GB-32GB） */
    SD_CARD_TYPE_SDXC = 4,         /**< SDXC卡（32GB-2TB） */
} SD_CARD_TYPE;

#endif /* __CSNP32_H */