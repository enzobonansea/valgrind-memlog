/*
 * Test tracking of stack-allocated arrays.
 * Uses client requests to manually track a stack array.
 *
 * This verifies that memlog can track any memory region,
 * not just heap allocations.
 *
 * Expected stores (IEEE 754 single precision):
 *   100.0f = 0x42c80000
 *   200.0f = 0x43480000
 *   300.0f = 0x43960000
 *   400.0f = 0x43c80000
 *   500.0f = 0x43fa0000
 */

#include <stdio.h>
#include "../memlog.h"

/* Prevent optimization */
volatile float g_sum;

int main(void)
{
    /* Stack-allocated array */
    volatile float stack_arr[2048];  /* 8KB on stack */

    /* Print base address for verification */
    fprintf(stderr, "STACK_BASE: %p\n", (void*)stack_arr);

    /* Tell memlog to track this stack region */
    MEMLOG_TRACK_BLOCK(stack_arr, sizeof(stack_arr));

    /* Write specific known values at various offsets */
    stack_arr[0]    = 100.0f;   /* 0x42c80000 */
    stack_arr[100]  = 200.0f;   /* 0x43480000 */
    stack_arr[500]  = 300.0f;   /* 0x43960000 */
    stack_arr[1000] = 400.0f;   /* 0x43c80000 */
    stack_arr[2000] = 500.0f;   /* 0x43fa0000 */

    /* Read back to prevent optimization */
    g_sum = stack_arr[0] + stack_arr[100] + stack_arr[500] +
            stack_arr[1000] + stack_arr[2000];

    /* Stop tracking before leaving scope */
    MEMLOG_UNTRACK_BLOCK(stack_arr);

    return 0;
}
