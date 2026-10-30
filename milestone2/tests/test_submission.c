#include <assert.h>
#include <stdio.h>
#include "submission.h"
struct fixture { int returns[8]; unsigned calls, seen[8]; };
static int submit(void *p) { struct fixture *f=p; assert(f->calls<8); return f->returns[f->calls++]; }
static void accepted(void *p,unsigned first,unsigned count) {
    struct fixture *f=p;
    for(unsigned i=first;i<first+count;i++) { assert(i<8); f->seen[i]++; }
}
int main(void) {
    struct fixture full={{4},0,{0}};
    assert(!m2_flush_batch(4,submit,accepted,&full));
    assert(full.calls==1);
    for(unsigned i=0;i<4;i++) assert(full.seen[i]==1);
    struct fixture partial={{1,2,1},0,{0}};
    assert(!m2_flush_batch(4,submit,accepted,&partial));
    assert(partial.calls==3);
    for(unsigned i=0;i<4;i++) assert(partial.seen[i]==1);
    struct fixture interrupted={{-EINTR,1,-EINTR,2,1},0,{0}};
    assert(!m2_flush_batch(4,submit,accepted,&interrupted));
    for(unsigned i=0;i<4;i++) assert(interrupted.seen[i]==1);
    struct fixture zero={{0},0,{0}};
    assert(m2_flush_batch(4,submit,accepted,&zero)<0);
    struct fixture failure={{-EIO},0,{0}};
    assert(m2_flush_batch(4,submit,accepted,&failure)<0);
    struct fixture overflow={{5},0,{0}};
    assert(m2_flush_batch(4,submit,accepted,&overflow)<0);
    struct fixture later_failure={{2,-EIO},0,{0}};
    assert(m2_flush_batch(4,submit,accepted,&later_failure)<0);
    assert(later_failure.seen[0]==1 && later_failure.seen[1]==1 && !later_failure.seen[2]);
    struct fixture empty={{0},0,{0}};
    assert(!m2_flush_batch(0,submit,accepted,&empty) && empty.calls==0);
    puts("PASS: 8 submission-batch scenarios");
    return 0;
}
