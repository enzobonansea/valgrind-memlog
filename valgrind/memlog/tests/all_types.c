/*
 * Test all basic data types and structures.
 * Verifies that memlog correctly captures stores of:
 *   - int8_t, int16_t, int32_t, int64_t
 *   - float, double
 *   - structs with mixed types
 *
 * This comprehensive test ensures type coverage.
 */

#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>

/* Test structure with mixed types */
typedef struct {
    int32_t  id;        /* offset 0,  4 bytes  - 0x12345678 */
    float    value;     /* offset 4,  4 bytes  - 0x40490fdb (pi) */
    double   precise;   /* offset 8,  8 bytes  - 0x400921fb54442d18 (pi) */
    int64_t  counter;   /* offset 16, 8 bytes  - 0xDEADBEEFCAFEBABE */
} TestStruct;

volatile void *g_ptr;

int main(void)
{
    size_t size = 8192;

    /* Print expected values for reference */
    fprintf(stderr, "Testing all data types\n");

    /*--- Test 8-bit integers ---*/
    volatile int8_t *arr8 = (volatile int8_t *)malloc(size);
    if (!arr8) return 1;
    g_ptr = arr8;
    fprintf(stderr, "int8 base: %p\n", (void*)arr8);

    arr8[0] = 0x7F;     /* max positive */
    arr8[1] = (int8_t)0x80;     /* min negative: -128 */
    arr8[2] = 0x42;     /* 'B' */

    free((void *)arr8);

    /*--- Test 16-bit integers ---*/
    volatile int16_t *arr16 = (volatile int16_t *)malloc(size);
    if (!arr16) return 1;
    g_ptr = arr16;
    fprintf(stderr, "int16 base: %p\n", (void*)arr16);

    arr16[0] = 0x1234;
    arr16[1] = (int16_t)0xABCD;
    arr16[2] = 0x7FFF;  /* max positive */

    free((void *)arr16);

    /*--- Test 32-bit integers ---*/
    volatile int32_t *arr32 = (volatile int32_t *)malloc(size);
    if (!arr32) return 1;
    g_ptr = arr32;
    fprintf(stderr, "int32 base: %p\n", (void*)arr32);

    arr32[0] = 0x12345678;
    arr32[1] = 0xDEADBEEF;
    arr32[2] = 0xCAFEBABE;

    free((void *)arr32);

    /*--- Test 64-bit integers ---*/
    volatile int64_t *arr64 = (volatile int64_t *)malloc(size);
    if (!arr64) return 1;
    g_ptr = arr64;
    fprintf(stderr, "int64 base: %p\n", (void*)arr64);

    arr64[0] = 0x123456789ABCDEF0LL;
    arr64[1] = 0xDEADBEEFCAFEBABELL;

    free((void *)arr64);

    /*--- Test floats ---*/
    volatile float *arrf = (volatile float *)malloc(size);
    if (!arrf) return 1;
    g_ptr = arrf;
    fprintf(stderr, "float base: %p\n", (void*)arrf);

    arrf[0] = 3.14159f;   /* 0x40490fdb */
    arrf[1] = 2.71828f;   /* 0x402df854 */
    arrf[2] = -0.0f;      /* 0x80000000 */
    arrf[3] = 1.0f/0.0f;  /* +inf: 0x7f800000 */

    free((void *)arrf);

    /*--- Test doubles ---*/
    volatile double *arrd = (volatile double *)malloc(size);
    if (!arrd) return 1;
    g_ptr = arrd;
    fprintf(stderr, "double base: %p\n", (void*)arrd);

    arrd[0] = 3.141592653589793;  /* 0x400921fb54442d18 */
    arrd[1] = 2.718281828459045;  /* 0x4005bf0a8b145769 */
    arrd[2] = -0.0;               /* 0x8000000000000000 */

    free((void *)arrd);

    /*--- Test structures ---*/
    volatile TestStruct *structs = (volatile TestStruct *)malloc(size);
    if (!structs) return 1;
    g_ptr = structs;
    fprintf(stderr, "struct base: %p, sizeof=%zu\n", (void*)structs, sizeof(TestStruct));

    /* Write to first struct */
    structs[0].id      = 0x12345678;
    structs[0].value   = 3.14159f;
    structs[0].precise = 3.141592653589793;
    structs[0].counter = 0xDEADBEEFCAFEBABELL;

    /* Write to second struct at different offset */
    structs[5].id      = 0xAABBCCDD;
    structs[5].value   = 2.71828f;
    structs[5].precise = 2.718281828459045;
    structs[5].counter = 0x1122334455667788LL;

    free((void *)structs);

    return 0;
}
