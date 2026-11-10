CC ?= cc
CFLAGS ?= -O3 -std=c11 -fPIC -fvisibility=hidden -Wall -Wextra

.PHONY: native clean
native: libmiaomiao.so
libmiaomiao.so: native/core.c
	$(CC) $(CFLAGS) -shared -o $@ $<
clean:
	rm -f libmiaomiao.so
