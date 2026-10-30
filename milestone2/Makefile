# Project 03 build. Uses system liburing if present, otherwise $(HOME)/local.
CC      ?= gcc
CFLAGS  ?= -O2 -Wall -Wextra -Werror -std=gnu11
ifeq ($(wildcard $(HOME)/local/include/liburing.h),)
  ifneq ($(wildcard $(HOME)/.local/m1-liburing-2.5/include/liburing.h),)
    LIBURING ?= $(HOME)/.local/m1-liburing-2.5
  endif
endif
LOCAL   := $(HOME)/local
ifneq ($(wildcard $(LOCAL)/include/liburing.h),)
  CFLAGS  += -I$(LOCAL)/include
  LDFLAGS += -L$(LOCAL)/lib -Wl,-rpath,$(LOCAL)/lib
endif
ifdef LIBURING
  CFLAGS  += -I$(LIBURING)/include
  LDFLAGS += -L$(LIBURING)/lib -Wl,-rpath,$(LIBURING)/lib
endif

all: bin/dispatcher

bin/smoke_test: src/smoke_test.c
	@mkdir -p bin
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS) -luring

bin/dispatcher: src/dispatcher.c src/dispatcher.h src/submission.h
	@mkdir -p bin
	$(CC) $(CFLAGS) -o $@ src/dispatcher.c $(LDFLAGS) -luring

bin/test_submission: tests/test_submission.c src/submission.h
	@mkdir -p bin
	$(CC) $(CFLAGS) -Isrc -o $@ tests/test_submission.c

test-unit: bin/test_submission
	./bin/test_submission

test: all test-unit
	python3 -m unittest discover -s analysis -p 'test_*.py'
	python3 -m unittest discover -s tests -p 'test_dispatcher.py' -v

clean:
	rm -rf bin

.PHONY: all test test-unit clean
