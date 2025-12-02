dist_noinst_SCRIPTS = filter_stderr filter_stderr_with_addr

noinst_PROGRAMS = \
	basic_alloc \
	double_stores \
	int_stores \
	small_block \
	multi_alloc \
	custom_threshold \
	calloc_test \
	avx_stores \
	random_offsets \
	stack_array \
	all_types

EXTRA_DIST = \
	basic_alloc.stderr.exp basic_alloc.vgtest \
	double_stores.stderr.exp double_stores.vgtest \
	int_stores.stderr.exp int_stores.vgtest \
	small_block.stderr.exp small_block.vgtest \
	multi_alloc.stderr.exp multi_alloc.vgtest \
	custom_threshold.stderr.exp custom_threshold.vgtest \
	calloc_test.stderr.exp calloc_test.vgtest \
	avx_stores.stderr.exp avx_stores.vgtest \
	random_offsets.stderr.exp random_offsets.vgtest \
	stack_array.stderr.exp stack_array.vgtest \
	all_types.stderr.exp all_types.vgtest

AM_CFLAGS   = $(WERROR) -Winline -Wall -Wshadow -Wno-long-long \
              @FLAG_FNO_STACK_PROTECTOR@ $(AM_FLAG_M3264_PRI) -O0
AM_CPPFLAGS = -I$(top_srcdir) -I$(top_srcdir)/include \
              -I$(top_srcdir)/coregrind -I$(top_builddir)/include \
              -I$(top_srcdir)/VEX/pub \
              -DVGA_@VGCONF_ARCH_PRI@=1 \
              -DVGO_@VGCONF_OS@=1 \
              -DVGP_@VGCONF_ARCH_PRI@_@VGCONF_OS@=1 \
              -DVGPV_@VGCONF_ARCH_PRI@_@VGCONF_OS@_vanilla=1

basic_alloc_SOURCES = basic_alloc.c
double_stores_SOURCES = double_stores.c
int_stores_SOURCES = int_stores.c
small_block_SOURCES = small_block.c
multi_alloc_SOURCES = multi_alloc.c
custom_threshold_SOURCES = custom_threshold.c
calloc_test_SOURCES = calloc_test.c
avx_stores_SOURCES = avx_stores.c
avx_stores_CFLAGS = $(AM_CFLAGS) -mavx -mavx2
random_offsets_SOURCES = random_offsets.c
stack_array_SOURCES = stack_array.c
all_types_SOURCES = all_types.c
