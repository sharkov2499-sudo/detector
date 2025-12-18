While working on this test task, I discovered that LLMs can understand combinational logic very well, and this kind of tasks are too easy, so I decided to test module with more complex inner structure, something that uses finite state machine. So I chose sequence detector. This kind of module could be used in various cases, such as:
Communication (preambula detection for synchronization of transmitter and receiver)
Security systems (sequence detection for activating function or reset)
and etc.

This module should be part of a bigger system, so it's basically a trigger mechanism, transitioning the entire system from one state to another.

In this particular case, to detect 7-bit consequence this module uses 8 states (S0..S7). S0 - "zero state", S7 - "sequence detected" state. At the state S0 detector waits of the start of the sequence and transit to a state S1, then if the input bit is equal to second bit of targeted sequency, detector transit to the state S2, if not - reset to S0. Every state has its own transition pattern. If detector transited to the state S7, that means that the sequence is detected, and output signal is high.