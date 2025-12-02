/*
 * Test random offset accesses within a tracked block.
 * Verifies that stores at arbitrary positions within the block
 * are all captured regardless of access pattern.
 *
 * This test writes to 7 random offsets (within bounds) and
 * verifies that all stores are logged with correct addresses and values.
 */

#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>

volatile void *g_ptr;

int main(void)
{
    size_t size = 16384;  /* 16KB block */
    volatile float *arr = (volatile float *)malloc(size);

    if (!arr) return 1;
    g_ptr = arr;

    /* Print base address so we can verify offsets in the log */
    fprintf(stderr, "BASE_ADDR: %p\n", (void*)arr);

    /* Write to 7 different random-like offsets (deterministic for test) */
    /* Offsets chosen to be spread across the block */
    arr[17]   = 1.0f;    /* offset 68 bytes   - 0x3f800000 */
    arr[523]  = 2.0f;    /* offset 2092 bytes - 0x40000000 */
    arr[1001] = 3.0f;    /* offset 4004 bytes - 0x40400000 */
    arr[2999] = 4.0f;    /* offset 11996 bytes - 0x40800000 */
    arr[100]  = 5.0f;    /* offset 400 bytes  - 0x40a00000 */
    arr[3500] = 6.0f;    /* offset 14000 bytes - 0x40c00000 */
    arr[7]    = 7.0f;    /* offset 28 bytes   - 0x40e00000 */

    /* Read back to prevent optimization */
    volatile float sum = arr[17] + arr[523] + arr[1001] + arr[2999] +
                         arr[100] + arr[3500] + arr[7];
    (void)sum;

    free((void *)arr);
    return 0;
}
