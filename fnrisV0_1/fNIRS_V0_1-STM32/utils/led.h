#ifndef __LED__H
#define __LED__H

#include "stdio.h"
#include "gpio.h"
#include "main.h"

#define LEDON  			GPIO_PIN_SET
#define LEDOFF 			GPIO_PIN_RESET

#define SETLEDR(x)							HAL_GPIO_WritePin(LEDR_GPIO_Port, LEDR_Pin, x)
#define SETLEDG(x)							HAL_GPIO_WritePin(LEDG_GPIO_Port, LEDG_Pin, x)
#define SETLEDB(x)							HAL_GPIO_WritePin(LEDB_GPIO_Port, LEDB_Pin, x)


#define ReadKey()								HAL_GPIO_ReadPin(POW_KEY_GPIO_Port, POW_KEY_Pin)
#define SetKey(x)   						HAL_GPIO_WritePin(POW_CTRL_GPIO_Port, POW_CTRL_Pin, x)

void SetLED(char chr);
void SwitchLED(void);
uint8_t SwitchOn(uint16_t DelayTime);
uint8_t SwitchOff(uint16_t DelayTime);

#endif
