from worker.main import WorkerConfig, embed_faq_job, probe_embed_job, process_inbound_message


def test_worker_config_has_functions() -> None:
    assert process_inbound_message in WorkerConfig.functions
    assert embed_faq_job in WorkerConfig.functions
    assert probe_embed_job in WorkerConfig.functions


def test_worker_config_has_redis_settings() -> None:
    assert WorkerConfig.redis_settings is not None
