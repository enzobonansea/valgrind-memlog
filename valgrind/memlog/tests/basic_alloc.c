/*
 * Basic test for memlog tool.
 * Allocates a large block (> PAGE_SIZE) and writes specific known values.
 * Memlog should log these exact store values.
 *
 * Expected stores (as hex representation of floats):
 *   0.6f  = 0x3f19999a (IEEE 754 single precision)
 *   1.5f  = 0x3fc00000
 *   42.0f = 0x42280000
 */

#include <stdlib.h>
#include <stdint.h>

/* Prevent compiler from optimizing away stores */
volatile float *g_ptr;

int main(void)
{
    /* Allocate a block larger than PAGE_SIZE (4096) */
    size_t size = 8192;
    volatile float *arr = (volatile float *)malloc(size);

    if (!arr) {
        return 1;
    }

    g_ptr = arr;

    /* Write specific known float values that we can verify in the log */
    arr[0] = 0.6f;    /* 0x3f19999a */
    arr[1] = 1.5f;    /* 0x3fc00000 */
    arr[2] = 42.0f;   /* 0x42280000 */
    arr[3] = -1.0f;   /* 0xbf800000 */
    arr[4] = 3.14159f; /* 0x40490fd0 (approx) */

    /* Read back to prevent optimization */
    volatile float sum = arr[0] + arr[1] + arr[2] + arr[3] + arr[4];
    (void)sum;

    free((void *)arr);

    return 0;
}
