#include "CSNP32.h"
#include "utils.h"

volatile uint8_t SDWriteReady = 1;

void HAL_SD_TxCpltCallback(SD_HandleTypeDef *hsd1){
	if(hsd1->Instance == hsd.Instance){
		SDWriteReady = 1;
	}
}


void sdio_init(void){
	if(HAL_SD_GetCardState(&hsd) == HAL_SD_CARD_TRANSFER){    
    DebugPrintf("Initialize SD card successfully!\r\n");
    // 打印SD卡基本信息
    DebugPrintf(" SD card information! \r\n");
    DebugPrintf(" CardCapacity  : %llu \r\n", (unsigned long long)hsd.SdCard.BlockSize * hsd.SdCard.BlockNbr);// 显示容量
    DebugPrintf(" CardBlockSize : %d \r\n", hsd.SdCard.BlockSize);   	// 块大小
    DebugPrintf(" LogBlockNbr   : %d \r\n", hsd.SdCard.LogBlockNbr);	// 逻辑块数量
		DebugPrintf(" LogBlockSize  : %d \r\n", hsd.SdCard.LogBlockSize);	// 逻辑块大小
    DebugPrintf(" RCA           : %d \r\n", hsd.SdCard.RelCardAdd);  	// 卡相对地址
    DebugPrintf(" CardType      : %d \r\n", hsd.SdCard.CardType);    	// 卡类型
    // 读取并打印SD卡的CID信息
    HAL_SD_CardCIDTypeDef sdcard_cid;
    HAL_SD_GetCardCID(&hsd,&sdcard_cid);
    DebugPrintf(" ManufacturerID: %d \r\n",sdcard_cid.ManufacturerID);
		
		while(HAL_SD_GetCardState(&hsd) != HAL_SD_CARD_TRANSFER);
		if(HAL_SD_Erase(&hsd, BLOCK_START_ADDR, NUM_OF_BLOCKS) == HAL_OK){		
			DebugPrintf("\r\nErase Block Success!\r\n");
		}
  }
  else{
    DebugPrintf("SD card init fail!\r\n" );
  }
}


HAL_StatusTypeDef sdio_read(uint8_t* buf, uint32_t addr, uint8_t num){
	HAL_StatusTypeDef res = HAL_ERROR;
	uint32_t delay = 1000;
//	while(HAL_SD_GetCardState(&hsd) != HAL_SD_CARD_TRANSFER){
//		delay--;
//		Delay_us(5);
//		if(!delay){
//			break;
//		}
//	}
//	if(delay == 0){
//		return 0;
//	}
	delay = 100;

	while(HAL_SD_ReadBlocks(&hsd, buf, addr, num, 1000) != HAL_OK){
		delay--;
		Delay_us(5);
		if(!delay){
			break;
		}
	}
	if(delay){
		res = HAL_OK;
	}
	return res;
}

HAL_StatusTypeDef sdio_write(uint8_t* buf, uint32_t addr, uint8_t num){
	HAL_StatusTypeDef res = HAL_ERROR;
	uint32_t delay = 100;
//	while(HAL_SD_GetCardState(&hsd) != HAL_SD_CARD_TRANSFER){
//		delay--;
//		Delay_us(5);
//		if(!delay){
//			break;
//		}
//	}
//	if(delay == 0){
//		return 0;
//	}
//	delay = 100;
	while(delay--){
		if(SDWriteReady){
			SDWriteReady = 0;
			res = HAL_SD_WriteBlocks_DMA(&hsd, buf, addr, num);
			if(res == HAL_OK){
				return res;
			}
		}
	}
	return res;
//	while(HAL_SD_WriteBlocks(&hsd, buf, addr, num, 1000) != HAL_OK){
//		delay--;
//		Delay_us(5);
//		if(!delay){
//			break;
//		}
//	}
//	if(delay == 0){
//		return 0;
//	}
//	else{
//		return 1;
//	}
}

