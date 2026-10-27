/*--------------------------------------------------------------------*/
/*--- Memlog: A memory store logging tool                ml_main.c ---*/
/*--------------------------------------------------------------------*/

/*
   This file is part of Memlog, a Valgrind tool for logging memory
   stores to heap-allocated blocks.

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License as
   published by the Free Software Foundation; either version 2 of the
   License, or (at your option) any later version.

   This program is distributed in the hope that it will be useful, but
   WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, see <http://www.gnu.org/licenses/>.

   The GNU General Public License is contained in the file COPYING.
*/

#include "pub_tool_basics.h"
#include "pub_tool_aspacemgr.h"
#include "pub_tool_libcbase.h"
#include "pub_tool_libcassert.h"
#include "pub_tool_libcprint.h"
#include "pub_tool_machine.h"
#include "pub_tool_mallocfree.h"
#include "pub_tool_options.h"
#include "pub_tool_replacemalloc.h"
#include "pub_tool_tooliface.h"
#include "pub_tool_execontext.h"
#include "pub_tool_debuginfo.h"
#include "pub_tool_libcfile.h"
#include "pub_tool_libcproc.h"
#include "pub_tool_stacktrace.h"
#include "pub_tool_vki.h"

#include "rbtree.h"

/* Include public header for client request IDs */
#include "valgrind.h"

/* Client request IDs - must match memlog.h */
typedef enum {
   VG_USERREQ__MEMLOG_TRACK_BLOCK = VG_USERREQ_TOOL_BASE('M','L'),
   VG_USERREQ__MEMLOG_UNTRACK_BLOCK
} Vg_MemlogClientRequest;

#define INLINE    inline __attribute__((always_inline))
#define MAX_LOG_ENTRIES 3000000
#define PAGE_SIZE 4096
#define ML_MALLOC_ALIGNMENT 32  /* 32-byte alignment for AVX support */

/*------------------------------------------------------------*/
/*--- Command line options                                 ---*/
/*------------------------------------------------------------*/

static SizeT clo_min_block_size = PAGE_SIZE;

/* MX emulation: blocks allocated from the listed sites have every store
   re-encoded as a 32-element shared-exponent block of doubles. */
static Bool         clo_mx_round      = False;
static Long         clo_mx_mbits      = 3;
static Long         clo_mx_emax       = 8;
static Long         clo_mx_emin       = -6;
static const HChar* clo_mx_sites_file = NULL;
static Bool         clo_mx_list_sites = False;
static Long         clo_mx_esz        = 8;
static Long         clo_mx_scale_bits = 8;

static Bool ml_process_cmd_line_option(const HChar* arg)
{
   if VG_BINT_CLO(arg, "--min-block-size", clo_min_block_size, 1, 1024*1024*1024) {}
   else if VG_BOOL_CLO(arg, "--mx-round", clo_mx_round) {}
   else if VG_BINT_CLO(arg, "--mx-mbits", clo_mx_mbits, 0, 52) {}
   else if VG_BINT_CLO(arg, "--mx-emax", clo_mx_emax, 0, 1023) {}
   else if VG_BINT_CLO(arg, "--mx-emin", clo_mx_emin, -1022, 0) {}
   else if VG_STR_CLO(arg, "--mx-sites-file", clo_mx_sites_file) {}
   else if VG_BOOL_CLO(arg, "--mx-list-sites", clo_mx_list_sites) {}
   else if VG_BINT_CLO(arg, "--mx-esz", clo_mx_esz, 4, 8) {}
   else if VG_BINT_CLO(arg, "--mx-scale-bits", clo_mx_scale_bits, 1, 16) {}
   else {
      return VG_(replacement_malloc_process_cmd_line_option)(arg);
   }
   return True;
}

static void ml_print_usage(void)
{
   VG_(printf)(
"    --min-block-size=<bytes>  minimum block size to track [%lu]\n"
"    --mx-round=no|yes         re-encode stores to selected blocks as MX blocks of doubles [no]\n"
"    --mx-mbits=<0..52>        element mantissa bits kept [3, as E4M3; saturates at 448 * 2^scale]\n"
"    --mx-emax=<n> --mx-emin=<n>  element exponent range relative to the block scale [8, -6]\n"
"    --mx-sites-file=<path>    allocating functions (names or 0x statement addresses) to round [all blocks]\n"
"    --mx-list-sites=no|yes    print the allocating statement of every tracked block [no]\n"
"    --mx-esz=4|8              element size: float or double [8]\n"
"    --mx-scale-bits=<1..16>   shared scale exponent bits, as E8M0 [8]\n",
   (unsigned long)PAGE_SIZE
   );
}

static void ml_print_debug_usage(void)
{
   VG_(printf)(
"    (none)\n"
   );
}

/*------------------------------------------------------------*/
/*--- Block tracking structures                            ---*/
/*------------------------------------------------------------*/

typedef struct {
   Addr        payload;   /* Start address of the block */
   SizeT       req_szB;   /* Size in bytes */
   ExeContext* alloc_ec;  /* Allocation stack trace */
   Bool        mx;        /* Stores are re-encoded as MX blocks */
} Block;

static rb_root_t tracked_blocks = RB_ROOT;

/*------------------------------------------------------------*/
/*--- Log buffer                                           ---*/
/*------------------------------------------------------------*/

typedef enum {
   LOG_STORE,
   LOG_ALLOC,
   LOG_FREE
} LogEventType;

typedef struct {
   LogEventType  type;
   Addr          addr;
   HWord         value;      /* For LOG_STORE */
   SizeT         size;       /* For LOG_ALLOC, LOG_FREE */
   ExeContext*   where;      /* For LOG_ALLOC, LOG_FREE */
} LogEntry;

static LogEntry log_buffer[MAX_LOG_ENTRIES];
static Int log_count = 0;

static INLINE void flush_log_buffer(void)
{
   for (Int i = 0; i < log_count; i++) {
      LogEntry* entry = &log_buffer[i];

      switch (entry->type) {
      case LOG_STORE:
         VG_(printf)("0x%lx 0x%lx\n", entry->addr, entry->value);
         break;

      case LOG_ALLOC:
         VG_(printf)("===ALLOC START===\n");
         VG_(printf)("Start 0x%lx, size %lu\n", entry->addr, entry->size);

         if (entry->where) {
            VG_(pp_ExeContext)(entry->where);
         } else {
            VG_(printf)("(No allocation stack trace available)\n");
         }

         VG_(printf)("===ALLOC END===\n");
         break;

      case LOG_FREE:
         VG_(printf)("===FREE START===\n");
         VG_(printf)("Start 0x%lx, size %lu\n", entry->addr, entry->size);

         if (entry->where) {
            VG_(pp_ExeContext)(entry->where);
         } else {
            VG_(printf)("(No free stack trace available)\n");
         }

         VG_(printf)("===FREE END===\n");
         break;
      }
   }
   log_count = 0;
}

static INLINE void add_to_buffer(LogEventType type, Addr addr, HWord value, SizeT size, ExeContext* where)
{
   log_buffer[log_count].type = type;
   log_buffer[log_count].addr = addr;
   if (type == LOG_STORE) {
      log_buffer[log_count].value = value;
   } else {
      log_buffer[log_count].size = size;
      log_buffer[log_count].where = where;
   }

   log_count++;
   if (log_count >= MAX_LOG_ENTRIES) {
      flush_log_buffer();
   }
}

/*------------------------------------------------------------*/
/*--- Block tracking                                       ---*/
/*------------------------------------------------------------*/

static INLINE void insert_block_rb(Block* bk) {
   rb_node_t **link  = &tracked_blocks.root;
   rb_node_t  *parent = NULL;

   while (*link) {
      parent = *link;
      if (bk->payload < parent->key)
         link = &parent->left;
      else if (bk->payload > parent->key)
         link = &parent->right;
      else {
         /* same start address already present – nothing to do */
         return;
      }
   }

   rb_node_t *n = VG_(malloc)("memlog.rbnode", sizeof(*n));
   *n = (rb_node_t){
      .parent = NULL, .left = NULL, .right = NULL,
      .color  = RED,
      .key    = bk->payload,
      .data   = bk
   };

   rb_link_node(n, parent, link);
   rb_insert_color(n, &tracked_blocks);
}

static INLINE Block* find_block_containing(Addr addr) {
   rb_node_t *n = rb_search_leq(&tracked_blocks, (unsigned long)addr);
   if (!n) return NULL;

   Block *bk = (Block*)n->data;
   if (addr < bk->payload + bk->req_szB) {
      return bk;
   }
   return NULL;
}

static INLINE Bool is_tracked(Addr addr) {
   return find_block_containing(addr) != NULL;
}

/*------------------------------------------------------------*/
/*--- Store logging                                        ---*/
/*------------------------------------------------------------*/

static VG_REGPARM(2) void log_store(Addr addr, HWord value) {
   if (is_tracked(addr)) {
      add_to_buffer(LOG_STORE, addr, value, 0, NULL);
   }
}

/*------------------------------------------------------------*/
/*--- MX emulation                                         ---*/
/*------------------------------------------------------------*/

#define MX_BLOCK_ELEMS 32
#define MX_MAX_SITES   4096

static HChar* mx_sites[MX_MAX_SITES];
static Int    mx_n_sites = 0;

static ULong mx_blocks_marked = 0, mx_bytes_marked = 0;
static ULong mx_stores = 0, mx_values_changed = 0, mx_values_flushed = 0;
static ULong mx_blocks_nan = 0, mx_scales_clamped = 0, mx_values_saturated = 0;

static void mx_load_sites(void)
{
   if (!clo_mx_sites_file) return;
   SysRes sr = VG_(open)(clo_mx_sites_file, VKI_O_RDONLY, 0);
   if (sr_isError(sr)) {
      VG_(fmsg)("memlog: cannot open --mx-sites-file=%s\n", clo_mx_sites_file);
      VG_(exit)(1);
   }
   Int fd = sr_Res(sr);
   SizeT cap = 1 << 16, len = 0;
   HChar* buf = VG_(malloc)("memlog.mx.sites", cap + 1);
   Int n;
   while ((n = VG_(read)(fd, buf + len, cap - len)) > 0) {
      len += n;
      if (len == cap) {
         cap *= 2;
         buf = VG_(realloc)("memlog.mx.sites", buf, cap + 1);
      }
   }
   VG_(close)(fd);
   buf[len] = 0;
   HChar* save;
   for (HChar* tok = VG_(strtok_r)(buf, "\r\n", &save);
        tok && mx_n_sites < MX_MAX_SITES;
        tok = VG_(strtok_r)(NULL, "\r\n", &save)) {
      if (tok[0] != '#' && tok[0] != 0)
         mx_sites[mx_n_sites++] = tok;
   }
}

static Bool is_allocator_frame(const HChar* fn)
{
   return VG_(strstr)(fn, "malloc") || VG_(strstr)(fn, "calloc")
       || VG_(strstr)(fn, "realloc") || VG_(strstr)(fn, "memalign")
       || VG_(strstr)(fn, "operator new") || VG_(strstr)(fn, "_gfortran");
}

/* The allocating statement is the first frame outside the allocator, the
   same frame the offline analysis uses. Sites match by function name or by
   the statement's address, written as in Memlog's stack traces. */
static Bool mx_site_selected(ThreadId tid, SizeT szB)
{
   if (mx_n_sites == 0 && !clo_mx_list_sites) return True;
   Addr ips[16];
   UInt n = VG_(get_StackTrace)(tid, ips, 16, NULL, NULL, 0);
   DiEpoch ep = VG_(current_DiEpoch)();
   for (UInt i = 0; i < n; i++) {
      const HChar* fn;
      if (!VG_(get_fnname)(ep, ips[i], &fn) || is_allocator_frame(fn))
         continue;
      HChar addr[32];
      VG_(sprintf)(addr, "0x%lX", ips[i]);
      if (clo_mx_list_sites)
         VG_(umsg)("MXSITE %s %s %lu\n", addr, fn, szB);
      if (mx_n_sites == 0) return True;
      for (Int s = 0; s < mx_n_sites; s++)
         if (VG_(strcmp)(fn, mx_sites[s]) == 0 || VG_(strcmp)(addr, mx_sites[s]) == 0)
            return True;
      return False;
   }
   return False;
}

/* IEEE layout of the stored elements: binary64 or binary32. */
typedef struct { Int esz, mant, emask, bias; } FpFmt;
static const FpFmt FMT64 = { 8, 52, 0x7FF, 1023 };
static const FpFmt FMT32 = { 4, 23, 0xFF, 127 };

static INLINE ULong mx_load(const FpFmt* f, Addr a)
{ return f->esz == 8 ? *(ULong*)a : *(UInt*)a; }

static INLINE void mx_store(const FpFmt* f, Addr a, ULong v)
{ if (f->esz == 8) *(ULong*)a = v; else *(UInt*)a = (UInt)v; }

/* Significand (implicit bit included) and exponent of its least significant
   bit for a finite nonzero element, so that |v| = sig * 2^lsb. */
static INLINE void mx_split(const FpFmt* f, ULong v, ULong* sig, Long* lsb)
{
   Long e = (v >> f->mant) & f->emask;
   *sig = v & ((1ULL << f->mant) - 1);
   if (e == 0) {
      *lsb = 1 - f->bias - f->mant;
   } else {
      *sig |= 1ULL << f->mant;
      *lsb = e - f->bias - f->mant;
   }
}

/* floor(log2|v|) for a finite nonzero element. */
static INLINE Long mx_lead(const FpFmt* f, ULong v)
{
   ULong sig;
   Long  lsb;
   mx_split(f, v, &sig, &lsb);
   return lsb + 63 - __builtin_clzll(sig);
}

/* Largest element significand, in units of the top binade's quantum, as
   microxcaling's max_norm: all mantissa bits set, except E4M3, whose
   S.1111.111 encoding is NaN, so its largest normal is 1.75 * 2^emax. */
static INLINE ULong mx_max_sig(void)
{
   ULong ones = (1ULL << (clo_mx_mbits + 1)) - 1;
   return clo_mx_mbits == 3 && clo_mx_emax == 8 ? ones - 1 : ones;
}

/* Round one finite element of a block with shared exponent `shared`, as
   microxcaling's _quantize_elemwise_core does on x / 2^shared: mbits of
   mantissa while the element is normal (exponent >= shared + emin), fixed
   quantum below that, ties away from zero, saturated to max_norm. Subnormal
   inputs and outputs are handled, so the result is the exact binary32/64
   value of the MX element. */
static ULong mx_quantize(const FpFmt* f, ULong v, Long shared)
{
   ULong sign = v & (1ULL << (8 * f->esz - 1));
   if ((v & ~sign) == 0) return v;
   ULong sig;
   Long  lsb;
   mx_split(f, v, &sig, &lsb);
   Long  lead  = lsb + 63 - __builtin_clzll(sig);
   Long  qe    = (lead - shared >= clo_mx_emin ? lead : shared + clo_mx_emin)
                 - clo_mx_mbits;
   Long  shift = qe - lsb;
   if (shift <= 0) return v;
   ULong r = shift < 64 ? (sig + (1ULL << (shift - 1))) >> shift : 0;
   if (r == 0) { mx_values_flushed++; return sign; }
   /* Only the top binade can exceed max_norm, by rounding up or by holding a
      significand above it. */
   if (qe == shared + clo_mx_emax - clo_mx_mbits && r > mx_max_sig()) {
      r = mx_max_sig();
      mx_values_saturated++;
   }
   Long rlead = qe + 63 - __builtin_clzll(r);
   Long be    = rlead + f->bias;
   if (be >= f->emask) return sign | ((ULong)f->emask << f->mant);
   if (be <= 0)
      return sign | (r << (qe - (1 - f->bias - f->mant)));
   ULong mmask = (1ULL << f->mant) - 1;
   return sign | ((ULong)be << f->mant)
               | ((r << (f->mant - (rlead - qe))) & mmask);
}

/* Every element of a block whose scale is NaN reads back as a quiet NaN;
   microxcaling divides by the NaN scale before restoring infinities, so an
   infinity in the block becomes NaN too. */
static INLINE ULong mx_nan_element(const FpFmt* f)
{
   return ((ULong)f->emask << f->mant) | (1ULL << (f->mant - 1));
}

/* Shared exponent as microxcaling's _shared_exponents with method "max":
   floor(log2(max|x|)) - emax, over every element of the block. A scale
   above the E8M0 range, or an Inf/NaN in the block, makes the scale NaN;
   a scale below the range is clamped to its minimum. */
static void mx_encode_block(const FpFmt* f, Block* bk, SizeT bi)
{
   Addr  base  = bk->payload + bi * MX_BLOCK_ELEMS * f->esz;
   SizeT left  = (bk->req_szB / f->esz) - bi * MX_BLOCK_ELEMS;
   Int   n     = left < MX_BLOCK_ELEMS ? (Int)left : MX_BLOCK_ELEMS;
   ULong sbit  = 1ULL << (8 * f->esz - 1);
   Long  semax = (1LL << (clo_mx_scale_bits - 1)) - 1;
   Bool  any = False, nonfinite = False;
   Long  lmax = 0;
   for (Int i = 0; i < n; i++) {
      ULong v = mx_load(f, base + i * f->esz);
      if ((v & ~sbit) == 0) continue;
      if (((v >> f->mant) & f->emask) == (ULong)f->emask) { nonfinite = True; continue; }
      Long lead = mx_lead(f, v);
      if (!any || lead > lmax) lmax = lead;
      any = True;
   }
   Long shared = lmax - clo_mx_emax;
   if (nonfinite || (any && shared > semax)) {
      mx_blocks_nan++;
      for (Int i = 0; i < n; i++) {
         Addr  a = base + i * f->esz;
         ULong v = mx_load(f, a);
         ULong q = mx_nan_element(f);
         if (q != v) { mx_store(f, a, q); mx_values_changed++; }
      }
      return;
   }
   if (!any) return;
   if (shared < -semax) { shared = -semax; mx_scales_clamped++; }
   for (Int i = 0; i < n; i++) {
      Addr  a = base + i * f->esz;
      ULong v = mx_load(f, a);
      ULong q = mx_quantize(f, v, shared);
      if (q != v) { mx_store(f, a, q); mx_values_changed++; }
   }
}

static VG_REGPARM(2) void mx_after_store(Addr addr, HWord size)
{
   Block* bk = find_block_containing(addr);
   if (!bk || !bk->mx) return;
   mx_stores++;
   const FpFmt* f = clo_mx_esz == 4 ? &FMT32 : &FMT64;
   SizeT span = MX_BLOCK_ELEMS * f->esz;
   SizeT nblocks = bk->req_szB / span + ((bk->req_szB % span) >= (SizeT)f->esz);
   SizeT first = (addr - bk->payload) / span;
   SizeT last  = (addr + size - 1 - bk->payload) / span;
   for (SizeT bi = first; bi <= last && bi < nblocks; bi++)
      mx_encode_block(f, bk, bi);
}

/*------------------------------------------------------------*/
/*--- malloc() et al replacement wrappers                  ---*/
/*------------------------------------------------------------*/

static void* new_block(ThreadId tid, SizeT szB, SizeT alignB, Bool is_zeroed)
{
   void* p;

   if ((SSizeT)szB < 0) return NULL;

   if (szB == 0) {
      szB = 1;
   }

   p = VG_(cli_malloc)(alignB, szB);
   if (!p) {
      return NULL;
   }
   if (is_zeroed) VG_(memset)(p, 0, szB);

   /* Only track blocks >= min_block_size */
   if (szB >= clo_min_block_size) {
      Block* bk = VG_(malloc)("memlog.block", sizeof(Block));
      bk->payload  = (Addr)p;
      bk->req_szB  = szB;
      bk->alloc_ec = VG_(record_ExeContext)(tid, 0);
      bk->mx       = clo_mx_round && mx_site_selected(tid, szB);
      if (bk->mx) {
         mx_blocks_marked++;
         mx_bytes_marked += szB;
      }

      insert_block_rb(bk);
      add_to_buffer(LOG_ALLOC, (Addr)p, 0, szB, bk->alloc_ec);
   }

   return p;
}

static void die_block(ThreadId tid, void* p)
{
   if (!p) return;

   Block* bk = find_block_containing((Addr)p);

   if (bk && bk->payload == (Addr)p) {
      ExeContext* free_ec = VG_(record_ExeContext)(tid, 0);
      add_to_buffer(LOG_FREE, (Addr)p, 0, bk->req_szB, free_ec);

      rb_node_t *deleted = rb_delete(&tracked_blocks, bk->payload);
      if (deleted) {
         VG_(free)(deleted);
      }
      VG_(free)(bk);
   }

   VG_(cli_free)(p);
}

static void* ml_malloc(ThreadId tid, SizeT szB)
{
   return new_block(tid, szB, ML_MALLOC_ALIGNMENT, False);
}

static void* ml___builtin_new(ThreadId tid, SizeT szB)
{
   return new_block(tid, szB, ML_MALLOC_ALIGNMENT, False);
}

static void* ml___builtin_new_aligned(ThreadId tid, SizeT szB, SizeT alignB, SizeT orig_alignB)
{
   return new_block(tid, szB, alignB, False);
}

static void* ml___builtin_vec_new(ThreadId tid, SizeT szB)
{
   return new_block(tid, szB, ML_MALLOC_ALIGNMENT, False);
}

static void* ml___builtin_vec_new_aligned(ThreadId tid, SizeT szB, SizeT alignB, SizeT orig_alignB)
{
   return new_block(tid, szB, alignB, False);
}

static void* ml_memalign(ThreadId tid, SizeT alignB, SizeT orig_alignB, SizeT szB)
{
   return new_block(tid, szB, alignB, False);
}

static void* ml_calloc(ThreadId tid, SizeT nmemb, SizeT size1)
{
   return new_block(tid, nmemb * size1, ML_MALLOC_ALIGNMENT, True);
}

static void ml_free(ThreadId tid, void* p)
{
   die_block(tid, p);
}

static void ml___builtin_delete(ThreadId tid, void* p)
{
   die_block(tid, p);
}

static void ml___builtin_delete_aligned(ThreadId tid, void* p, SizeT alignB)
{
   die_block(tid, p);
}

static void ml___builtin_vec_delete(ThreadId tid, void* p)
{
   die_block(tid, p);
}

static void ml___builtin_vec_delete_aligned(ThreadId tid, void* p, SizeT alignB)
{
   die_block(tid, p);
}

static void* ml_realloc(ThreadId tid, void* p_old, SizeT new_szB)
{
   if (p_old == NULL) {
      return ml_malloc(tid, new_szB);
   }
   if (new_szB == 0) {
      if (VG_(clo_realloc_zero_bytes_frees) == True) {
         ml_free(tid, p_old);
         return NULL;
      }
      new_szB = 1;
   }

   Block* old_bk = find_block_containing((Addr)p_old);
   SizeT old_szB = old_bk ? old_bk->req_szB : VG_(cli_malloc_usable_size)(p_old);

   void* p_new = ml_malloc(tid, new_szB);
   if (!p_new) {
      return NULL;
   }

   VG_(memmove)(p_new, p_old, VG_MIN(old_szB, new_szB));
   ml_free(tid, p_old);

   return p_new;
}

static SizeT ml_malloc_usable_size(ThreadId tid, void* p)
{
   Block* bk = find_block_containing((Addr)p);
   if (bk && bk->payload == (Addr)p) {
      return bk->req_szB;
   }
   return VG_(cli_malloc_usable_size)(p);
}

/*------------------------------------------------------------*/
/*--- Instrumentation                                      ---*/
/*------------------------------------------------------------*/

static INLINE void wire_log_store(IRSB* bb_out,
   IRTemp  addr_tmp,
   IRExpr* addr,
   IRTemp  data_tmp,
   IRExpr* data_widen)
{
   addStmtToIRSB(bb_out, IRStmt_WrTmp(addr_tmp, addr));
   addStmtToIRSB(bb_out, IRStmt_WrTmp(data_tmp, data_widen));
   IRDirty* dirty = unsafeIRDirty_0_N(
      2,
      "log_store",
      (void*)VG_(fnptr_to_fnentry)(log_store),
      mkIRExprVec_2(IRExpr_RdTmp(addr_tmp), IRExpr_RdTmp(data_tmp)));
   addStmtToIRSB(bb_out, IRStmt_Dirty(dirty));
}

/* Called after the store so the helper sees the stored value. The declared
   memory footprint covers any 256-byte MX block the store can touch, so
   later loads in the superblock are not served from before the rewrite. */
static IRSB* wire_mx(IRSB* bb_in)
{
   IRSB* bb_out = deepCopyIRSBExceptStmts(bb_in);
   for (Int i = 0; i < bb_in->stmts_used; i++) {
      IRStmt* stmt = bb_in->stmts[i];
      if (!stmt) continue;
      if (stmt->tag != Ist_Store) {
         addStmtToIRSB(bb_out, stmt);
         continue;
      }
      IRTemp addr_tmp = newIRTemp(bb_out->tyenv, Ity_I64);
      addStmtToIRSB(bb_out, IRStmt_WrTmp(addr_tmp, stmt->Ist.Store.addr));
      IRStmt* st = IRStmt_Store(stmt->Ist.Store.end, IRExpr_RdTmp(addr_tmp),
                                stmt->Ist.Store.data);
      addStmtToIRSB(bb_out, st);
      Int size = sizeofIRType(typeOfIRExpr(bb_in->tyenv, stmt->Ist.Store.data));
      IRTemp lo_tmp = newIRTemp(bb_out->tyenv, Ity_I64);
      addStmtToIRSB(bb_out, IRStmt_WrTmp(lo_tmp,
         IRExpr_Binop(Iop_Sub64, IRExpr_RdTmp(addr_tmp), IRExpr_Const(IRConst_U64(256)))));
      IRDirty* d = unsafeIRDirty_0_N(
         2, "mx_after_store", (void*)VG_(fnptr_to_fnentry)(mx_after_store),
         mkIRExprVec_2(IRExpr_RdTmp(addr_tmp),
                       IRExpr_Const(IRConst_U64(size))));
      d->mFx   = Ifx_Modify;
      d->mAddr = IRExpr_RdTmp(lo_tmp);
      d->mSize = 512 + size;
      addStmtToIRSB(bb_out, IRStmt_Dirty(d));
   }
   return bb_out;
}

static INLINE IRSB* wire_memlog(IRSB* bb_in)
{
   IRSB* bb_out = deepCopyIRSBExceptStmts(bb_in);
   IRTemp addr_tmp, data_tmp, addr_tmp1, data_tmp1, addr_tmp2, data_tmp2, addr_tmp3, data_tmp3;

   for (Int i = 0; i < bb_in->stmts_used; i++) {
      IRStmt* stmt = bb_in->stmts[i];
      if (!stmt)
         continue;

      if (stmt->tag == Ist_Store) {
         IRExpr* data       = stmt->Ist.Store.data;
         IRExpr* addr       = stmt->Ist.Store.addr;
         addr_tmp           = newIRTemp(bb_out->tyenv, Ity_I64);
         data_tmp           = newIRTemp(bb_out->tyenv, Ity_I64);
         addr_tmp1          = newIRTemp(bb_out->tyenv, Ity_I64);
         data_tmp1          = newIRTemp(bb_out->tyenv, Ity_I64);
         addr_tmp2          = newIRTemp(bb_out->tyenv, Ity_I64);
         data_tmp2          = newIRTemp(bb_out->tyenv, Ity_I64);
         addr_tmp3          = newIRTemp(bb_out->tyenv, Ity_I64);
         data_tmp3          = newIRTemp(bb_out->tyenv, Ity_I64);
         IRType  ty         = typeOfIRExpr(bb_in->tyenv, data);
         switch (ty) {
         case Ity_I1:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_1Uto64, data));
            break;
         case Ity_I8:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_8Uto64, data));
            break;
         case Ity_I16:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_16Uto64, data));
            break;
         case Ity_I32:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_32Uto64, data));
            break;
         case Ity_I64:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, data);
            break;
         case Ity_F32:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp,
               IRExpr_Unop(Iop_32Uto64, IRExpr_Unop(Iop_ReinterpF32asI32, data)));
            break;
         case Ity_F64:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_ReinterpF64asI64, data));
            break;
         case Ity_V128:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_V128HIto64, data));
            wire_log_store(bb_out, addr_tmp1, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(8))), data_tmp1, IRExpr_Unop(Iop_V128to64, data));
            break;
         case Ity_I128:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_128HIto64, data));
            wire_log_store(bb_out, addr_tmp1, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(8))), data_tmp1, IRExpr_Unop(Iop_128to64, data));
            break;
         case Ity_F128:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_ReinterpF64asI64, IRExpr_Unop(Iop_F128HItoF64, data)));
            wire_log_store(bb_out, addr_tmp1, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(8))), data_tmp1, IRExpr_Unop(Iop_ReinterpF64asI64, IRExpr_Unop(Iop_F128LOtoF64, data)));
            break;
         case Ity_D128:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_ReinterpD64asI64, IRExpr_Unop(Iop_D128HItoD64, data)));
            wire_log_store(bb_out, addr_tmp1, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(8))), data_tmp1, IRExpr_Unop(Iop_ReinterpD64asI64, IRExpr_Unop(Iop_D128LOtoD64, data)));
            break;
         case Ity_F16:
            /* F16 not fully supported - skip for now */
            break;
         case Ity_V256:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_V256to64_3, data));
            wire_log_store(bb_out, addr_tmp1, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(8))), data_tmp1, IRExpr_Unop(Iop_V256to64_2, data));
            wire_log_store(bb_out, addr_tmp2, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(16))), data_tmp2, IRExpr_Unop(Iop_V256to64_1, data));
            wire_log_store(bb_out, addr_tmp3, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(24))), data_tmp3, IRExpr_Unop(Iop_V256to64_0, data));
            break;
         case Ity_D32:
         case Ity_D64:
            /* TODO: add support for D32 and D64 */
            break;
         case Ity_INVALID:
            break;
         }
      }

      addStmtToIRSB(bb_out, stmt);
   }

   return bb_out;
}

static IRSB* ml_instrument(VgCallbackClosure* closure,
    IRSB* bb_in,
    const VexGuestLayout* layout,
    const VexGuestExtents* vge,
    const VexArchInfo* archinfo_host,
    IRType gWordTy,
    IRType hWordTy)
{
    return clo_mx_round ? wire_mx(bb_in) : wire_memlog(bb_in);
}

/*------------------------------------------------------------*/
/*--- Client request handler                               ---*/
/*------------------------------------------------------------*/

static Bool ml_handle_client_request(ThreadId tid, UWord* arg, UWord* ret)
{
   switch (arg[0]) {
   case VG_USERREQ__MEMLOG_TRACK_BLOCK: {
      Addr  addr = arg[1];
      SizeT size = arg[2];

      if (size > 0) {
         Block* bk = VG_(malloc)("memlog.client_block", sizeof(Block));
         bk->payload  = addr;
         bk->req_szB  = size;
         bk->alloc_ec = VG_(record_ExeContext)(tid, 0);
         bk->mx       = False;

         insert_block_rb(bk);
         add_to_buffer(LOG_ALLOC, addr, 0, size, bk->alloc_ec);
      }
      *ret = 0;
      return True;
   }

   case VG_USERREQ__MEMLOG_UNTRACK_BLOCK: {
      Addr addr = arg[1];

      Block* bk = find_block_containing(addr);
      if (bk && bk->payload == addr) {
         ExeContext* ec = VG_(record_ExeContext)(tid, 0);
         add_to_buffer(LOG_FREE, addr, 0, bk->req_szB, ec);

         rb_node_t *deleted = rb_delete(&tracked_blocks, bk->payload);
         if (deleted) {
            VG_(free)(deleted);
         }
         VG_(free)(bk);
      }
      *ret = 0;
      return True;
   }

   default:
      return False;
   }
}

/*------------------------------------------------------------*/
/*--- Cleanup helpers                                      ---*/
/*------------------------------------------------------------*/

static void free_rb_tree_recursive(rb_node_t *node) {
   if (!node)
       return;

   free_rb_tree_recursive(node->left);
   free_rb_tree_recursive(node->right);

   /* Free the Block data */
   if (node->data) {
      VG_(free)(node->data);
   }
   VG_(free)(node);
}

static void free_rb_tree(rb_root_t *root) {
   free_rb_tree_recursive(root->root);
   root->root = NULL;
}

/*------------------------------------------------------------*/
/*--- Tool init/fini                                       ---*/
/*------------------------------------------------------------*/

static void ml_post_clo_init(void)
{
   if (clo_mx_round) mx_load_sites();
}

static void ml_fini(Int exitcode)
{
   flush_log_buffer();
   if (clo_mx_round) {
      VG_(umsg)("MX: esz=%lld mbits=%lld emax=%lld emin=%lld scale_bits=%lld sites=%d\n",
                clo_mx_esz, clo_mx_mbits, clo_mx_emax, clo_mx_emin,
                clo_mx_scale_bits, mx_n_sites);
      VG_(umsg)("MX: blocks_marked=%llu bytes_marked=%llu stores=%llu\n",
                mx_blocks_marked, mx_bytes_marked, mx_stores);
      VG_(umsg)("MX: values_changed=%llu values_flushed=%llu values_saturated=%llu\n",
                mx_values_changed, mx_values_flushed, mx_values_saturated);
      VG_(umsg)("MX: blocks_nan=%llu scales_clamped=%llu\n",
                mx_blocks_nan, mx_scales_clamped);
   }
   free_rb_tree(&tracked_blocks);
}

static void ml_pre_clo_init(void)
{
   VG_(details_name)            ("Memlog");
   VG_(details_version)         (NULL);
   VG_(details_description)     ("a memory store logger");
   VG_(details_copyright_author)(
      "Copyright (C) 2025, and GNU GPL'd, by Enzo Bonansea (ebonansea@dc.uba.ar).");
   VG_(details_bug_reports_to)  (VG_BUGS_TO);
   VG_(details_avg_translation_sizeB)(640);

   VG_(basic_tool_funcs)        (ml_post_clo_init,
                                 ml_instrument,
                                 ml_fini);

   VG_(needs_command_line_options)(ml_process_cmd_line_option,
                                   ml_print_usage,
                                   ml_print_debug_usage);

   VG_(needs_client_requests)(ml_handle_client_request);

   VG_(needs_malloc_replacement)(ml_malloc,
                                 ml___builtin_new,
                                 ml___builtin_new_aligned,
                                 ml___builtin_vec_new,
                                 ml___builtin_vec_new_aligned,
                                 ml_memalign,
                                 ml_calloc,
                                 ml_free,
                                 ml___builtin_delete,
                                 ml___builtin_delete_aligned,
                                 ml___builtin_vec_delete,
                                 ml___builtin_vec_delete_aligned,
                                 ml_realloc,
                                 ml_malloc_usable_size,
                                 0);
}

VG_DETERMINE_INTERFACE_VERSION(ml_pre_clo_init)

/*--------------------------------------------------------------------*/
/*--- end                                                ml_main.c ---*/
/*--------------------------------------------------------------------*/
