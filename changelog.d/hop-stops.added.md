A failover hop can name the stops it is for: `stops = ["rate_limited", "api_error"]` in a
`[[defaults.fallbacks]]` or `[[tasks.<kind>.fallbacks]]` block (`Route.stops`). A task whose
launch ends on another stop passes the hop over, a 429 opens the breaker only onto a hop for
`rate_limited`, and a safety stop moves the task to a hop for `refused`. With no hop left for
its stop, the launch's own stop stands. A block without `stops` is for every stop, as before.
