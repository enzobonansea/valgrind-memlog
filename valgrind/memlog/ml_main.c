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

#include "memlog.h"
#include "rbtree.h"

#define INLINE    inline __attribute__((always_inline))
#define MAX_LOG_ENTRIES 3000000
#define PAGE_SIZE 4096

/*------------------------------------------------------------*/
/*--- Command line options                                 ---*/
/*------------------------------------------------------------*/

static SizeT clo_min_block_size = PAGE_SIZE;

static Bool ml_process_cmd_line_option(const HChar* arg)
{
   if VG_BINT_CLO(arg, "--min-block-size", clo_min_block_size, 1, 1024*1024*1024) {}
   else {
      return VG_(replacement_malloc_process_cmd_line_option)(arg);
   }
   return True;
}

static void ml_print_usage(void)
{
   VG_(printf)(
"    --min-block-size=<bytes>  minimum block size to track [%lu]\n",
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
   return new_block(tid, szB, VG_(clo_alignment), False);
}

static void* ml___builtin_new(ThreadId tid, SizeT szB)
{
   return new_block(tid, szB, VG_(clo_alignment), False);
}

static void* ml___builtin_new_aligned(ThreadId tid, SizeT szB, SizeT alignB, SizeT orig_alignB)
{
   return new_block(tid, szB, alignB, False);
}

static void* ml___builtin_vec_new(ThreadId tid, SizeT szB)
{
   return new_block(tid, szB, VG_(clo_alignment), False);
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
   return new_block(tid, nmemb * size1, VG_(clo_alignment), True);
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

static INLINE Bool is_app_code(const VexGuestExtents* vge)
{
   /* Instrument all code - the is_tracked() check in log_store()
    * ensures we only log stores to tracked heap blocks */
   (void)vge;
   return True;
}

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
    return is_app_code(vge) ? wire_memlog(bb_in) : bb_in;
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
}

static void ml_fini(Int exitcode)
{
   flush_log_buffer();
   free_rb_tree(&tracked_blocks);
}

static void ml_pre_clo_init(void)
{
   VG_(details_name)            ("Memlog");
   VG_(details_version)         (NULL);
   VG_(details_description)     ("a memory store logger");
   VG_(details_copyright_author)(
      "Copyright (C) 2024, and GNU GPL'd, by the Memlog authors.");
   VG_(details_bug_reports_to)  (VG_BUGS_TO);
   VG_(details_avg_translation_sizeB)(640);

   VG_(basic_tool_funcs)        (ml_post_clo_init,
                                 ml_instrument,
                                 ml_fini);

   VG_(needs_command_line_options)(ml_process_cmd_line_option,
                                   ml_print_usage,
                                   ml_print_debug_usage);

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
