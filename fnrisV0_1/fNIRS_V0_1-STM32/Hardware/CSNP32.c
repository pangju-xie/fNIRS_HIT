#include "CSNP32.h"
#include "utils.h"

/******************************************************************************
 * Global Variables Definition
 ******************************************************************************/

volatile uint8_t g_sd_write_ready = 1;  /**< SD card write ready flag, set to 1 when DMA transfer completes */

/******************************************************************************
 * SD Card DMA Transfer Complete Callback Function
 ******************************************************************************/

/**
 * @brief SD card DMA transfer complete callback function
 * @param hsd1 SD card handle pointer
 * @note Automatically called when SD card DMA write operation completes, sets write ready flag
 */
void HAL_SD_TxCpltCallback(SD_HandleTypeDef *hsd1)
{
    if (hsd1->Instance == hsd.Instance) {
        g_sd_write_ready = 1;  /* Set write ready flag */
    }
}

/******************************************************************************
 * SD Card Initialization Function
 ******************************************************************************/

/**
 * @brief Initialize SD card interface
 * @note Configure SDIO hardware interface, initialize SD card and print card information
 *       If initialization succeeds, erase specified area for data storage
 */
void sdio_init(void)
{
    HAL_SD_CardCIDTypeDef card_cid = {0};
    HAL_SD_CardStatusTypeDef card_status = {0};
    
    /* Check SD card state */
    if (HAL_SD_GetCardState(&hsd) != HAL_SD_CARD_TRANSFER) {
        DebugPrintf("SD card initialization failed: card state abnormal\r\n");
        return;
    }
    
    DebugPrintf("========== SD Card Initialization Successful ==========\r\n");
    
    /* Print basic SD card information */
    DebugPrintf("SD Card Basic Information:\r\n");
    DebugPrintf("  Physical Capacity : %llu MB\r\n", 
               (unsigned long long)hsd.SdCard.BlockSize * hsd.SdCard.BlockNbr / 1024 / 1024);
    DebugPrintf("  Block Size       : %d bytes\r\n", hsd.SdCard.BlockSize);
    DebugPrintf("  Block Count      : %d\r\n", hsd.SdCard.BlockNbr);
    DebugPrintf("  Logical Block Size: %d bytes\r\n", hsd.SdCard.LogBlockSize);
    DebugPrintf("  Logical Block Count: %d\r\n", hsd.SdCard.LogBlockNbr);
    DebugPrintf("  Relative Card Address: 0x%04X\r\n", hsd.SdCard.RelCardAdd);
    
    /* Print card type information */
    switch (hsd.SdCard.CardType) {
        case CARD_SDSC:
            DebugPrintf("  Card Type       : SDSC (Standard Capacity, <=2GB)\r\n");
            break;
        case CARD_SDHC_SDXC:
            DebugPrintf("  Card Type       : SDHC/SDXC (High Capacity/Extended Capacity)\r\n");
            break;
        case CARD_SECURED:
            DebugPrintf("  Card Type       : Secured Digital Card\r\n");
            break;
        default:
            DebugPrintf("  Card Type       : Unknown (0x%02X)\r\n", hsd.SdCard.CardType);
            break;
    }
    
    /* Read and print CID register information */
    if (HAL_SD_GetCardCID(&hsd, &card_cid) == HAL_OK) {
        DebugPrintf("CID Register Information:\r\n");
        DebugPrintf("  Manufacturer ID : 0x%02X\r\n", card_cid.ManufacturerID);
        DebugPrintf("  Product Revision: %d.%d\r\n", 
                   (card_cid.ProdRev >> 4) & 0x0F, card_cid.ProdRev & 0x0F);
        DebugPrintf("  Serial Number   : 0x%08lX\r\n", card_cid.ProdSN);
        DebugPrintf("  Manufacturing Date: %d/%d\r\n", 
                   card_cid.ManufactDate & 0x0F,  /* Month */
                   ((card_cid.ManufactDate >> 4) & 0xFFF) + 2000);  /* Year */
    }
    
    /* Read and print card status information */
    if (HAL_SD_GetCardStatus(&hsd, &card_status) == HAL_OK) {
        DebugPrintf("SD Card Status Information:\r\n");
        DebugPrintf("  Secured Mode    : %s\r\n", (card_status.SecuredMode == 1) ? "Secured" : "Not Secured");
    }
    
    /* Wait for card to enter transfer state */
    uint32_t wait_timeout = 1000;
    while (HAL_SD_GetCardState(&hsd) != HAL_SD_CARD_TRANSFER && wait_timeout--) {
        Delay_us(10);
    }
    
    if (wait_timeout == 0) {
        DebugPrintf("Error: SD card cannot enter transfer state\r\n");
        return;
    }
    
    /* Erase specified area for data storage */
    DebugPrintf("Erasing storage area: Start Block=%d, Block Count=%d...\r\n", 
               BLOCK_START_ADDR, DEFAULT_NUM_OF_BLOCKS);
    
    if (HAL_SD_Erase(&hsd, BLOCK_START_ADDR, DEFAULT_NUM_OF_BLOCKS) == HAL_OK) {
        DebugPrintf("Storage area erase successful\r\n");
    } else {
        DebugPrintf("Warning: Storage area erase failed\r\n");
    }
    
    DebugPrintf("========== SD Card Initialization Complete ==========\r\n");
}

/******************************************************************************
 * SD Card Read Operation Function
 ******************************************************************************/

/**
 * @brief Read data from SD card
 * @param read_buffer  Read data buffer pointer
 * @param block_addr   Start block address
 * @param block_count  Number of blocks to read
 * @return HAL_StatusTypeDef HAL library status code
 *         HAL_OK      : Read successful
 *         HAL_ERROR   : Read failed
 *         HAL_TIMEOUT : Operation timeout
 */
HAL_StatusTypeDef sdio_read(uint8_t* read_buffer, 
                           uint32_t block_addr, 
                           uint8_t block_count)
{
    HAL_StatusTypeDef result = HAL_ERROR;
    uint32_t retry_count = 0;
    const uint32_t MAX_RETRY_COUNT = 100;
    
    /* Parameter validation */
    if (read_buffer == NULL || block_count == 0) {
        DebugPrintf("SD read error: Invalid parameters\r\n");
        return HAL_ERROR;
    }
    
    /* Check SD card state */
    if (HAL_SD_GetCardState(&hsd) != HAL_SD_CARD_TRANSFER) {
        DebugPrintf("SD read error: Card not ready\r\n");
        return HAL_ERROR;
    }
    
    DebugPrintf("SD card reading: Address=%lu, Block Count=%u...\r\n", 
               (unsigned long)block_addr, block_count);
    
    /* Try to read data with retry mechanism */
    while (retry_count < MAX_RETRY_COUNT) {
        result = HAL_SD_ReadBlocks(&hsd, read_buffer, block_addr, 
                                  block_count, 1000);
        
        if (result == HAL_OK) {
            /* Wait for read operation to complete - alternative method */
            uint32_t read_wait_timeout = 5000;
            while (HAL_SD_GetCardState(&hsd) != HAL_SD_CARD_TRANSFER && read_wait_timeout--) {
                Delay_us(100);
            }
            
            if (read_wait_timeout > 0) {
                DebugPrintf("SD card read successful\r\n");
                return HAL_OK;
            } else {
                DebugPrintf("SD read error: Read operation timeout\r\n");
                result = HAL_TIMEOUT;
            }
        }
        
        /* Read failed, wait before retry */
        retry_count++;
        if (retry_count < MAX_RETRY_COUNT) {
            Delay_us(50);  /* Wait 50 microseconds before retry */
        }
    }
    
    /* All retries failed */
    DebugPrintf("SD card read failed, retry count: %lu\r\n", (unsigned long)retry_count);
    return result;
}

/******************************************************************************
 * SD Card Write Operation Function
 ******************************************************************************/

/**
 * @brief Write data to SD card
 * @param write_buffer Write data buffer pointer
 * @param block_addr   Start block address
 * @param block_count  Number of blocks to write
 * @return HAL_StatusTypeDef HAL library status code
 *         HAL_OK      : Write successful
 *         HAL_ERROR   : Write failed
 *         HAL_BUSY    : Device busy (DMA transfer in progress)
 *         HAL_TIMEOUT : Operation timeout
 */
HAL_StatusTypeDef sdio_write(uint8_t* write_buffer, 
                            uint32_t block_addr, 
                            uint8_t block_count)
{
    HAL_StatusTypeDef result = HAL_ERROR;
    uint32_t retry_count = 0;
    const uint32_t MAX_RETRY_COUNT = 100;
    
    /* Parameter validation */
    if (write_buffer == NULL || block_count == 0) {
        DebugPrintf("SD write error: Invalid parameters\r\n");
        return HAL_ERROR;
    }
    
    /* Check SD card state */
    if (HAL_SD_GetCardState(&hsd) != HAL_SD_CARD_TRANSFER) {
        DebugPrintf("SD write error: Card not ready\r\n");
        return HAL_ERROR;
    }
    
    DebugPrintf("\r\nSD card writing: Address=%lu, Block Count=%u...\r\n", 
               (unsigned long)block_addr, block_count);
    
    /* Write data using DMA with retry mechanism */
    while (retry_count < MAX_RETRY_COUNT) {
        /* Check write ready flag (DMA transfer complete) */
        if (g_sd_write_ready) {
            g_sd_write_ready = 0;  /* Clear write ready flag */
            
            result = HAL_SD_WriteBlocks_DMA(&hsd, write_buffer, block_addr, block_count);
            
            if (result == HAL_OK) {
                /* DMA transfer started, wait for completion */
                uint32_t dma_wait_timeout = 5000;  /* 5 second timeout */
                while (!g_sd_write_ready && dma_wait_timeout--) {
                    Delay_us(100);  /* Check every 100 microseconds */
                }
                
                if (g_sd_write_ready) {
                    /* Check if write operation completed - alternative method */
                    uint32_t write_wait_timeout = 5000;
                    while (HAL_SD_GetCardState(&hsd) != HAL_SD_CARD_TRANSFER && write_wait_timeout--) {
                        Delay_us(100);
                    }
                    
                    if (write_wait_timeout > 0) {
                        DebugPrintf("SD card write successful\r\n");
                        return HAL_OK;
                    } else {
                        DebugPrintf("SD write error: Write operation timeout\r\n");
                        result = HAL_TIMEOUT;
                    }
                } else {
                    DebugPrintf("SD write error: DMA transfer timeout\r\n");
                    result = HAL_TIMEOUT;
                    g_sd_write_ready = 1;  /* Force set write ready flag */
                }
            } else if (result == HAL_BUSY) {
                DebugPrintf("SD write error: Device busy\r\n");
                g_sd_write_ready = 1;  /* Restore write ready flag */
            } else {
                DebugPrintf("SD write error: DMA start failed (Error code: 0x%08lX)\r\n", 
                           (unsigned long)result);
                g_sd_write_ready = 1;  /* Restore write ready flag */
            }
        } else {
            result = HAL_BUSY;
        }
        
        /* Operation failed, wait before retry */
        retry_count++;
        if (retry_count < MAX_RETRY_COUNT) {
            Delay_us(100);  /* Wait 100 microseconds before retry */
        }
    }
    
    /* All retries failed */
    DebugPrintf("SD card write failed, retry count: %lu\r\n", (unsigned long)retry_count);
    return result;
}

/******************************************************************************
 * SD Card Status Check Function (Optional Implementation)
 ******************************************************************************/

/**
 * @brief Check SD card status
 * @return uint8_t Status code
 */
uint8_t sdio_check_status(void)
{
    HAL_SD_CardStateTypeDef card_state = HAL_SD_GetCardState(&hsd);
    
    switch (card_state) {
        case HAL_SD_CARD_TRANSFER:
            return SDIO_ERROR_NONE;
            
        case HAL_SD_CARD_ERROR:
            DebugPrintf("SD card error state\r\n");
            return SDIO_ERROR_READ_FAILED;
            
        case HAL_SD_CARD_DISCONNECTED:
            DebugPrintf("SD card not connected\r\n");
            return SDIO_ERROR_CARD_NOT_PRESENT;

        default:
            DebugPrintf("SD card unknown state: %d\r\n", card_state);
            return SDIO_ERROR_INIT_FAILED;
    }
}
