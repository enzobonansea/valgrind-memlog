/*
 * Basic test for memlog tool.
 * Allocates a large block (> PAGE_SIZE) and writes to it.
 * Memlog should track these stores.
 */

#include <stdlib.h>
#include <string.h>

int main(void)
{
    /* Allocate a block larger than PAGE_SIZE (4096) */
    size_t size = 8192;
    double *arr = (double *)malloc(size);

    if (!arr) {
        return 1;
    }

    /* Write some values to the array */
    for (int i = 0; i < (int)(size / sizeof(double)); i++) {
        arr[i] = (double)i * 1.5;
    }

    /* Sum the values to prevent optimization */
    double sum = 0.0;
    for (int i = 0; i < (int)(size / sizeof(double)); i++) {
        sum += arr[i];
    }

    free(arr);

    return (sum > 0.0) ? 0 : 1;
}
