/* Test AVX 256-bit stores to malloc'd memory */
#include <stdio.h>
#include <stdlib.h>
#include <immintrin.h>

int main(void)
{
    int qty = 100;

    /* Allocate memory - malloc doesn't guarantee 32-byte alignment */
    __m256i *ptr = (__m256i *)malloc(qty * sizeof(__m256i));
    if (!ptr) {
        fprintf(stderr, "malloc failed\n");
        return 1;
    }

    /* Create a 256-bit value */
    __m256i value = _mm256_set_epi64x(0xDEADBEEFDEADBEEF, 0x0123456789ABCDEF,
                                       0xFEDCBA9876543210, 0xAABBCCDDEEFF0011);

    /* Store using aligned store - requires 32-byte alignment */
    for (int i = 0; i < qty; i++) {
        _mm256_store_si256(ptr + i, value);
    }

    free(ptr);
    return 0;
}
