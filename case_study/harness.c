#include "config.h"
int32_t filter_avg(const int32_t *s); int32_t clamp_cmd(int32_t); int32_t gain(int32_t);
int32_t rate_limit(int32_t,int32_t); int32_t mode_next(int32_t,int32_t); int32_t actuator_cmd(int32_t,int32_t);
void ring_push(ring_t*,int32_t); int32_t control_step(const int32_t*,int32_t,int32_t*,int32_t,ring_t*);
void h_filter_avg(void){ const int32_t *s; filter_avg(s); }
void h_clamp_cmd(void){ int32_t a; clamp_cmd(a); }
void h_gain(void){ int32_t a; gain(a); }
void h_rate_limit(void){ int32_t a,b; rate_limit(a,b); }
void h_mode_next(void){ int32_t a,b; mode_next(a,b); }
void h_actuator_cmd(void){ int32_t a,b; actuator_cmd(a,b); }
void h_ring_push(void){ ring_t *r; int32_t v; ring_push(r,v); }
void h_control_step(void){ const int32_t *s; int32_t p; int32_t *m; int32_t f; ring_t *l; control_step(s,p,m,f,l); }
