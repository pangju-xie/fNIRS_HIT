set(src_dirs
            "."
            )

set(include_dirs
            "include"
            )

set(requires  driver esp_wifi nvs_flash esp_event esp_http_server)

idf_component_register(SRC_DIRS ${src_dirs} INCLUDE_DIRS ${include_dirs} REQUIRES ${requires} EMBED_FILES "index.html" )
component_compile_options(-ffast-math -O3 -Wno-error=format=-Wno-format)
