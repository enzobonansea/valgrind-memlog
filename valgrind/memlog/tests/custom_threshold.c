/*
 * Test custom --min-block-size threshold.
 * Uses a smaller threshold (512) so smaller blocks are tracked.
 */

#include <stdlib.h>
#include <stdint.h>

volatile uint64_t *g_ptr;

int main(void)
{
    /* With --min-block-size=512, this 1024-byte block should be tracked */
    size_t size = 1024;
    volatile uint64_t *arr = (volatile uint64_t *)malloc(size);

    if (!arr) return 1;

    g_ptr = arr;

    arr[0] = 0x1234567890ABCDEFULL;
    arr[1] = 0xFEDCBA0987654321ULL;

    free((void *)arr);

    return 0;
}
