/*
 * Test that small blocks (< min-block-size) are NOT tracked.
 * With default min-block-size=4096, a 1024-byte block should be ignored.
 */

#include <stdlib.h>

volatile int *g_ptr;

int main(void)
{
    /* Allocate a small block - should NOT be tracked */
    size_t size = 1024;  /* Less than PAGE_SIZE */
    volatile int *arr = (volatile int *)malloc(size);

    if (!arr) return 1;

    g_ptr = arr;

    /* These stores should NOT appear in the log */
    arr[0] = 0x11111111;
    arr[1] = 0x22222222;
    arr[2] = 0x33333333;

    free((void *)arr);

    return 0;
}
