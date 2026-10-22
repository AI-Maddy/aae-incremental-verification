#include "config.h"

int32_t filter_avg(const int32_t *s)
__CPROVER_requires(__CPROVER_is_fresh(s, NSAMP * sizeof(int32_t)))
__CPROVER_requires(__CPROVER_forall { int k; (0 <= k && k < NSAMP) ==> (SENSOR_MIN <= s[k] && s[k] <= SENSOR_MAX) })
__CPROVER_assigns()
__CPROVER_ensures(SENSOR_MIN <= __CPROVER_return_value && __CPROVER_return_value <= SENSOR_MAX)
{
  int32_t acc = 0;
  for (int i = 0; i < NSAMP; i++)
  __CPROVER_loop_invariant(0 <= i && i <= NSAMP && i * SENSOR_MIN <= acc && acc <= i * SENSOR_MAX)
  {
    acc += s[i];
  }
  return acc / NSAMP;
}

int32_t clamp_cmd(int32_t raw)
__CPROVER_assigns()
__CPROVER_ensures(0 <= __CPROVER_return_value && __CPROVER_return_value <= CMD_MAX)
{
  if (raw < 0) return 0;
  if (raw > CMD_MAX) return CMD_MAX;
  return raw;
}

int32_t gain(int32_t cmd)
__CPROVER_requires(0 <= cmd && cmd <= CMD_MAX)
__CPROVER_assigns()
__CPROVER_ensures(0 <= __CPROVER_return_value && __CPROVER_return_value <= ACT_MAX)
{
  return GAIN_K * cmd;
}

int32_t rate_limit(int32_t prev, int32_t target)
__CPROVER_requires(0 <= prev && prev <= ACT_MAX && 0 <= target && target <= ACT_MAX)
__CPROVER_assigns()
__CPROVER_ensures(0 <= __CPROVER_return_value && __CPROVER_return_value <= ACT_MAX)
__CPROVER_ensures(__CPROVER_return_value - prev <= RATE_STEP && prev - __CPROVER_return_value <= RATE_STEP)
{
  if (target > prev + RATE_STEP) return prev + RATE_STEP;
  if (target < prev - RATE_STEP) return prev - RATE_STEP;
  return target;
}

int32_t mode_next(int32_t mode, int32_t fault)
__CPROVER_requires(MODE_OFF <= mode && mode <= MODE_SAFE)
__CPROVER_assigns()
__CPROVER_ensures(MODE_OFF <= __CPROVER_return_value && __CPROVER_return_value <= MODE_SAFE)
__CPROVER_ensures((mode == MODE_SAFE || fault != 0) ==> __CPROVER_return_value == MODE_SAFE)
{
  if (mode == MODE_SAFE) return MODE_SAFE;
  if (fault != 0) return MODE_SAFE;
  return MODE_RUN;
}

int32_t actuator_cmd(int32_t mode, int32_t value)
__CPROVER_requires(MODE_OFF <= mode && mode <= MODE_SAFE && 0 <= value && value <= ACT_MAX)
__CPROVER_assigns()
__CPROVER_ensures(0 <= __CPROVER_return_value && __CPROVER_return_value <= ACT_MAX)
__CPROVER_ensures(mode != MODE_RUN ==> __CPROVER_return_value == 0)
__CPROVER_ensures(mode == MODE_RUN ==> __CPROVER_return_value == value)
{
  if (mode != MODE_RUN) return 0;
  return value;
}

void ring_push(ring_t *r, int32_t v)
__CPROVER_requires(__CPROVER_is_fresh(r, sizeof(ring_t)) && r->idx < RING_N)
__CPROVER_assigns(r->idx, r->data)
__CPROVER_ensures(r->idx < RING_N)
{
  r->data[r->idx] = v;
  r->idx = (r->idx + 1) % RING_N;
}

int32_t control_step(const int32_t *s, int32_t prev, int32_t *mode, int32_t fault, ring_t *log)
__CPROVER_requires(__CPROVER_is_fresh(s, NSAMP * sizeof(int32_t)))
__CPROVER_requires(__CPROVER_forall { int k; (0 <= k && k < NSAMP) ==> (SENSOR_MIN <= s[k] && s[k] <= SENSOR_MAX) })
__CPROVER_requires(0 <= prev && prev <= ACT_MAX)
__CPROVER_requires(__CPROVER_is_fresh(mode, sizeof(int32_t)) && MODE_OFF <= *mode && *mode <= MODE_SAFE)
__CPROVER_requires(__CPROVER_is_fresh(log, sizeof(ring_t)) && log->idx < RING_N)
__CPROVER_assigns(*mode, log->idx, log->data)
__CPROVER_ensures(0 <= __CPROVER_return_value && __CPROVER_return_value <= 400)
__CPROVER_ensures((*mode == 2 || fault != 0) ==> __CPROVER_return_value == 0)
__CPROVER_ensures(__CPROVER_old(*mode) == 2 ==> *mode == 2)
__CPROVER_ensures(*mode == 1 ==> (__CPROVER_return_value - prev <= 20 && prev - __CPROVER_return_value <= 20))
__CPROVER_ensures(log->idx < RING_N)
{
  int32_t avg = filter_avg(s);
  int32_t c = clamp_cmd(avg);
  int32_t g = gain(c);
  int32_t r = rate_limit(prev, g);
  *mode = mode_next(*mode, fault);
  int32_t out = actuator_cmd(*mode, r);
  ring_push(log, out);
  return out;
}
