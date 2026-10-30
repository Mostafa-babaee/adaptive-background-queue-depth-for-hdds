# Project 03 build. Uses system liburing if present, otherwise $(HOME)/local.
CC      ?= gcc
CFLAGS  ?= -O2 -Wall -Wextra -std=gnu11
LOCAL   := $(HOME)/local
ifneq ($(wildcard $(LOCAL)/include/liburing.h),)
  CFLAGS  += -I$(LOCAL)/include
  LDFLAGS += -L$(LOCAL)/lib -Wl,-rpath,$(LOCAL)/lib
endif
ifdef LIBURING
  CFLAGS  += -I$(LIBURING)/include
  LDFLAGS += -L$(LIBURING)/lib -Wl,-rpath,$(LIBURING)/lib
endif

all: bin/smoke_test bin/dispatcher

bin/smoke_test: src/smoke_test.c
	@mkdir -p bin
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS) -luring

bin/dispatcher: src/dispatcher.c src/dispatcher.h
	@mkdir -p bin
	$(CC) $(CFLAGS) -o $@ src/dispatcher.c $(LDFLAGS) -luring

test: all
	python3 -m unittest discover -s analysis -p 'test_*.py'
	python3 -m unittest tests/test_dispatcher.py -v

clean:
	rm -rf bin

.PHONY: all test clean
