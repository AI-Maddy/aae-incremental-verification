/* Independent system-level oracle: whole program, no contracts, fixed requirement literals R1-R5. */
#include "config.h"
int32_t control_step(const int32_t*,int32_t,int32_t*,int32_t,ring_t*);
int32_t nondet_i32(void); uint32_t nondet_u32(void);
int main(void) {
  int32_t s[4]; for (int k = 0; k < 4; k++) { s[k] = nondet_i32(); __CPROVER_assume(-1000 <= s[k] && s[k] <= 1000); }
  int32_t prev = nondet_i32(); __CPROVER_assume(0 <= prev && prev <= 400);
  int32_t mode = nondet_i32(); __CPROVER_assume(0 <= mode && mode <= 2);
  int32_t m0 = mode; int32_t fault = nondet_i32();
  ring_t log; log.idx = nondet_u32(); __CPROVER_assume(log.idx < 8);
  int32_t out = control_step(s, prev, &mode, fault, &log);
  __CPROVER_assert(0 <= out && out <= 400, "R1 actuator range");
  __CPROVER_assert(!(mode == 2 || fault != 0) || out == 0, "R2 safe/fault => zero output");
  __CPROVER_assert(m0 != 2 || mode == 2, "R3 SAFE latches");
  __CPROVER_assert(mode != 1 || (out - prev <= 20 && prev - out <= 20), "R4 rate limit in RUN");
  __CPROVER_assert(0 <= mode && mode <= 2, "R5 valid mode");
  __CPROVER_assert(log.idx < 8, "R5 log index");
  return 0;
}
