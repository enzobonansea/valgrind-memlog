#!/bin/bash

# Repository version information (will be updated during CI build)
MAIN_REPO_COMMIT="MAIN_COMMIT_PLACEHOLDER"

# Display version information
echo "===== Repository Information ====="
echo "memlog commit: $MAIN_REPO_COMMIT"
echo "Build tag: memlog-${MAIN_REPO_COMMIT}"

echo -e "\n"
while true; do
    echo "Select an option:"
    echo "1. Analyze example"
    echo "2. Analyze SPEC fprate"
    echo "3. Analyze SPEC app"
    echo "4. Analyze generic app (absolute path must start with /usr)"
    echo "5. Run bash"
    echo "6. Exit"

    read -p "Enter your choice: " choice

    case $choice in
        1)
            echo "Analyzing example..."
            /usr/local/bin/analyze.sh /usr/alloc
            /bin/bash
            ;;
        2)
            /usr/local/bin/analyze.sh fprate
            /bin/bash
            ;;
        3)
            read -p "Enter SPEC app name: " app_name
            if [ -n "$app_name" ]; then
                /usr/local/bin/analyze.sh "spec:$app_name"
            else
                echo "No app name provided."
            fi
            /bin/bash
            ;;
        4)
            read -p "Enter executable path: " executable_path
            if [ -n "$executable_path" ]; then
                echo "Analyzing $executable_path ..."
                /usr/local/bin/analyze.sh $executable_path
            else
                echo "No executable path provided."
            fi
            /bin/bash
            ;;
        5)
            bash
            exit 0
            ;;
        6)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid option."
            ;;
    esac
done
