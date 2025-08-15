/**********************************************************************
Copyright ? LIZ MEDICAL TECHNOLOGY Co., Ltd. 2022. All rights reserved.
�ļ���		: key.h
����	  	: л����<823767544@qq.com>
�汾	   	: V1.1
����	   	: ��������ͷ�ļ�
����	   	: ��
��־	   	: ����V1.0 2024/8/10 л���Ĵ���
***********************************************************************/
#ifndef __KEY__H
#define __KEY__H

#include "main.h"
#include "utils.h"
#include "stdio.h"

#define KEY_Up  1         //��������
#define KEY_DownShake  2  //���¶���
#define KEY_Down  3       //��������
#define KEY_wait  4       //�ȴ�״̬

#define NON_KEY 0
#define SHORT_KEY 1       //�̰�����
#define LONG_KEY 2        //��������
#define DOUBLE_CLICK 3    //˫������

#define FALSE 0
#define TRUE 1  


extern uint8_t key_return;

/**
  * @brief  KEY_Scan();// �������
  * @note   ������⣬���ص�����˫��������
  * @param  1�������£�0�����ɿ�
  * @retval ��
	PS:key_return�����ⲿȫ�ֱ��������ڽ��ܷ�����Ϣ
  */	
uint8_t KEY_Scan(void);
#endif
