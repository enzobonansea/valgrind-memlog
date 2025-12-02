/*--------------------------------------------------------------------*/
/*--- Memlog: A memory store logging tool                 memlog.h ---*/
/*--------------------------------------------------------------------*/

/*
   This file is part of Memlog, a Valgrind tool for logging memory
   stores to tracked memory blocks.

   This header provides client request macros that allow programs
   to manually track memory regions (stack, globals, mmap'd memory, etc.)
   in addition to automatic heap tracking.
*/

#ifndef __MEMLOG_H
#define __MEMLOG_H

#include "valgrind.h"

/* Client request IDs for Memlog */
typedef enum {
   VG_USERREQ__MEMLOG_TRACK_BLOCK = VG_USERREQ_TOOL_BASE('M','L'),
   VG_USERREQ__MEMLOG_UNTRACK_BLOCK
} Vg_MemlogClientRequest;

/*
 * MEMLOG_TRACK_BLOCK(addr, size)
 *
 * Start tracking a memory region at 'addr' of 'size' bytes.
 * Stores to this region will be logged regardless of how the memory
 * was allocated (stack, global, mmap, etc.).
 *
 * Note: Does not respect --min-block-size; all tracked regions are logged.
 */
#define MEMLOG_TRACK_BLOCK(_qzz_addr, _qzz_size)                  \
   VALGRIND_DO_CLIENT_REQUEST_EXPR(0 /* default return */,        \
                           VG_USERREQ__MEMLOG_TRACK_BLOCK,        \
                           (_qzz_addr), (_qzz_size), 0, 0, 0)

/*
 * MEMLOG_UNTRACK_BLOCK(addr)
 *
 * Stop tracking the memory region starting at 'addr'.
 * This is optional for stack/automatic variables as they will
 * simply stop receiving stores when out of scope.
 */
#define MEMLOG_UNTRACK_BLOCK(_qzz_addr)                           \
   VALGRIND_DO_CLIENT_REQUEST_EXPR(0 /* default return */,        \
                           VG_USERREQ__MEMLOG_UNTRACK_BLOCK,      \
                           (_qzz_addr), 0, 0, 0, 0)

#endif /* __MEMLOG_H */
