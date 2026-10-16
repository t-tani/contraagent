{#- One release: `### <type>` per type with fragments, in the order of [[tool.towncrier.type]], one bullet per fragment. -#}
{% for section, _ in sections.items() %}
{% for category, val in definitions.items() if category in sections[section] and sections[section][category] %}

### {{ definitions[category]['name'] }}

{% for text, values in sections[section][category].items() %}
- {{ text }}
{% endfor %}
{% endfor %}
{% endfor %}
