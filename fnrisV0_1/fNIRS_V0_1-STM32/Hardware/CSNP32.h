#ifndef __CSNP32__H
#define __CSNP32__H

#include "main.h"
#include "sdio.h"

#define BLOCK_START_ADDR         0     /* Block start address      */
#define NUM_OF_BLOCKS            1   /* Total number of blocks   */
#define BUFFER_WORDS_SIZE        ((BLOCKSIZE * NUM_OF_BLOCKS) >> 2) /* Total data size in bytes */

typedef struct{
	uint8_t buf[512];
}fnirs_sd_buf;

typedef struct{
	uint8_t sd_baise;
	uint16_t bufsize;
	uint8_t batchnum;
	uint8_t blocknum;
	uint8_t idx;
	fnirs_sd_buf txbuf[3];
}SD_CARD_STRUCT;



void sdio_init(void);
HAL_StatusTypeDef sdio_read(uint8_t* buf, uint32_t addr, uint8_t num);
HAL_StatusTypeDef sdio_write(uint8_t* buf, uint32_t addr, uint8_t num);

#endif
