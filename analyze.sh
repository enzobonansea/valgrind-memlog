#!/bin/bash

# Check if an argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <executable|fprate|spec:benchmark>"
    echo "Examples:"
    echo "  $0 /usr/alloc          # Analyze a specific executable"
    echo "  $0 fprate              # Run SPEC CPU fprate suite"
    echo "  $0 spec:503.bwaves_r   # Run specific SPEC benchmark"
    exit 1
fi

ARG="$1"

# Check if running SPEC CPU fprate
if [ "$ARG" = "fprate" ]; then
    echo "Running SPEC CPU fprate suite with memlog..."
    cd /usr/cpu2017
    . ./shrc
    runcpu --action=run --config=memlog-monitor.cfg --size=test fprate
    exit $?
fi

# Check if running a specific SPEC benchmark (spec:benchmark_name)
if [[ "$ARG" == spec:* ]]; then
    BENCHMARK="${ARG#spec:}"
    echo "Running SPEC CPU benchmark: $BENCHMARK with memlog..."
    cd /usr/cpu2017
    . ./shrc
    runcpu --action=run --config=memlog-monitor.cfg --size=test "$BENCHMARK"
    exit $?
fi

# Otherwise, treat as an executable path
EXECUTABLE="$ARG"

# Check if the executable exists and is executable
if [ ! -x "$EXECUTABLE" ]; then
    echo "Error: $EXECUTABLE is not executable or does not exist"
    exit 1
fi

# Extract the executable name (basename)
EXECUTABLE_NAME=$(basename "$EXECUTABLE")

# Generate timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create log file path
LOG_FILE="/tmp/${EXECUTABLE_NAME}-${TIMESTAMP}.log"

echo "Running valgrind on $EXECUTABLE..."
echo "Log file: $LOG_FILE"

# Run valgrind with memlog tool
/opt/valgrind/inst/bin/valgrind --tool=memlog --min-block-size=4096 --log-file="$LOG_FILE" -- "$EXECUTABLE"

# Check if valgrind ran successfully
if [ $? -eq 0 ]; then
    echo "Valgrind completed successfully. Parsing log file..."

    # Run the parser
    /usr/parser.py "$LOG_FILE"

    echo "Analysis complete. Log file: $LOG_FILE"
else
    echo "Valgrind failed to run"
    exit 1
fi
