`contraagent monitor --base-path /monitor` and `contraagent hub --base-path /monitor`
serve the monitor behind a reverse proxy that serves it under `/monitor/` of a site and
takes that path off. The page names the base path in every URL it reads
(`<ca-monitor base-url="/monitor">`, its script and icons), so the page, the API and the
live feeds pass the proxy with no change to the HTML. The API documentation and the
`servers` of the OpenAPI document name it too, and a hub's `/login` redirects to it and
sets its cookie for it. A value that is not a plain path ends the command with exit
status 2. `create_app(base_path=)` and `serve(base_path=)` in `contraagent.monitor` take
the same. The monitor topic (`contraagent docs monitor`) shows an nginx configuration
and what a proxy needs for the live feeds and the `Host` check.
