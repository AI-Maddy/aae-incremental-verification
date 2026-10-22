/* Independent random/boundary test oracle, native build with UBSan. */
#include <stdio.h>
#include <stdlib.h>
#include "config.h"
int32_t control_step(const int32_t*,int32_t,int32_t*,int32_t,ring_t*);
static int32_t pick(int32_t lo, int32_t hi) {
  int r = rand() % 8;
  if (r == 0) return lo; if (r == 1) return hi; if (r == 2) return lo + 1; if (r == 3) return hi - 1;
  return lo + (int32_t)(((int64_t)rand() * 7919 + rand()) % ((int64_t)hi - lo + 1));
}
int main(void) {
  srand(12345);
  for (long n = 0; n < 200000; n++) {
    int32_t s[4]; for (int k = 0; k < 4; k++) s[k] = pick(-1000, 1000);
    int32_t prev = pick(0, 400), mode = pick(0, 2), m0 = mode;
    int32_t fault = (rand() % 4 == 0) ? pick(-5, 5) : 0;
    ring_t log = {{0}, (uint32_t)pick(0, 7)};
    int32_t out = control_step(s, prev, &mode, fault, &log);
    int ok = 0 <= out && out <= 400 && (!(mode == 2 || fault != 0) || out == 0) && (m0 != 2 || mode == 2)
      && (mode != 1 || (out - prev <= 20 && prev - out <= 20)) && 0 <= mode && mode <= 2 && log.idx < 8;
    if (!ok) { printf("VIOLATION n=%ld out=%d prev=%d m0=%d mode=%d fault=%d\n", n, out, prev, m0, mode, fault); return 1; }
  }
  printf("PASS\n"); return 0;
}
