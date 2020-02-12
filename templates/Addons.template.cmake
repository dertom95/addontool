
list(APPEND INCLUDE_DIRS ${CMAKE_CURRENT_SOURCE_DIR}/src_addon)

{% for addon in data.values() %}
    {% for file in addon.files.files %} {% if "cmake" in file %} include("{{ file }}") {% endif %} {% endfor %}
{% endfor %}
