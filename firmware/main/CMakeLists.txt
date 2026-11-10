idf_component_register(
    SRCS "main.cpp" "hal_esp32.cpp" "settings.cpp" "api.cpp" "net.cpp" "web.cpp" "ota.cpp"
         "core/robot.cpp" "core/config.cpp"
    INCLUDE_DIRS "."
    EMBED_TXTFILES "../web/index.html"
    PRIV_REQUIRES driver esp_http_server app_update esp_https_ota esp_http_client mbedtls esp_wifi esp_netif esp_event nvs_flash json esp_timer lwip)
