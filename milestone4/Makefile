# Project 03 build (Milestone 3). Uses system liburing if present, otherwise $(HOME)/local.
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

all: bin/dispatcher bin/ctrl_replay

bin/smoke_test: src/smoke_test.c
	@mkdir -p bin
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS) -luring

bin/dispatcher: src/dispatcher.c src/dispatcher.h src/submission.h src/controller.c src/controller.h src/rl_policy.c src/rl_policy.h src/rl_table.h
	@mkdir -p bin
	$(CC) $(CFLAGS) -o $@ src/dispatcher.c src/controller.c src/rl_policy.c $(LDFLAGS) -luring -lm

# Milestone 3: controller unit tests and a replay tool (no disk, no liburing)
bin/test_controller: tests/test_controller.c src/controller.c src/controller.h
	@mkdir -p bin
	$(CC) $(CFLAGS) -Isrc -o $@ tests/test_controller.c src/controller.c -lm

bin/ctrl_replay: tools/ctrl_replay.c src/controller.c src/controller.h
	@mkdir -p bin
	$(CC) $(CFLAGS) -Isrc -o $@ tools/ctrl_replay.c src/controller.c -lm

# Milestone 4: RL policy unit tests (no disk, no liburing)
bin/test_rl: tests/test_rl.c src/rl_policy.c src/rl_policy.h src/rl_table.h src/controller.c src/controller.h
	@mkdir -p bin
	$(CC) $(CFLAGS) -Isrc -o $@ tests/test_rl.c src/rl_policy.c src/controller.c -lm

bin/test_submission: tests/test_submission.c src/submission.h
	@mkdir -p bin
	$(CC) $(CFLAGS) -Isrc -o $@ tests/test_submission.c

test-unit: bin/test_submission bin/test_controller bin/test_rl
	./bin/test_submission
	./bin/test_controller
	./bin/test_rl

test: all test-unit
	python3 -m unittest discover -s analysis -p 'test_*.py'
	python3 -m unittest discover -s tests -p 'test_dispatcher.py' -v
	python3 -m unittest discover -s tests -p 'test_adaptive.py' -v

clean:
	rm -rf bin

.PHONY: all test test-unit clean
