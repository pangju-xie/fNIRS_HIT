#include "fnirs.h"
#include "main.h"
#include "tim.h"
#include "sdio.h"
#include "ads1258.h"
#include "is31fl.h"
#include "utils.h"
#include <string.h>
#include <stdlib.h>
#include "transmit.h"
#include "led.h"
#include <math.h>


FNIRS_STRUCT g_fnirs_ctx;
float read_ads_value = 0.0f;

//读取ADS1258光电数据中断函数
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
	nirs_data_collect(GPIO_Pin);
}


/*************************************************
 * @description				:	脑氧数据采集
 * @param - gpio_pin	:	引脚号
 * @return 						:	无
**************************************************/
void nirs_data_collect(uint16_t GPIO_Pin){
	if(GPIO_Pin == NIRS_DRDY_Pin){
		if(!ReadNIRS()){
      read_ads_value = ReadDataDirect(g_fnirs_ctx.databuf.SaveAddr);
      g_fnirs_ctx.databuf.SaveAddr+=3;
			//read_ads_value = ReadDataDirect(g_fnirs_ctx.databuf.buffer.buf[g_fnirs_ctx.databuf.buffer.idx].readbuf);
    }
		__HAL_GPIO_EXTI_CLEAR_IT(NIRS_DRDY_Pin);
	}
}

void fnirs_struct_init(void){
	memset(&g_fnirs_ctx, 0, sizeof(g_fnirs_ctx));
	g_fnirs_ctx.state = INIT;														//状态，初始化状态
	g_fnirs_ctx.sample_rate = 10;												//采样率，默认10hz
	
	//fnirs配置默认初始化，18光源，16探测器，全开
	g_fnirs_ctx.config.source = 18;											
	g_fnirs_ctx.config.detect = 16;
	memset(g_fnirs_ctx.config.config, 0xFF, sizeof(uint16_t)*g_fnirs_ctx.config.source);
	memset(g_fnirs_ctx.config.open, 16, sizeof(uint8_t)*g_fnirs_ctx.config.source);
	for(uint8_t i = 0; i<g_fnirs_ctx.config.source;i++){
		g_fnirs_ctx.config.open_count[i+1] = g_fnirs_ctx.config.open[i]+g_fnirs_ctx.config.open_count[i];
	}
	
	//fnirs发送缓存初始化
	g_fnirs_ctx.databuf.period = 0;											//包编号，初始化为0
	g_fnirs_ctx.databuf.datalen = g_fnirs_ctx.config.source * g_fnirs_ctx.config.detect*LEN_ONE_SOURCE+4;
	g_fnirs_ctx.databuf.length = g_fnirs_ctx.databuf.datalen+FRAME_LEN;
	InitDataBuf(g_fnirs_ctx.databuf.send_buf[0].chn_data, fNIRS, CMD_DATA, g_fnirs_ctx.databuf.datalen);
	InitDataBuf(g_fnirs_ctx.databuf.send_buf[1].chn_data, fNIRS, CMD_DATA, g_fnirs_ctx.databuf.datalen);
}

/*************************************************
 * @description			:	脑氧采集功能初始化
 * @param 				:	无
 * @return 				:	无
**************************************************/
void nirs_init(void){
	
	LED_Init();																					//初始化IS31FL芯片
	ads1258init();																			//初始化ads1258芯片
	DataFrameInit();																		//初始化指令帧数据结构
//	fnirs_struct_init();																//初始化fnirs数据结构
	DebugPrintf("fnirs init done.\r\n");
}

/*************************************************
 * @description			:	脑氧设置采样率
 * @param 			 spr:	采样率
 * @return 				:	无
**************************************************/
uint8_t nirs_set_sample_rate(uint8_t spr){
	uint8_t ret = 0;
	switch(spr){
		case 1:
			__HAL_TIM_SET_AUTORELOAD(&fNIRS_TIM, 1000-1);
			g_fnirs_ctx.sample_rate = 10;
			ret = 1;
			break;
		case 2:
			__HAL_TIM_SET_AUTORELOAD(&fNIRS_TIM, 500-1);
			g_fnirs_ctx.sample_rate = 20;
			ret = 1;
			break;
		default:
			break;
	}
	return ret;
}

/*************************************************
 * @description			:	脑氧配置网络结构
 * @param 			 data:	配置结构数组
 * @return 				:	无
**************************************************/
uint8_t nirs_config(uint8_t* data,uint8_t len){
	memset(&g_fnirs_ctx.config, 0, sizeof(g_fnirs_ctx.config));
	g_fnirs_ctx.config.source = data[0];				//光源数
	g_fnirs_ctx.config.detect = data[1];				//探测器数
	for(uint8_t i = 0; i<g_fnirs_ctx.config.source;i++){
		for(uint8_t j = 0; j<len;j++){				//配置探测器开启时机
			g_fnirs_ctx.config.config[i] = g_fnirs_ctx.config.config[i]<<8;
			g_fnirs_ctx.config.config[i] |= data[i*len+2+j];
		}
		for(uint8_t j = 0;j<g_fnirs_ctx.config.detect;j++){
			//统计单个光源下开启探测器数量
			g_fnirs_ctx.config.open[i] += GetBit(g_fnirs_ctx.config.config[i], j);	
		}
		//统计探测器开启累加次数
		g_fnirs_ctx.config.open_count[i+1] = g_fnirs_ctx.config.open[i]+g_fnirs_ctx.config.open_count[i];
	}

	g_fnirs_ctx.databuf.datalen = g_fnirs_ctx.config.open_count[g_fnirs_ctx.config.source]*6+4;			//统计有效数据帧长度
	g_fnirs_ctx.databuf.length = g_fnirs_ctx.databuf.datalen+FRAME_LEN;															//统计数据帧长度
	g_fnirs_ctx.state = READY;									//切换fnirs状态为预备态
	
	InitDataBuf(g_fnirs_ctx.databuf.send_buf[0].chn_data, fNIRS, CMD_DATA, g_fnirs_ctx.databuf.datalen);
	InitDataBuf(g_fnirs_ctx.databuf.send_buf[1].chn_data, fNIRS, CMD_DATA, g_fnirs_ctx.databuf.datalen);
	
	//sd card 结构体初始化
	g_fnirs_ctx.databuf.sd_buff.sd_baise = 0;
	g_fnirs_ctx.databuf.sd_buff.idx = 0;
	g_fnirs_ctx.databuf.sd_buff.batchnum = BLOCKSIZE/g_fnirs_ctx.databuf.length;
	g_fnirs_ctx.databuf.sd_buff.blocknum = 1;

	g_fnirs_ctx.databuf.sd_buff.bufsize = g_fnirs_ctx.databuf.sd_buff.blocknum * BLOCKSIZE;
	
	
	return 1;
}

/*************************************************
 * @description			:	脑氧采集功能开启
 * @param 				:	无
 * @return 				:	无
**************************************************/
uint8_t nirs_start(void){
	DebugPrintf("_____fnirs start_______\r\n");
	g_fnirs_ctx.state = START;													//切换fnirs状态
	g_fnirs_ctx.tim_count = g_fnirs_ctx.config.source*2;//统计定时器触发次数
	__HAL_TIM_SetCounter(&fNIRS_TIM, 0);								//清0定时器计数器
	HAL_TIM_Base_Start_IT(&fNIRS_TIM);								
  g_fnirs_ctx.databuf.idx = 0;
  g_fnirs_ctx.databuf.SaveAddr = g_fnirs_ctx.databuf.send_buf[g_fnirs_ctx.databuf.idx].chn_data + DATA_PLACE;
	//g_fnirs_ctx.databuf.buffer.idx = 1;									//先保存在第一缓存数组
	return 1;
}

/*************************************************
 * @description			:	脑氧采集功能关闭
 * @param 				:	无
 * @return 				:	无
**************************************************/
uint8_t nirs_stop(void){
	g_fnirs_ctx.state = STOP;													//切换fnirs状态
	SetLED_ALL(0);																		//关闭led和光电采样
	stopConversions();
	HAL_TIM_Base_Stop_IT(&fNIRS_TIM);
	DebugPrintf("_______fnirs stop__________\r\n");
	return 1;
}

/*************************************************
 * @description			:	获取脑氧功能状态
 * @param - 			:	无
 * @return 				:	无
**************************************************/
uint8_t nirs_get_state(void){
	return g_fnirs_ctx.state;
}

uint16_t nirs_get_len(void){
	return g_fnirs_ctx.databuf.length;
}

/*************************************************
 * @description			:	数据保存和传输函数
 * @param 				:	无
 * @return 				:	无
**************************************************/
void nirs_data_send(uint8_t* srcbuf){
  		//SD_CARD_STRUCT sdcard = g_fnirs_ctx.databuf.sd_buff;
  SwitchLED();				//LED灯闪烁
  //填充包编号
  *(uint32_t*)(srcbuf+g_fnirs_ctx.databuf.length-6) = ENDIAN_SWAP_32B(g_fnirs_ctx.databuf.period);
  
  //计算校验码
  uint16_t crc = CRC16Calculate(srcbuf, g_fnirs_ctx.databuf.length-2);
  *(uint16_t*)(srcbuf+g_fnirs_ctx.databuf.length-2) = ENDIAN_SWAP_16B(crc);
  
  //SPI的DMA发送
  SPITransmitDMA(srcbuf, g_fnirs_ctx.databuf.length, 1000);
  
  //写入sd卡
  uint8_t baise = g_fnirs_ctx.databuf.period % g_fnirs_ctx.databuf.sd_buff.batchnum;
  uint32_t yy = g_fnirs_ctx.databuf.period / g_fnirs_ctx.databuf.sd_buff.batchnum;
  memcpy(g_fnirs_ctx.databuf.sd_buff.txbuf[g_fnirs_ctx.databuf.sd_buff.idx].buf + baise*g_fnirs_ctx.databuf.length, srcbuf, g_fnirs_ctx.databuf.length);
  if(baise == g_fnirs_ctx.databuf.sd_buff.batchnum-1){
    if(!sdio_write(g_fnirs_ctx.databuf.sd_buff.txbuf[g_fnirs_ctx.databuf.sd_buff.idx].buf, g_fnirs_ctx.databuf.sd_buff.sd_baise + yy * g_fnirs_ctx.databuf.sd_buff.blocknum , g_fnirs_ctx.databuf.sd_buff.blocknum)){
      DebugPrintf("write sd card error.\r\n");
    }
    g_fnirs_ctx.databuf.sd_buff.idx = g_fnirs_ctx.databuf.sd_buff.idx==1?0:1;
  }
  
  g_fnirs_ctx.databuf.idx = (g_fnirs_ctx.databuf.idx==1) ? 0:1;
  g_fnirs_ctx.databuf.period++;
  g_fnirs_ctx.databuf.SaveAddr = g_fnirs_ctx.databuf.send_buf[g_fnirs_ctx.databuf.idx].chn_data + DATA_PLACE;
}

/*************************************************
 * @description			:	定时处理函数
 * @param 				:	无
 * @return 				:	无
**************************************************/
void nirs_timer_handle(void){
	if(g_fnirs_ctx.state != START){
		return ;
	}
	uint8_t s1 = g_fnirs_ctx.tim_count/2;				
	uint8_t d1 = g_fnirs_ctx.tim_count%2;
	uint8_t idx1 = s1%g_fnirs_ctx.config.source;			//第几组开启的LED
	uint8_t *srcbuf = g_fnirs_ctx.databuf.send_buf[g_fnirs_ctx.databuf.idx].chn_data;
	uint16_t setchn = g_fnirs_ctx.config.config[idx1];

	if(d1 == 0){
		//关闭上一个LED的IR光，并开启该LED的RED光
		uint8_t idx2 = (s1-1)%g_fnirs_ctx.config.source;
		SwitchDiffLED(idx2, idx1);
		set_ads_channel(&setchn);
		HAL_Delay(1);
		if(g_fnirs_ctx.config.open[idx1] == 1){
			ADS1258_START(HIGH);
			Delay_us(1);
			ADS1258_START(LOW);
		}
		else if(g_fnirs_ctx.config.open[idx1]>1){
			ADS1258_START(HIGH);
		}
	}
	else{
		//关闭该LED的RED光，并开启该LED的IR光
		SwitchSameLED(idx1);
		Delay_us(100);
		if(g_fnirs_ctx.config.open[idx1] == 1){
			ADS1258_START(HIGH);
			Delay_us(1);
			ADS1258_START(LOW);
		}
		else if(g_fnirs_ctx.config.open[idx1]>1){
			ADS1258_START(HIGH);
		}
	}
	
	if((!(g_fnirs_ctx.tim_count%(g_fnirs_ctx.config.source*2))) && (g_fnirs_ctx.tim_count != g_fnirs_ctx.config.source*2) ){
    nirs_data_send(srcbuf);
	}
	g_fnirs_ctx.tim_count++;
}

void sd_read_nirs(uint32_t pkg){
	//SD_CARD_STRUCT *sdcard = &g_fnirs_ctx.databuf.sd_buff;

	uint8_t* buf = g_fnirs_ctx.databuf.sd_buff.txbuf[2].buf;
	uint8_t baise = pkg % g_fnirs_ctx.databuf.sd_buff.batchnum;
	uint32_t yy = pkg / g_fnirs_ctx.databuf.sd_buff.batchnum;
	uint32_t cnt = g_fnirs_ctx.databuf.sd_buff.sd_baise + yy * g_fnirs_ctx.databuf.sd_buff.blocknum;
	
	if(HAL_OK != sdio_read(buf, cnt, g_fnirs_ctx.databuf.sd_buff.blocknum)){
		DebugPrintf("read sd card error.\r\n");
	}
	
	buf = buf + baise * g_fnirs_ctx.databuf.length +1; //未知问题，缓存相对首位偏移一个字节
	buf[CMD_PLACE] = CMD_SUPP;
	uint16_t crc = CRC16Calculate(buf, g_fnirs_ctx.databuf.length-2);
	*(uint16_t*)(buf+g_fnirs_ctx.databuf.length-2) = ENDIAN_SWAP_16B(crc);
	
	SPITransmitDMA(buf, g_fnirs_ctx.databuf.length, 100);

}
