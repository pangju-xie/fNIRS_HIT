#include "main.h"
#include "led.h"
#include "gpio.h"
#include "key.h"

static char cur_chr = 'o';
static char pre_chr = 'o';


void SetLED(char chr){
	switch(chr){
		case 'r':
		case 'R':
			cur_chr = 'r';
			SETLEDR(LEDON);
			SETLEDG(LEDOFF);
			SETLEDB(LEDOFF);
			break;
		case 'g':
		case 'G':
			cur_chr = 'g';
			SETLEDR(LEDOFF);
			SETLEDG(LEDON);
			SETLEDB(LEDOFF);
			break;
		case 'b':
		case 'B':
			cur_chr = 'b';
			SETLEDR(LEDOFF);
			SETLEDG(LEDOFF);
			SETLEDB(LEDON);
			break;
		case 'y':
		case 'Y':
			cur_chr = 'y';
			SETLEDR(LEDON);
			SETLEDG(LEDON);
			SETLEDB(LEDOFF);
			break;
		case 'c':
		case 'C':
			cur_chr = 'c';
			SETLEDR(LEDOFF);
			SETLEDG(LEDON);
			SETLEDB(LEDON);
			break;
		case 'p':
		case 'P':
			cur_chr = 'p';
			SETLEDR(LEDON);
			SETLEDG(LEDOFF);
			SETLEDB(LEDON);
			break;
		case 'w':
		case 'W':
			cur_chr = 'w';
			SETLEDR(LEDON);
			SETLEDG(LEDON);
			SETLEDB(LEDON);
			break;
		case 'o':
		case 'O':
			cur_chr = 'o';
			SETLEDR(LEDOFF);
			SETLEDG(LEDOFF);
			SETLEDB(LEDOFF);
			break;
		default:
			cur_chr = 'o';
			SETLEDR(LEDOFF);
			SETLEDG(LEDOFF);
			SETLEDB(LEDOFF);
			break;
	}
}

void SwitchLED(void){
	if(cur_chr!= 'o'){
		pre_chr = cur_chr;
		SetLED('o');
	}
	else{
		if(pre_chr=='o'){
			pre_chr = 'w';		//Ä¬ÈÏ°×¹â
		}
		SetLED(pre_chr);
	}
	
}

uint8_t SwitchOn(uint16_t DelayTime){
	uint16_t delay = 0;
	while(1){
		if(ReadKey()==0){
			delay++;
			HAL_Delay(1);
			if(delay > DelayTime){
				SetLED('g');
				SetKey(LEDON);
				return 1;
			}
		}else{
			return 0;	
		}
	}
}
uint8_t SwitchOff(uint16_t DelayTime){
	uint16_t delay = 0;
	while(1){
		if(ReadKey()==0){
			delay++;
			HAL_Delay(1);
			if(delay > DelayTime){
				SetLED('o');
				SetKey(LEDOFF);
				return 1;
			}
		}else{
			return 0;	
		}
	}
}


