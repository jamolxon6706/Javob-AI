from worker.main import WorkerConfig, process_inbound_message


def test_worker_config_has_functions() -> None:
    assert process_inbound_message in WorkerConfig.functions


def test_worker_config_has_redis_settings() -> None:
    assert WorkerConfig.redis_settings is not None
