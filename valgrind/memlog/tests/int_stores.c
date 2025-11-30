/*
 * Test integer stores of various sizes.
 * Verifies that int32 and int64 values are logged correctly.
 */

#include <stdlib.h>
#include <stdint.h>

volatile void *g_ptr;

int main(void)
{
    size_t size = 8192;

    /* Test 32-bit integers */
    volatile int32_t *arr32 = (volatile int32_t *)malloc(size);
    if (!arr32) return 1;
    g_ptr = arr32;

    arr32[0] = 0x12345678;
    arr32[1] = 0xDEADBEEF;
    arr32[2] = 0xCAFEBABE;
    arr32[3] = -1;  /* 0xFFFFFFFF */

    free((void *)arr32);

    /* Test 64-bit integers */
    volatile int64_t *arr64 = (volatile int64_t *)malloc(size);
    if (!arr64) return 1;
    g_ptr = arr64;

    arr64[0] = 0x123456789ABCDEF0LL;
    arr64[1] = 0xDEADBEEFCAFEBABELL;
    arr64[2] = -1LL;  /* 0xFFFFFFFFFFFFFFFF */

    free((void *)arr64);

    return 0;
}
