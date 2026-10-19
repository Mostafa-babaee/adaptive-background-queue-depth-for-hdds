# Mostafa's Presentation Notes

Use the paragraphs below as your speaking script. The language is kept simple, so you can explain the work comfortably. Read the ideas naturally rather than memorizing every word.

## Slide 1 - Introduction

Hello everyone. My name is Mostafa Babaei. I will present my part of our first milestone for the storage systems project.

My work focused on checking the programming tools, running and verifying asynchronous reads, and reviewing the dispatcher design. I will also show a small foreground and background test that I completed as extra work.

## Slide 2 - Development tools

First, I connected to Babbage and checked the tools we need. GCC, Make, and Python were available. The main issue was that the compiler could not find the liburing development files.

I built liburing version 2.5 and installed it in my own account, without sudo. I also fixed a compiler flag that was causing errors in the library headers. After that, the C read test compiled successfully.

This gave us a working environment for testing the read operations.

## Slide 3 - C read smoke test

My first test was a small C program using io_uring. The program opens a known test file for direct reads and uses an aligned memory buffer.

Each read has a request ID. When the read finishes, the program checks the ID, the number of bytes returned, and every byte of the data. The expected contents come from a known pattern.

This output shows a successful 256-KiB read. The program keeps one read outstanding at a time. The purpose was to confirm that the read and verification steps work correctly.

## Slide 4 - Correctness results

All twelve unit tests and all fifteen smoke-suite checks passed.

The unit tests checked the pattern generator and the test-runner logic. The smoke suite checked compilation, reads at different offsets and sizes, repeated reads, and whether the original file stayed unchanged.

Some tests deliberately used invalid inputs, an empty file, or corrupted data. For those cases, passing means that the program detected the expected problem. It does not mean that an incorrect read was accepted.

I saved the summaries and individual logs as evidence.

## Slide 5 - Multiple outstanding reads

Queue depth means how many reads have been submitted but have not yet completed. A depth of one allows one outstanding read. A depth of eight allows up to eight.

The purpose of a multiple-read check is to make sure the program can track the requests and verify the returned data while more than one read is active.

The measurements shown here should be treated as early checks. Our main project comparison will study foreground response time and background progress together.

**Preparation reminder, not spoken:** This slide references a second C program, larger files, and `results/m1_smoke.txt`. Those source files/logs were not in the workspace reviewed here. Keep this slide only if you have verified that evidence. Otherwise, skip it; the other slides already cover your confirmed work. Do not describe the separate Python pilot as this C test.

## Slide 6 - HDD arranged with the department

I contacted Brian Hays from the university's IT support team to arrange a physical HDD for our project.

He confirmed that a five-hundred-gigabyte hard drive has been installed in a university computer. This gives us a physical HDD for the next stage of testing.

Our next step is to check access, set up the software, and run the foreground and background experiments.

## Slide 7 - Dispatcher design

For the dispatcher, I reviewed a design with two pending queues. One holds the small foreground reads, and the other holds the sequential background reads. Both queues feed the same io_uring backend.

The dispatcher will use a fixed foreground limit and a background limit called q. It will keep request IDs, timestamps, and a separate buffer for each outstanding read.

When a read completes, the dispatcher will match its ID, check the result, and verify the data before reusing the buffer.

If q decreases, reads already submitted will continue. New background reads will wait until the outstanding count is below the new limit. This is the reviewed design for the full C dispatcher, which we will implement next.

## Slide 8 - Additional foreground/background pilot

As extra work, I ran a separate Python pilot using worker threads and direct reads. This is different from the C io_uring program.

I tested foreground reads alone, background reads alone, and both together at four background depths. I repeated the six conditions three times, giving eighteen cases. All cases finished without reported errors or foreground rejections.

The graph shows the p99 from each repetition separately. There was no consistent winner across the depths. Background throughput stayed close to the configured rate limit.

Because the file was small and the runs were short, these are preliminary observations. They helped check the concurrent workload logic, but they do not identify the best queue depth.

That completes my part. The next step is to build the full dispatcher and connect it to the controller and workload generator. Thank you.

---

## Before presenting

- Slide 6 now uses general information about the installed HDD and IT support, without the date or exact computer location.
- For slide 2, use the title **Development tools and read-test setup**. Only discuss the Python-package installation if you have confirmed it actually completed. libaio was not found through pkg-config; do not state it was definitely absent.
- Confirm the cover's deadline with the course page.
- If Tariq combines the team deck, you should still present and record your own section.

## Short answers for likely questions

**What does q mean?**  
It is the maximum number of background reads we allow to remain outstanding in the C design. In the Python pilot, it limits outstanding worker jobs.

**Did you already implement the full dispatcher?**  
The C smoke test is complete, and the design review is written. The full two-queue C dispatcher is the next step.

**Why can a negative test pass?**  
Because we expected an error, and the program detected the correct error instead of reporting success.

**What does p99 mean here?**  
It is a latency percentile calculated from the measured requests. Our short runs have few samples, so these p99 values are only preliminary.

**Is the new HDD ready for experiments?**  
Brian confirmed the drive installation. We still need to check access and set up our software on that computer.
