from noema.routing import select_executor


def test_deterministic_preference_and_fallback():
    executors = [
        {"id":"a","status":"verified","capabilities":["repo"],"interfaces":["github"],"modalities":["code"]},
        {"id":"b","status":"verified","capabilities":["repo"],"interfaces":["github"],"modalities":["code"]},
    ]
    route = {"prefer":["a"],"fallback":["b"]}
    result = select_executor({"capabilities":["repo"],"interfaces":["github"]}, executors, route, {"a":{"enabled":False}})
    assert result["status"] == "ROUTED"
    assert result["executor"] == "b"


def test_unverified_executor_is_blocked():
    executors = [{"id":"a","status":"needs-verification","capabilities":["repo"],"interfaces":[],"modalities":[]}]
    result = select_executor({"capabilities":["repo"]}, executors, {"prefer":["a"],"fallback":[]}, {})
    assert result["status"] == "BLOCKED_NO_VERIFIED_EXECUTOR"
