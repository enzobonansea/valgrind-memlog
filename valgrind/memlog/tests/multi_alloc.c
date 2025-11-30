/*
 * Test multiple allocations.
 * Verifies that stores to different tracked blocks are logged correctly.
 */

#include <stdlib.h>
#include <stdint.h>

volatile void *g_ptr1, *g_ptr2;

int main(void)
{
    size_t size = 8192;

    /* First allocation */
    volatile uint64_t *arr1 = (volatile uint64_t *)malloc(size);
    if (!arr1) return 1;
    g_ptr1 = arr1;

    arr1[0] = 0xAAAAAAAAAAAAAAAAULL;
    arr1[1] = 0xBBBBBBBBBBBBBBBBULL;

    /* Second allocation */
    volatile uint64_t *arr2 = (volatile uint64_t *)malloc(size);
    if (!arr2) return 1;
    g_ptr2 = arr2;

    arr2[0] = 0xCCCCCCCCCCCCCCCCULL;
    arr2[1] = 0xDDDDDDDDDDDDDDDDULL;

    /* Write more to first block */
    arr1[2] = 0xEEEEEEEEEEEEEEEEULL;

    free((void *)arr1);
    free((void *)arr2);

    return 0;
}
