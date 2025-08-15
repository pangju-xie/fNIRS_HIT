#ifndef _LED_H
#define _LED_H

#include "driver/gpio.h"

#define LED_R  (GPIO_NUM_21)
#define LED_G  (GPIO_NUM_22)
#define LED_B  (GPIO_NUM_19)

#define KEY_PIN             (GPIO_NUM_0)

#define SETLEDR(X)                gpio_set_level(LED_R, X)
#define SETLEDG(X)                gpio_set_level(LED_G, X)
#define SETLEDB(X)                gpio_set_level(LED_B, X)

void led_init(void);
void led_set(char chr);
void led_toggle(void);

void Key_init(void);


#endif
