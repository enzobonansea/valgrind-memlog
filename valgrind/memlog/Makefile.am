include $(top_srcdir)/Makefile.tool.am

#----------------------------------------------------------------------------
# Headers
#----------------------------------------------------------------------------

noinst_HEADERS = \
	memlog.h \
	rbtree.h

#----------------------------------------------------------------------------
# memlog-<platform>
#----------------------------------------------------------------------------

noinst_PROGRAMS  = memlog-@VGCONF_ARCH_PRI@-@VGCONF_OS@
if VGCONF_HAVE_PLATFORM_SEC
noinst_PROGRAMS += memlog-@VGCONF_ARCH_SEC@-@VGCONF_OS@
endif

MEMLOG_SOURCES_COMMON = \
	ml_main.c \
	rbtree.c

memlog_@VGCONF_ARCH_PRI@_@VGCONF_OS@_SOURCES      = \
	$(MEMLOG_SOURCES_COMMON)
memlog_@VGCONF_ARCH_PRI@_@VGCONF_OS@_CPPFLAGS     = \
	$(AM_CPPFLAGS_@VGCONF_PLATFORM_PRI_CAPS@)
memlog_@VGCONF_ARCH_PRI@_@VGCONF_OS@_CFLAGS       = $(LTO_CFLAGS) \
	$(AM_CFLAGS_@VGCONF_PLATFORM_PRI_CAPS@)
memlog_@VGCONF_ARCH_PRI@_@VGCONF_OS@_DEPENDENCIES = \
	$(TOOL_DEPENDENCIES_@VGCONF_PLATFORM_PRI_CAPS@)
memlog_@VGCONF_ARCH_PRI@_@VGCONF_OS@_LDADD        = \
	$(TOOL_LDADD_@VGCONF_PLATFORM_PRI_CAPS@)
memlog_@VGCONF_ARCH_PRI@_@VGCONF_OS@_LDFLAGS      = \
	$(TOOL_LDFLAGS_@VGCONF_PLATFORM_PRI_CAPS@)
memlog_@VGCONF_ARCH_PRI@_@VGCONF_OS@_LINK = \
	$(top_builddir)/coregrind/link_tool_exe_@VGCONF_OS@ \
	@VALT_LOAD_ADDRESS_PRI@ \
	$(LINK) \
	$(memlog_@VGCONF_ARCH_PRI@_@VGCONF_OS@_CFLAGS) \
	$(memlog_@VGCONF_ARCH_PRI@_@VGCONF_OS@_LDFLAGS)

if VGCONF_HAVE_PLATFORM_SEC
memlog_@VGCONF_ARCH_SEC@_@VGCONF_OS@_SOURCES      = \
	$(MEMLOG_SOURCES_COMMON)
memlog_@VGCONF_ARCH_SEC@_@VGCONF_OS@_CPPFLAGS     = \
	$(AM_CPPFLAGS_@VGCONF_PLATFORM_SEC_CAPS@)
memlog_@VGCONF_ARCH_SEC@_@VGCONF_OS@_CFLAGS       = $(LTO_CFLAGS) \
	$(AM_CFLAGS_@VGCONF_PLATFORM_SEC_CAPS@)
memlog_@VGCONF_ARCH_SEC@_@VGCONF_OS@_DEPENDENCIES = \
	$(TOOL_DEPENDENCIES_@VGCONF_PLATFORM_SEC_CAPS@)
memlog_@VGCONF_ARCH_SEC@_@VGCONF_OS@_LDADD        = \
	$(TOOL_LDADD_@VGCONF_PLATFORM_SEC_CAPS@)
memlog_@VGCONF_ARCH_SEC@_@VGCONF_OS@_LDFLAGS      = \
	$(TOOL_LDFLAGS_@VGCONF_PLATFORM_SEC_CAPS@)
memlog_@VGCONF_ARCH_SEC@_@VGCONF_OS@_LINK = \
	$(top_builddir)/coregrind/link_tool_exe_@VGCONF_OS@ \
	@VALT_LOAD_ADDRESS_SEC@ \
	$(LINK) \
	$(memlog_@VGCONF_ARCH_SEC@_@VGCONF_OS@_CFLAGS) \
	$(memlog_@VGCONF_ARCH_SEC@_@VGCONF_OS@_LDFLAGS)
endif
