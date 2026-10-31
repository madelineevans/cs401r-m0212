def test_lab4_intentional_ci_failure_demo():
    """Deliberately fail once to verify CodeBuild's PRE_BUILD gate and alarm."""
    assert False, "Lab 4 failure demonstration: this test must fail in PRE_BUILD"
