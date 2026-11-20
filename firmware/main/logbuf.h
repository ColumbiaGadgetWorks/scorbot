// Keeps the most recent log output in RAM so the web UI can show and save it
// (Settings > Logs) without a serial cable.
#pragma once

#include <string>

namespace logbuf {

// Hooks esp_log: everything still goes to the serial port as well.
void Start();
// The buffered log, oldest line first.
std::string Text();

}  // namespace logbuf
