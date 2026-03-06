import uuid


class EagerResult:
    """Minimal AsyncResult-like object for local fallback execution."""

    def __init__(self, result=None, exception=None):
        self.id = str(uuid.uuid4())
        self.result = result
        self._exception = exception
        self.state = "FAILURE" if exception is not None else "SUCCESS"

    def get(self, timeout=None, propagate=True):
        if self._exception is not None and propagate:
            raise self._exception
        return self.result

    def successful(self):
        return self._exception is None


class _Request:
    retries = 0


class _BoundTask:
    request = _Request()

    def retry(self, exc=None, countdown=None):
        if exc is not None:
            raise exc
        raise RuntimeError("Task retry requested in local fallback mode")


def shared_task(*decorator_args, **decorator_kwargs):
    """Fallback replacement for celery.shared_task when Celery is unavailable."""

    bind = decorator_kwargs.get("bind", False)

    def decorate(func):
        def run(*args, **kwargs):
            if bind:
                return func(_BoundTask(), *args, **kwargs)
            return func(*args, **kwargs)

        def delay(*args, **kwargs):
            try:
                return EagerResult(result=run(*args, **kwargs))
            except Exception as exc:
                return EagerResult(exception=exc)

        def apply_async(args=None, kwargs=None, **options):
            args = args or ()
            kwargs = kwargs or {}
            return delay(*args, **kwargs)

        run.delay = delay
        run.apply_async = apply_async
        run.name = getattr(func, "__name__", "task")
        return run

    if decorator_args and callable(decorator_args[0]) and len(decorator_args) == 1 and not decorator_kwargs:
        return decorate(decorator_args[0])

    return decorate
