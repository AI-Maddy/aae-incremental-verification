#ifndef CONFIG_H
#define CONFIG_H
#include <stdint.h>
#define SENSOR_MIN   (-1000)
#define SENSOR_MAX   1000
#define CMD_MAX      100
#define GAIN_K       4
#define ACT_MAX      400
#define RATE_STEP    20
#define MODE_OFF     0
#define MODE_RUN     1
#define MODE_SAFE    2
#define NSAMP        4
#define RING_N       8
typedef struct { int32_t data[RING_N]; uint32_t idx; } ring_t;
#endif
