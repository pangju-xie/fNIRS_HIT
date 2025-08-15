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

//��ȡADS1258��������жϺ���
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
	nirs_data_collect(GPIO_Pin);
}


/*************************************************
 * @description				:	�������ݲɼ�
 * @param - gpio_pin	:	���ź�
 * @return 						:	��
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
	g_fnirs_ctx.state = INIT;														//״̬����ʼ��״̬
	g_fnirs_ctx.sample_rate = 10;												//�����ʣ�Ĭ��10hz
	
	//fnirs����Ĭ�ϳ�ʼ����18��Դ��16̽������ȫ��
	g_fnirs_ctx.config.source = 18;											
	g_fnirs_ctx.config.detect = 16;
	memset(g_fnirs_ctx.config.config, 0xFF, sizeof(uint16_t)*g_fnirs_ctx.config.source);
	memset(g_fnirs_ctx.config.open, 16, sizeof(uint8_t)*g_fnirs_ctx.config.source);
	for(uint8_t i = 0; i<g_fnirs_ctx.config.source;i++){
		g_fnirs_ctx.config.open_count[i+1] = g_fnirs_ctx.config.open[i]+g_fnirs_ctx.config.open_count[i];
	}
	
	//fnirs���ͻ����ʼ��
	g_fnirs_ctx.databuf.period = 0;											//����ţ���ʼ��Ϊ0
	g_fnirs_ctx.databuf.datalen = g_fnirs_ctx.config.source * g_fnirs_ctx.config.detect*LEN_ONE_SOURCE+4;
	g_fnirs_ctx.databuf.length = g_fnirs_ctx.databuf.datalen+FRAME_LEN;
	InitDataBuf(g_fnirs_ctx.databuf.send_buf[0].chn_data, fNIRS, CMD_DATA, g_fnirs_ctx.databuf.datalen);
	InitDataBuf(g_fnirs_ctx.databuf.send_buf[1].chn_data, fNIRS, CMD_DATA, g_fnirs_ctx.databuf.datalen);
}

/*************************************************
 * @description			:	�����ɼ����ܳ�ʼ��
 * @param 				:	��
 * @return 				:	��
**************************************************/
void nirs_init(void){
	
	LED_Init();																					//��ʼ��IS31FLоƬ
	ads1258init();																			//��ʼ��ads1258оƬ
	DataFrameInit();																		//��ʼ��ָ��֡���ݽṹ
//	fnirs_struct_init();																//��ʼ��fnirs���ݽṹ
	DebugPrintf("fnirs init done.\r\n");
}

/*************************************************
 * @description			:	�������ò�����
 * @param 			 spr:	������
 * @return 				:	��
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
 * @description			:	������������ṹ
 * @param 			 data:	���ýṹ����
 * @return 				:	��
**************************************************/
uint8_t nirs_config(uint8_t* data,uint8_t len){
	memset(&g_fnirs_ctx.config, 0, sizeof(g_fnirs_ctx.config));
	g_fnirs_ctx.config.source = data[0];				//��Դ��
	g_fnirs_ctx.config.detect = data[1];				//̽������
	for(uint8_t i = 0; i<g_fnirs_ctx.config.source;i++){
		for(uint8_t j = 0; j<len;j++){				//����̽��������ʱ��
			g_fnirs_ctx.config.config[i] = g_fnirs_ctx.config.config[i]<<8;
			g_fnirs_ctx.config.config[i] |= data[i*len+2+j];
		}
		for(uint8_t j = 0;j<g_fnirs_ctx.config.detect;j++){
			//ͳ�Ƶ�����Դ�¿���̽��������
			g_fnirs_ctx.config.open[i] += GetBit(g_fnirs_ctx.config.config[i], j);	
		}
		//ͳ��̽���������ۼӴ���
		g_fnirs_ctx.config.open_count[i+1] = g_fnirs_ctx.config.open[i]+g_fnirs_ctx.config.open_count[i];
	}

	g_fnirs_ctx.databuf.datalen = g_fnirs_ctx.config.open_count[g_fnirs_ctx.config.source]*6+4;			//ͳ����Ч����֡����
	g_fnirs_ctx.databuf.length = g_fnirs_ctx.databuf.datalen+FRAME_LEN;															//ͳ������֡����
	g_fnirs_ctx.state = READY;									//�л�fnirs״̬ΪԤ��̬
	
	InitDataBuf(g_fnirs_ctx.databuf.send_buf[0].chn_data, fNIRS, CMD_DATA, g_fnirs_ctx.databuf.datalen);
	InitDataBuf(g_fnirs_ctx.databuf.send_buf[1].chn_data, fNIRS, CMD_DATA, g_fnirs_ctx.databuf.datalen);
	
	//sd card �ṹ���ʼ��
	g_fnirs_ctx.databuf.sd_buff.sd_baise = 0;
	g_fnirs_ctx.databuf.sd_buff.idx = 0;
	g_fnirs_ctx.databuf.sd_buff.batchnum = BLOCKSIZE/g_fnirs_ctx.databuf.length;
	g_fnirs_ctx.databuf.sd_buff.blocknum = 1;

	g_fnirs_ctx.databuf.sd_buff.bufsize = g_fnirs_ctx.databuf.sd_buff.blocknum * BLOCKSIZE;
	
	
	return 1;
}

/*************************************************
 * @description			:	�����ɼ����ܿ���
 * @param 				:	��
 * @return 				:	��
**************************************************/
uint8_t nirs_start(void){
	DebugPrintf("_____fnirs start_______\r\n");
	g_fnirs_ctx.state = START;													//�л�fnirs״̬
	g_fnirs_ctx.tim_count = g_fnirs_ctx.config.source*2;//ͳ�ƶ�ʱ����������
	__HAL_TIM_SetCounter(&fNIRS_TIM, 0);								//��0��ʱ��������
	HAL_TIM_Base_Start_IT(&fNIRS_TIM);								
  g_fnirs_ctx.databuf.idx = 0;
  g_fnirs_ctx.databuf.SaveAddr = g_fnirs_ctx.databuf.send_buf[g_fnirs_ctx.databuf.idx].chn_data + DATA_PLACE;
	//g_fnirs_ctx.databuf.buffer.idx = 1;									//�ȱ����ڵ�һ��������
	return 1;
}

/*************************************************
 * @description			:	�����ɼ����ܹر�
 * @param 				:	��
 * @return 				:	��
**************************************************/
uint8_t nirs_stop(void){
	g_fnirs_ctx.state = STOP;													//�л�fnirs״̬
	SetLED_ALL(0);																		//�ر�led�͹�����
	stopConversions();
	HAL_TIM_Base_Stop_IT(&fNIRS_TIM);
	DebugPrintf("_______fnirs stop__________\r\n");
	return 1;
}

/*************************************************
 * @description			:	��ȡ��������״̬
 * @param - 			:	��
 * @return 				:	��
**************************************************/
uint8_t nirs_get_state(void){
	return g_fnirs_ctx.state;
}

uint16_t nirs_get_len(void){
	return g_fnirs_ctx.databuf.length;
}

/*************************************************
 * @description			:	���ݱ���ʹ��亯��
 * @param 				:	��
 * @return 				:	��
**************************************************/
void nirs_data_send(uint8_t* srcbuf){
  		//SD_CARD_STRUCT sdcard = g_fnirs_ctx.databuf.sd_buff;
  SwitchLED();				//LED����˸
  //�������
  *(uint32_t*)(srcbuf+g_fnirs_ctx.databuf.length-6) = ENDIAN_SWAP_32B(g_fnirs_ctx.databuf.period);
  
  //����У����
  uint16_t crc = CRC16Calculate(srcbuf, g_fnirs_ctx.databuf.length-2);
  *(uint16_t*)(srcbuf+g_fnirs_ctx.databuf.length-2) = ENDIAN_SWAP_16B(crc);
  
  //SPI��DMA����
  SPITransmitDMA(srcbuf, g_fnirs_ctx.databuf.length, 1000);
  
  //д��sd��
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
 * @description			:	��ʱ������
 * @param 				:	��
 * @return 				:	��
**************************************************/
void nirs_timer_handle(void){
	if(g_fnirs_ctx.state != START){
		return ;
	}
	uint8_t s1 = g_fnirs_ctx.tim_count/2;				
	uint8_t d1 = g_fnirs_ctx.tim_count%2;
	uint8_t idx1 = s1%g_fnirs_ctx.config.source;			//�ڼ��鿪����LED
	uint8_t *srcbuf = g_fnirs_ctx.databuf.send_buf[g_fnirs_ctx.databuf.idx].chn_data;
	uint16_t setchn = g_fnirs_ctx.config.config[idx1];

	if(d1 == 0){
		//�ر���һ��LED��IR�⣬��������LED��RED��
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
		//�رո�LED��RED�⣬��������LED��IR��
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
	
	buf = buf + baise * g_fnirs_ctx.databuf.length +1; //δ֪���⣬���������λƫ��һ���ֽ�
	buf[CMD_PLACE] = CMD_SUPP;
	uint16_t crc = CRC16Calculate(buf, g_fnirs_ctx.databuf.length-2);
	*(uint16_t*)(buf+g_fnirs_ctx.databuf.length-2) = ENDIAN_SWAP_16B(crc);
	
	SPITransmitDMA(buf, g_fnirs_ctx.databuf.length, 100);

}
