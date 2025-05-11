#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/gpio.h"
#include "hardware/adc.h"
#include "hardware/timer.h"
#include "hardware/irq.h"

#define LED_PIN 25 // Built-in LED pin on Raspberry Pi Pico
#define LO_PLUS 12
#define LO_MINUS 13
#define ADC_PIN 28
#define ADC_INPUT 2

#define SAMPLING_INTERVAL_MS 4 // 250 Hz

bool timer_callback(repeating_timer_t *rt) {
    gpio_put(LED_PIN, !gpio_get(LED_PIN));
    
    int16_t adc_value = -1;
    bool leads_connected = true;
    if (gpio_get(LO_PLUS) || gpio_get(LO_MINUS)) {
        leads_connected = false;
    }
    
    if (leads_connected) {
        adc_value = adc_read();
    }
    printf("%d\n", adc_value);

    return true;
}

int main() {
    stdio_init_all();
    
    sleep_ms(2000);
    printf("ECG Sampling Application Started\n");
    printf("Sampling interval: %d ms\n", SAMPLING_INTERVAL_MS);
    
    // Initialize GPIO pins
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);
    
    gpio_init(LO_PLUS);
    gpio_pull_down(LO_PLUS);
    gpio_set_dir(LO_PLUS, GPIO_IN);
    
    gpio_init(LO_MINUS);
    gpio_pull_down(LO_MINUS);
    gpio_set_dir(LO_MINUS, GPIO_IN);
    
    // Initialize ADC
    adc_init();
    adc_gpio_init(ADC_PIN);
    adc_select_input(ADC_INPUT);
    
    // Initialize and start timer with configured sampling interval
    repeating_timer_t timer;
    add_repeating_timer_ms(-SAMPLING_INTERVAL_MS, timer_callback, NULL, &timer);
    
    // Main loop
    while (1) {
        // Sleep to prevent busy-waiting
        sleep_ms(100);
        
    }
    
    return 0;
}