def test_module_importable():
    import api.middleware.audit_log
    assert hasattr(api.middleware.audit_log, "audit_log_middleware")
