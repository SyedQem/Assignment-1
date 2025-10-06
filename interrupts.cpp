/**
 *
 * @file interrupts.cpp
 * @author Qurb E Muhammad Syed 101281787
 *
 */

#include<interrupts.hpp>

int main(int argc, char** argv) {

    //vectors is a C++ std::vector of strings that contain the address of the ISR
    //delays  is a C++ std::vector of ints that contain the delays of each device
    //the index of these elemens is the device number, starting from 0
    auto [vectors, delays] = parse_args(argc, argv);
    std::ifstream input_file(argv[1]);

    std::string trace;      //!< string to store single line of trace file
    std::string execution;  //!< string to accumulate the execution output

    /******************ADD YOUR VARIABLES HERE*************************/
    const int SAVE = 10;
    const int RESTORE = 10;
    const int FIND_VECTOR = 10;
    const int GET_ISR = 1;
    const int IRET = 1;

    const int VECTOR_ENTRY_BYTES = 2;

    struct event {
        enum Type {CPU,END_IO, SYSCALL};
        Type type;
        int dur;
    };

    struct logLine {
        long long start;
        int dur;
        std::string text;
    };

    long long t = 0;
    int mode = 1;
    
    std::vector<logLine> out;
    std::vector<event> tracefile;
    std::srand(std::time(nullptr));


    const std::vector<std::string> SYSCALL_MIDDLE = {
    "validate parameters", "copy user buffer",
    "set up DMA", "enqueue request", "update file table"
    };
    const std::vector<std::string> ENDIO_MIDDLE = {
        "read status register", "copy data to kernel buffer",
        "clear device flag", "record completion"
    };
    // helper functions

    auto trace_convert = [](std::string type, int dur){
        event::Type t;

        if (type == "CPU")       t = event::CPU;
        else if (type == "END_IO") t = event::END_IO;
        else if (type == "SYSCALL") t = event::SYSCALL;
        else throw std::invalid_argument("Unknown type");

        return event{t, dur};
    };

    auto logger = [&t, &out](int dur, std::string activity){
        out.push_back({t, dur, activity});
    };

    auto emit_line = [&](long long& t, std::string& execution, int dur, const std::string& text) {
        execution += std::to_string(t) + ", " + std::to_string(dur) + ", " + text + "\n";
        t += dur;
    };

    auto split_middle_random = [&](int R, int M) -> std::vector<int> {
        std::vector<int> mids;
        if (M <= 0) return mids;
        if (M == 1) { mids.push_back(R); return mids; }

        // M == 2: random cut
        int a = 1 + (std::rand() % (R - 1)); // between 1 and R-1
        mids.push_back(a);
        mids.push_back(R - a);
        return mids;
    };

    auto pick_random_label = [&](const std::vector<std::string>& pool) -> const std::string& {
        int idx = std::rand() % pool.size();
        return pool[idx];
    };

    auto syscall_body = [&](long long& t, int dev, int delay, std::string& execution) {
        int K = (delay >= 80) ? 4 : 3;
        if (delay < K) K = delay; // clamp if delay is tiny

        // anchors
        int start = std::max(1, delay * 15 / 100);
        int end   = std::max(1, delay * 15 / 100);

        // if anchors get too big shrink
        if (start + end > delay) {
            start = std::max(1, delay - 1);
            end   = delay - start;
        }

        int M = K - 2;                 
        int R = delay - start - end;   // leftover 

        emit_line(t, execution, start, "call device driver");

        if (M == 1) {
            emit_line(t, execution, R, pick_random_label(SYSCALL_MIDDLE));
        } else if (M == 2) {
            int a = 1 + (std::rand() % (R - 1)); 
            int b = R - a;
            emit_line(t, execution, a, pick_random_label(SYSCALL_MIDDLE));
            emit_line(t, execution, b, pick_random_label(SYSCALL_MIDDLE));
        }

        emit_line(t, execution, end, "update PCB");
    };

     auto endio_body = [&](long long& t, int dev, int delay, std::string& execution) {
        int K = (delay >= 80) ? 4 : 3;
        if (delay < K) K = delay;

        int start = std::max(1, delay * 15 / 100);
        int end   = std::max(1, delay * 15 / 100);

        if (start + end > delay) {
            start = std::max(1, delay - 1);
            end   = delay - start;
        }

        int M = K - 2;
        int R = delay - start - end;

        emit_line(t, execution, start, "acknowledge device");

        if (M == 1) {
            emit_line(t, execution, R, pick_random_label(ENDIO_MIDDLE));
        } else if (M == 2) {
            int a = 1 + (std::rand() % (R - 1));
            int b = R - a;
            emit_line(t, execution, a, pick_random_label(ENDIO_MIDDLE));
            emit_line(t, execution, b, pick_random_label(ENDIO_MIDDLE));
        }

        emit_line(t, execution, end, "unblock waiting process");
    };

    // device_id -> queue of ints

    // std::unordered_map<int, std::queue<int>> device_queues;


    /******************************************************************/

    //parse each line of the input trace file
    while(std::getline(input_file, trace)) {
        auto [activity, duration_intr] = parse_trace(trace);

        /******************ADD YOUR SIMULATION CODE HERE*************************/



        /************************************************************************/

    }

    input_file.close();

    write_output(execution);

    return 0;
}
