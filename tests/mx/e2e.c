/* End-to-end check of --mx-round under Valgrind. Reads doubles from argv[1]
   into a staging buffer (allocated in main, not an MX site), copies them
   element by element into a buffer allocated by mx_target_alloc (the MX
   site), writing the largest-magnitude element of each 32-block first so
   every block is rounded once with its final scale, then dumps both. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

__attribute__((noinline)) double* mx_target_alloc(size_t n)
{
   return calloc(n, sizeof(double));
}

int main(int argc, char** argv)
{
   FILE* f = fopen(argv[1], "rb");
   fseek(f, 0, SEEK_END);
   size_t n = ftell(f) / sizeof(double);
   fseek(f, 0, SEEK_SET);
   double* staging = malloc(n * sizeof(double));
   if (fread(staging, sizeof(double), n, f) != n) return 3;
   fclose(f);

   volatile double* dst = mx_target_alloc(n);
   for (size_t b = 0; b < n; b += 32) {
      size_t imax = b;
      for (size_t i = b; i < b + 32; i++)
         if (fabs(staging[i]) > fabs(staging[imax])) imax = i;
      dst[imax] = staging[imax];
      for (size_t i = b; i < b + 32; i++)
         if (i != imax) dst[i] = staging[i];
   }

   FILE* o = fopen(argv[2], "wb");
   fwrite((const void*)dst, sizeof(double), n, o);
   fwrite(staging, sizeof(double), n, o);
   fclose(o);
   return 0;
}
