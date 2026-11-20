#include "logbuf.h"

#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cstring>

#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"

namespace logbuf {
namespace {

constexpr size_t kSize = 12 * 1024;
char g_ring[kSize];
size_t g_head = 0;   // next write position
bool g_wrapped = false;
portMUX_TYPE g_mux = portMUX_INITIALIZER_UNLOCKED;
vprintf_like_t g_prev = nullptr;

int Hook(const char* fmt, va_list args) {
  va_list copy;
  va_copy(copy, args);
  char line[200];
  int n = std::vsnprintf(line, sizeof(line), fmt, copy);
  va_end(copy);
  if (n > 0) {
    size_t len = std::min(static_cast<size_t>(n), sizeof(line) - 1);
    // strip the ANSI colour codes esp_log adds for terminals
    size_t w = 0;
    for (size_t r = 0; r < len; ++r) {
      if (line[r] == '\033') {
        while (r < len && line[r] != 'm') ++r;
        continue;
      }
      line[w++] = line[r];
    }
    portENTER_CRITICAL(&g_mux);
    for (size_t i = 0; i < w; ++i) {
      g_ring[g_head] = line[i];
      if (++g_head == kSize) {
        g_head = 0;
        g_wrapped = true;
      }
    }
    portEXIT_CRITICAL(&g_mux);
  }
  return g_prev ? g_prev(fmt, args) : std::vprintf(fmt, args);
}

}  // namespace

void Start() { g_prev = esp_log_set_vprintf(Hook); }

std::string Text() {
  std::string out;
  out.reserve(kSize);
  portENTER_CRITICAL(&g_mux);
  const size_t head = g_head;
  const bool wrapped = g_wrapped;
  portEXIT_CRITICAL(&g_mux);
  // A line may be written while we copy; at worst one line is torn.
  if (wrapped) out.append(g_ring + head, kSize - head);
  out.append(g_ring, head);
  if (wrapped) {
    const size_t nl = out.find('\n');
    if (nl != std::string::npos) out.erase(0, nl + 1);  // drop the partial first line
  }
  return out;
}

}  // namespace logbuf
