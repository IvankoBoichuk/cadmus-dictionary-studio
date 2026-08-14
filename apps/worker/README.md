# Worker application

Background-job entrypoints for long-running processing. The worker uses the
same backend application and domain modules as the API while Celery remains a
thin infrastructure adapter.

Run Redis and the worker through the standard local environment:

~~~bash
docker compose up --build redis worker
~~~

Or run Redis in Compose and the worker on the host:

~~~bash
make redis-up
make worker
~~~

The infrastructure smoke task is named `cadmus.processing.test`. Worker log
events are JSON objects containing an `event` and Celery `task_id`; task
arguments and results are deliberately excluded from info-level logs.
