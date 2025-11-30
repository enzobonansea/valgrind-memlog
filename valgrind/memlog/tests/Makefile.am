dist_noinst_SCRIPTS = filter_stderr

noinst_PROGRAMS = basic_alloc

EXTRA_DIST = \
	basic_alloc.stderr.exp \
	basic_alloc.vgtest

AM_CFLAGS   = $(WERROR) -Winline -Wall -Wshadow -Wno-long-long \
              @FLAG_FNO_STACK_PROTECTOR@ $(AM_FLAG_M3264_PRI)
AM_CPPFLAGS = -I$(top_srcdir) -I$(top_srcdir)/include \
              -I$(top_srcdir)/coregrind -I$(top_builddir)/include \
              -I$(top_srcdir)/VEX/pub \
              -DVGA_@VGCONF_ARCH_PRI@=1 \
              -DVGO_@VGCONF_OS@=1 \
              -DVGP_@VGCONF_ARCH_PRI@_@VGCONF_OS@=1 \
              -DVGPV_@VGCONF_ARCH_PRI@_@VGCONF_OS@_vanilla=1

basic_alloc_SOURCES = basic_alloc.c
