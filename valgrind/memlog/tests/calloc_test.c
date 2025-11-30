/*
 * Test calloc allocation (zeroed memory).
 * Verifies that calloc-allocated blocks are tracked.
 */

#include <stdlib.h>
#include <stdint.h>

volatile uint64_t *g_ptr;

int main(void)
{
    /* calloc: allocate and zero 1024 elements of 8 bytes each = 8192 bytes */
    volatile uint64_t *arr = (volatile uint64_t *)calloc(1024, sizeof(uint64_t));

    if (!arr) return 1;

    g_ptr = arr;

    /* Write specific values */
    arr[0] = 0xCA110C00000001ULL;
    arr[1] = 0xCA110C00000002ULL;
    arr[2] = 0xCA110C00000003ULL;

    free((void *)arr);

    return 0;
}
