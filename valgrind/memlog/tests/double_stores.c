/*
 * Test double (64-bit float) stores.
 * Verifies that double values are logged with correct bit representation.
 *
 * Expected stores (IEEE 754 double precision):
 *   0.6   = 0x3fe3333333333333
 *   1.5   = 0x3ff8000000000000
 *   42.0  = 0x4045000000000000
 *   -1.0  = 0xbff0000000000000
 */

#include <stdlib.h>

volatile double *g_ptr;

int main(void)
{
    size_t size = 8192;
    volatile double *arr = (volatile double *)malloc(size);

    if (!arr) return 1;

    g_ptr = arr;

    arr[0] = 0.6;
    arr[1] = 1.5;
    arr[2] = 42.0;
    arr[3] = -1.0;

    volatile double sum = arr[0] + arr[1] + arr[2] + arr[3];
    (void)sum;

    free((void *)arr);
    return 0;
}
