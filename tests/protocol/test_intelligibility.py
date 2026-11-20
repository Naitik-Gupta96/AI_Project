from ai_project.protocol import Level, agent_level, classify


def test_paper_degenerate_strong_example():
    # 2410.20600 footnote: <INIT_m, RATIFY_h, RATIFY_m> is Strong for the machine
    report = classify([("m", "INIT"), ("h", "RATIFY"), ("m", "RATIFY")])
    assert report.per_agent == {"m": Level.STRONG, "h": Level.STRONG}
    assert report.session == Level.STRONG


def test_ultra_strong_needs_a_revise():
    assert agent_level(["RATIFY", "REVISE"]) == Level.ULTRA_STRONG
    assert agent_level(["REVISE"]) == Level.ULTRA_STRONG
    assert agent_level(["RATIFY", "RATIFY"]) == Level.STRONG


def test_one_way_allows_refute_but_not_reject():
    assert agent_level(["REFUTE", "RATIFY"]) == Level.ONE_WAY
    assert agent_level(["REFUTE", "RATIFY", "REJECT"]) == Level.NONE
    assert agent_level(["REFUTE"]) == Level.NONE


def test_init_alone_is_not_intelligible():
    assert agent_level(["INIT"]) == Level.NONE


def test_session_level_is_the_weakest_speaking_agent():
    report = classify([("a", "INIT"), ("b", "REVISE"), ("c", "REFUTE"), ("a", "RATIFY"),
                       ("c", "RATIFY"), ("b", "RATIFY")])
    assert report.per_agent == {"a": Level.STRONG, "b": Level.ULTRA_STRONG, "c": Level.ONE_WAY}
    assert report.session == Level.ONE_WAY
    assert report.to_dict()["session"] == "One-Way"


def test_agent_with_only_init_does_not_lower_the_session():
    report = classify([("a", "INIT"), ("b", "RATIFY")])
    assert report.session == Level.STRONG
