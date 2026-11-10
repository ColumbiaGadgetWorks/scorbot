# Scorbot ER-4u controller firmware. Build with ESP-IDF 5.3+:
#   idf.py set-target esp32 && idf.py build flash monitor
cmake_minimum_required(VERSION 3.16)
# Firmware version (shown in Settings, compared for OTA updates): set by
# flasher/build_firmware.py; otherwise ESP-IDF uses `git describe`.
if(DEFINED ENV{SCORBOT_VERSION})
  set(PROJECT_VER "$ENV{SCORBOT_VERSION}")
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(scorbot_controller)
