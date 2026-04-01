/**
 * @file circular_buffer.c
 * @brief 循环缓冲区实现文件
 * @version 1.0
 * @date 2024
 */

#include "circular_buffer.h"
#include <stdlib.h>
#include <string.h>
#include <esp_log.h>
#include "udp.h"
#include "transmit.h"


static const char *TAG = "BUFFER";
/**
 * @brief 验证循环缓冲区指针有效性
 * @param cb 循环缓冲区指针
 * @return 操作结果
 */
static inline circ_buf_result_t validate_buffer(circular_buffer_t *cb)
{
    if (cb == NULL) {
        return CIRC_BUF_ERROR_NULL_POINTER;
    }
    if (cb->buffer == NULL || cb->buffer_size == 0) {
        return CIRC_BUF_ERROR_INVALID_PARAM;
    }
    return CIRC_BUF_OK;
}

circ_buf_result_t circular_buffer_init(circular_buffer_t *cb, uint32_t size)
{
    if (cb == NULL) {
        return CIRC_BUF_ERROR_NULL_POINTER;
    }
    
    if (size == 0) {
        return CIRC_BUF_ERROR_INVALID_SIZE;
    }
    
    // 分配内存
    cb->buffer = (uint8_t*)malloc(size);
    if (cb->buffer == NULL) {
        return CIRC_BUF_ERROR_NO_MEMORY;
    }
    
    // 初始化参数
    cb->buffer_size = size;
    cb->write_pos = 0;
    cb->read_pos = 0;
    cb->data_len = 0;
    cb->allocated = true;
    
    return CIRC_BUF_OK;
}

circ_buf_result_t circular_buffer_init_static(circular_buffer_t *cb, uint8_t *buffer, uint32_t size)
{
    if (cb == NULL || buffer == NULL) {
        return CIRC_BUF_ERROR_NULL_POINTER;
    }
    
    if (size == 0) {
        return CIRC_BUF_ERROR_INVALID_SIZE;
    }
    
    // 使用静态缓冲区
    cb->buffer = buffer;
    cb->buffer_size = size;
    cb->write_pos = 0;
    cb->read_pos = 0;
    cb->data_len = 0;
    cb->allocated = false;
    
    return CIRC_BUF_OK;
}

circ_buf_result_t circular_buffer_deinit(circular_buffer_t *cb)
{
    if (cb == NULL) {
        return CIRC_BUF_ERROR_NULL_POINTER;
    }
    
    // 如果是动态分配的内存，则释放
    if (cb->allocated && cb->buffer != NULL) {
        free(cb->buffer);
    }
    
    // 重置所有参数
    cb->buffer = NULL;
    cb->buffer_size = 0;
    cb->write_pos = 0;
    cb->read_pos = 0;
    cb->data_len = 0;
    cb->allocated = false;
    
    return CIRC_BUF_OK;
}

circ_buf_result_t circular_buffer_reset(circular_buffer_t *cb)
{
    circ_buf_result_t result = validate_buffer(cb);
    if (result != CIRC_BUF_OK) {
        return result;
    }
    
    cb->write_pos = 0;
    cb->read_pos = 0;
    cb->data_len = 0;
    
    return CIRC_BUF_OK;
}

int circular_buffer_write(circular_buffer_t *cb, const uint8_t *data, uint32_t len)
{
    if (validate_buffer(cb) != CIRC_BUF_OK || data == NULL) {
        return -CIRC_BUF_ERROR_NULL_POINTER;
    }
    
    if (len == 0) {
        return 0;
    }
    
    // 检查剩余空间
    uint32_t free_space = cb->buffer_size - cb->data_len;
    if (len > free_space) {
        return -CIRC_BUF_ERROR_BUFFER_FULL;
    }
    
    uint32_t written = 0;
    
    for (uint32_t i = 0; i < len; i++) {
        cb->buffer[cb->write_pos] = data[i];
        cb->write_pos = (cb->write_pos + 1) % cb->buffer_size;
        cb->data_len++;
        written++;
    }
    
    return written;
}

int circular_buffer_write_force(circular_buffer_t *cb, const uint8_t *data, uint32_t len)
{
    if (validate_buffer(cb) != CIRC_BUF_OK || data == NULL) {
        return -CIRC_BUF_ERROR_NULL_POINTER;
    }
    
    if (len == 0) {
        return 0;
    }
    
    uint32_t written = 0;
    
    for (uint32_t i = 0; i < len; i++) {
        // 如果缓冲区满，丢弃最老的数据
        if (cb->data_len >= cb->buffer_size) {
            cb->read_pos = (cb->read_pos + 1) % cb->buffer_size;
            cb->data_len--;
        }
        
        cb->buffer[cb->write_pos] = data[i];
        cb->write_pos = (cb->write_pos + 1) % cb->buffer_size;
        cb->data_len++;
        written++;
    }
    
    return written;
}

int circular_buffer_read(circular_buffer_t *cb, uint8_t *data, uint32_t len)
{
    if (validate_buffer(cb) != CIRC_BUF_OK || data == NULL) {
        return -CIRC_BUF_ERROR_NULL_POINTER;
    }
    
    if (len == 0) {
        return 0;
    }
    
    // 限制读取长度为实际可用数据长度
    if (len > cb->data_len) {
        len = cb->data_len;
    }
    
    uint32_t read_count = 0;
    
    for (uint32_t i = 0; i < len; i++) {
        data[i] = cb->buffer[cb->read_pos];
        cb->read_pos = (cb->read_pos + 1) % cb->buffer_size;
        cb->data_len--;
        read_count++;
    }
    
    return read_count;
}

circ_buf_result_t circular_buffer_peek(circular_buffer_t *cb, uint32_t offset, uint8_t *data)
{
    circ_buf_result_t result = validate_buffer(cb);
    if (result != CIRC_BUF_OK) {
        return result;
    }
    
    if (data == NULL) {
        return CIRC_BUF_ERROR_NULL_POINTER;
    }
    
    if (offset >= cb->data_len) {
        return CIRC_BUF_ERROR_INVALID_PARAM;
    }
    
    uint32_t pos = (cb->read_pos + offset) % cb->buffer_size;
    *data = cb->buffer[pos];
    
    return CIRC_BUF_OK;
}

int circular_buffer_discard(circular_buffer_t *cb, uint32_t len)
{
    if (validate_buffer(cb) != CIRC_BUF_OK) {
        return -CIRC_BUF_ERROR_NULL_POINTER;
    }
    
    if (len == 0) {
        return 0;
    }
    
    // 限制丢弃长度为实际可用数据长度
    if (len > cb->data_len) {
        len = cb->data_len;
    }
    
    cb->read_pos = (cb->read_pos + len) % cb->buffer_size;
    cb->data_len -= len;
    
    return len;
}

int circular_buffer_find(circular_buffer_t *cb, const uint8_t *pattern, uint32_t pattern_len, uint32_t start_offset)
{
    if (validate_buffer(cb) != CIRC_BUF_OK || pattern == NULL) {
        return -CIRC_BUF_ERROR_NULL_POINTER;
    }
    
    if (pattern_len == 0 || start_offset >= cb->data_len) {
        return -CIRC_BUF_ERROR_INVALID_PARAM;
    }
    
    if (cb->data_len < pattern_len + start_offset) {
        return -1;  // 数据不够，无法匹配
    }
    
    // 从start_offset开始搜索
    for (uint32_t i = start_offset; i <= cb->data_len - pattern_len; i++) {
        bool match = true;
        
        // 检查是否匹配
        for (uint32_t j = 0; j < pattern_len; j++) {
            uint32_t pos = (cb->read_pos + i + j) % cb->buffer_size;
            if (cb->buffer[pos] != pattern[j]) {
                match = false;
                break;
            }
        }
        
        if (match) {
            return i;  // 返回匹配位置
        }
    }
    
    return -1;  // 未找到
}

int circular_buffer_get_data_len(circular_buffer_t *cb)
{
    if (validate_buffer(cb) != CIRC_BUF_OK) {
        return -CIRC_BUF_ERROR_NULL_POINTER;
    }
    
    return cb->data_len;
}

int circular_buffer_get_free_space(circular_buffer_t *cb)
{
    if (validate_buffer(cb) != CIRC_BUF_OK) {
        return -CIRC_BUF_ERROR_NULL_POINTER;
    }
    
    return cb->buffer_size - cb->data_len;
}

bool circular_buffer_is_empty(circular_buffer_t *cb)
{
    if (validate_buffer(cb) != CIRC_BUF_OK) {
        return false;
    }
    
    return cb->data_len == 0;
}

bool circular_buffer_is_full(circular_buffer_t *cb)
{
    if (validate_buffer(cb) != CIRC_BUF_OK) {
        return false;
    }
    
    return cb->data_len >= cb->buffer_size;
}

const char* circular_buffer_get_error_string(circ_buf_result_t result)
{
    switch (result) {
        case CIRC_BUF_OK:
            return "Success";
        case CIRC_BUF_ERROR_NULL_POINTER:
            return "Null pointer error";
        case CIRC_BUF_ERROR_INVALID_SIZE:
            return "Invalid size";
        case CIRC_BUF_ERROR_NO_MEMORY:
            return "Memory allocation failed";
        case CIRC_BUF_ERROR_BUFFER_FULL:
            return "Buffer is full";
        case CIRC_BUF_ERROR_BUFFER_EMPTY:
            return "Buffer is empty";
        case CIRC_BUF_ERROR_INVALID_PARAM:
            return "Invalid parameter";
        default:
            return "Unknown error";
    }
}
/**
 * @brief 查找帧头位置
 * @param cb 循环缓冲区指针
 * @return 帧头位置偏移量，-1表示未找到
 */
static int find_frame_header(circular_buffer_t *cb)
{
    int data_len = circular_buffer_get_data_len(cb);
    if (data_len < 2) {
        return -1;
    }
    
    // 构造帧头模式
    uint8_t frame_header[2] = {0xBA, 0xBA};
    
    // 使用循环缓冲区的查找函数
    return circular_buffer_find(cb, frame_header, 2, 0);
}

/**
 * @brief 从循环缓冲区读取指定偏移位置的字节
 * @param cb 循环缓冲区指针
 * @param offset 偏移量
 * @param data 存储结果的指针
 * @return 操作结果
 */
static bool peek_byte_at_offset(circular_buffer_t *cb, uint32_t offset, uint8_t *data)
{
    return circular_buffer_peek(cb, offset, data) == CIRC_BUF_OK;
}

/**
 * @brief 验证并处理完整帧
 * @param cb 循环缓冲区指针
 * @param frame_start 帧头位置
 * @return true表示处理成功，false表示帧不完整或错误
 */
static frame_process_result_t  process_frame(circular_buffer_t *cb, uint32_t frame_start)
{
    int available_data = circular_buffer_get_data_len(cb);
    
    // 检查是否有足够的数据来读取长度字段
    if (available_data < (int)(frame_start + 11)) {
        ESP_LOGI(TAG, "No enough data. ");
        return FRAME_INCOMPLETE;  // 数据不够，等待更多数据
    }
    
    // 读取数据长度字段 (假设在第7、8字节位置，大端序)
    uint8_t len_high, len_low;
    if (!peek_byte_at_offset(cb, frame_start + 7, &len_high) ||
        !peek_byte_at_offset(cb, frame_start + 8, &len_low)) {
        ESP_LOGE(TAG, "Failed to read length field");
        return FRAME_ERROR;
    }
    
    uint16_t data_len = (len_high << 8) | len_low;
    
    // 计算完整帧长度
    int total_frame_len = MIN_FRAME_SIZE + data_len;
    
     // 验证帧长度合理性
    if (total_frame_len > MAX_FRAME_SIZE || data_len > MAX_FRAME_SIZE - 11) {
        ESP_LOGE(TAG, "Frame too large: total=%d, data=%d", total_frame_len, data_len);
        // 丢弃损坏的帧头，继续处理
        // circular_buffer_discard(cb, 1);
        return FRAME_INVALID;
    }
    
    // 检查是否接收到完整帧
    if (available_data < (int)(frame_start + total_frame_len)) {
        ESP_LOGI(TAG, "data frame incomplete.");
        return FRAME_INCOMPLETE;  // 帧不完整，等待更多数据
    }
    
    // 先丢弃帧头之前的无效数据（但不要丢弃太多）
    if (frame_start > 0) {
        int discarded = circular_buffer_discard(cb, frame_start);
        if (discarded > 0) {
            ESP_LOGW(TAG, "Discarded %d invalid bytes", discarded);
        }
        // 更新frame_start，因为丢弃数据后位置变了
        frame_start = 0;
    }
    
    
    // 读取完整帧
    uint8_t frame_buf[MAX_FRAME_SIZE];
    int read_len = circular_buffer_read(cb, frame_buf, total_frame_len);
    
    if (read_len != total_frame_len) {
        ESP_LOGE(TAG, "Frame read error: expected %d, got %d", total_frame_len, read_len);
        return FRAME_ERROR;
    }
    
    // 验证帧头
    if (frame_buf[0] != 0xba || frame_buf[1] != 0xba) {
        ESP_LOGE(TAG, "Frame header verification failed");
        return FRAME_INVALID;
    }
    
    // 验证长度字段
    uint16_t expected_data_len = (frame_buf[7] << 8) | frame_buf[8];
    if (expected_data_len != data_len) {
        ESP_LOGE(TAG, "Frame length mismatch: expected %d, got %d", data_len, expected_data_len);
        return FRAME_ERROR;
    }
    
// 打印接收到的数据（调试用）
    ESP_LOGI(TAG, "Received valid frame: %d bytes", total_frame_len);
    // printf("FRAME DATA: ");
    // for (uint32_t i = 0; i < total_frame_len; i++) {
    //     printf("%02X ", frame_buf[i]);
    // }
    // printf("\r\n");
    
    //如果是连接命令，则直接返回类型帧
    if(CMD_CONN == (T_COMMAND) frame_buf[CMD_PLACE]){
        stype = (SENSOR_TYPE) frame_buf[5];
        ESP_LOGI(TAG, "sensor type: %d", stype);
        return FRAME_SUCCESS;
    }

    // 发送UDP数据
    udp_safe_send(frame_buf, total_frame_len);
    
    return FRAME_SUCCESS;
}

/**
 * @brief 处理接收缓冲区中的所有完整帧
 * @param cb 循环缓冲区指针
 */
void process_all_frames(circular_buffer_t *cb)
{
    int max_iterations = 20; // 防止无限循环
    
    while (max_iterations-- > 0 && !circular_buffer_is_empty(cb)) {
        // 查找帧头
        int header_pos = find_frame_header(cb);
        
        if (header_pos == -1) {
            ESP_LOGE(TAG, "No frame header found in buffer");
            // 没有找到帧头，检查缓冲区是否需要清理
            int data_len = circular_buffer_get_data_len(cb);
            int free_space = circular_buffer_get_free_space(cb);
            
            if (free_space < (int)(cb->buffer_size * 0.1) && data_len > MAX_FRAME_SIZE) {
                uint32_t discard_len = data_len - MAX_FRAME_SIZE;
                circular_buffer_discard(cb, discard_len);
                ESP_LOGW(TAG, "Buffer cleanup: discarded %d bytes", (int)discard_len);
            }
            break;
        }
        // 处理帧并获取明确的结果状态
        frame_process_result_t result = process_frame(cb, (uint32_t)header_pos);
        
        switch (result) {
            case FRAME_SUCCESS:
                // 成功处理一帧，继续查找下一帧
                break;
                
            case FRAME_INCOMPLETE:
                // 帧不完整，退出循环等待更多数据
                ESP_LOGD(TAG, "Incomplete frame, waiting for more data");
                return; // 直接返回，不再继续处理
                
            case FRAME_INVALID:
                // 帧无效，丢弃帧头第一个字节继续查找
                circular_buffer_discard(cb, 1);
                ESP_LOGD(TAG, "Invalid frame, discarded 1 byte");
                break;
                
            case FRAME_ERROR:
                // 处理错误，丢弃帧头继续查找
                circular_buffer_discard(cb, header_pos > 0 ? (uint32_t)header_pos : 1);
                ESP_LOGE(TAG, "Frame processing error, discarded data");
                break;
        }
    }
    
    // if (max_iterations <= 0) {
    //     ESP_LOGW(TAG, "Frame processing loop limit reached");
    // }
}
