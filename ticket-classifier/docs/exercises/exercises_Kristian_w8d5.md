# W08 D5 - Observability

## Why do we need it?

- better logging
- monitoring an agentic system (inspect errors and reconstruct history)
- information in checkpoints does not contain metadata: when it was started, how long did it run, how many tokens were spent, (who started it, which machine did it run on) ...
- do not litter nodes with print() or logging.info()
- we want to use a standard protocol (Open Telemetry Standard)
- we might want to store the trace (log messages) somewhere else

## Term

telemetry data == trace == log info for agents

## Usage scenarios

1. we want to have a dashboard that other people can access (separation of concerns)
2. agent server gets hacked or crashes, I still want to inspect the trace
3. benchmarking
4. you run 2 agent servers and collect traces in 1 place
5. supervision (bias, improper use, attacks, ...)

## ???

- What is a span???

## TODO:

- add OpenTelemetry to our workflow
- use the TraceVerde / OpenTelemetry SDK library
- implement the wrapper / decorator
- try to make TraceVerde print to the console instead of sending by HTTP
- measure performance (timing, structure) of notes
- measure token usage
- generate checkpoint history
- read the telemetry data
- no cloud access for the telemetry required
- raise an error on pause (human in the loop)
----
- install docker
- start jaeger container with "docker compose up"
- visit the page: http://127.0.0.1:16686
- show telemetry data on a dashboard

- make jaeger container keep stuff across runs (add docker volume)