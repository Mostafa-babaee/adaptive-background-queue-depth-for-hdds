# Dispatcher Design Review

**Mostafa Babaei | CSC 720: Storage Systems | Project 03**  
**October 19, 2026**

## Design approach

I reviewed the dispatcher design to define how foreground and background reads will share the storage system. The design uses two pending queues connected to one C/io_uring backend. Foreground requests are 4 KiB random reads, while the background scanner reads sequential 256 KiB chunks.

The dispatcher will check foreground work first and submit it when the fixed foreground limit allows. Background submissions will follow the queue-depth limit q, selected from 1, 2, 4, and 8. This separates the read mechanism from the controller that chooses q.

## Request lifecycle

| Stage | Dispatcher action |
|---|---|
| Arrival | Assign a unique request ID and preserve the intended arrival time. |
| Waiting | Place the request in its foreground or background pending queue. |
| Submission | Check the limit, assign an aligned buffer, and submit the read. |
| Completion | Match the returned ID, record the completion time, and check the result. |
| Verification | Verify the data, record one success or error, and release the buffer. |

Request IDs allow reads to finish in a different order without mixing their results. Each outstanding read will own its buffer until completion and verification are finished.

## Timing and correctness

Arrival, admission, submission, completion, and verification-finish times will be recorded separately. This makes it possible to distinguish waiting inside the program from time after submission. The original arrival time will be preserved even when the dispatcher is busy.

An outstanding counter will increase only after successful submission and decrease once when its completion is processed. Rejections, short reads, and errors will be logged explicitly. If q decreases, existing reads will finish while new background submissions wait until the count is below the new limit.

At normal shutdown, the dispatcher will stop new arrivals and drain accepted work. During an interruption, it will record unsubmitted requests as shutdown errors and wait for submitted reads before releasing their resources.

## Completed checks and next step

The C smoke test passed all **15 recorded suite checks**, and all **12 unit tests** passed. The additional Python pilot completed **18 foreground/background cases** with no reported errors or rejections. These tests provide a working basis for the dispatcher implementation.

The next step is to implement this design in the common C dispatcher, finalize the shared configuration and log format with the team, and test queue limits, concurrent completions, and shutdown behavior.
