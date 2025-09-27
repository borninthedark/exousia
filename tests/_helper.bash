# tests/_helper.bash

# Set fallback if CI didn't set it
export BATS_LIB_PATH=${BATS_LIB_PATH:-"/usr/lib"}

# Load bats libraries
bats_load_library bats-support
bats_load_library bats-assert
bats_load_library bats-file
bats_load_library bats-detik/detik.bash
