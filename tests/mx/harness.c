/* Unit harness for Memlog's MX quantizer. The MX functions are pulled
   verbatim from ml_main.c into mx_region.c by compare.py and
   compiled natively; this file only
   provides the Valgrind types and globals they use.
   Usage: harness <esz 4|8> <in.bin> <out.bin> [mbits emax emin scale_bits] */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

typedef unsigned long long ULong;
typedef long long          Long;
typedef int                Int;
typedef unsigned int       UInt;
typedef unsigned char      Bool;
typedef uintptr_t          Addr;
typedef size_t             SizeT;
#define True  1
#define False 0
#define INLINE inline __attribute__((always_inline))

typedef struct { Addr payload; SizeT req_szB; } Block;

static Long clo_mx_mbits = 3, clo_mx_emax = 8, clo_mx_emin = -6;
static Long clo_mx_scale_bits = 8;
static ULong mx_values_changed, mx_values_flushed, mx_values_saturated;
static ULong mx_blocks_nan, mx_scales_clamped;
static ULong mx_values_unencodable __attribute__((unused)); /* 3e26451 quantizer */
#define MX_BLOCK_ELEMS 32

#include "mx_region.c"

int main(int argc, char** argv)
{
   if (argc < 4) return 2;
   int esz = atoi(argv[1]);
   if (argc >= 8) {
      clo_mx_mbits = atoll(argv[4]); clo_mx_emax = atoll(argv[5]);
      clo_mx_emin = atoll(argv[6]); clo_mx_scale_bits = atoll(argv[7]);
   }
   FILE* fi = fopen(argv[2], "rb");
   fseek(fi, 0, SEEK_END);
   long n = ftell(fi);
   fseek(fi, 0, SEEK_SET);
   unsigned char* buf = malloc(n);
   if (fread(buf, 1, n, fi) != (size_t)n) return 3;
   fclose(fi);
   const FpFmt* f = esz == 4 ? &FMT32 : &FMT64;
   Block bk = { (Addr)buf, (SizeT)n };
   SizeT span = MX_BLOCK_ELEMS * esz;
   for (SizeT bi = 0; bi * span < (SizeT)n; bi++)
      mx_encode_block(f, &bk, bi);
   FILE* fo = fopen(argv[3], "wb");
   fwrite(buf, 1, n, fo);
   fclose(fo);
   fprintf(stderr, "changed=%llu flushed=%llu saturated=%llu blocks_nan=%llu scales_clamped=%llu\n",
           mx_values_changed, mx_values_flushed, mx_values_saturated, mx_blocks_nan,
           mx_scales_clamped);
   return 0;
}
