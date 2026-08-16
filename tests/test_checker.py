import sys
import os
import pandas as pd

# Add src to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.checker import run_checker

def test_checker_all_matching_cases():
    cases_df = pd.read_csv("data/cases.csv")
    unmatched = [
        row["case_id"]
        for _, row in cases_df.iterrows()
        if run_checker(row["show_outputs"]) is None
    ]
    assert unmatched == []
    
    # NET-001
    net001 = cases_df[cases_df["case_id"] == "NET-001"].iloc[0]
    res001 = run_checker(net001["show_outputs"])
    assert res001 is not None
    assert res001["source"] == "checker"
    assert "GigabitEthernet0/0.30" in res001["root_cause"]
    assert res001["osi_layer"] == "Data Link"
    
    # NET-003
    net003 = cases_df[cases_df["case_id"] == "NET-003"].iloc[0]
    res003 = run_checker(net003["show_outputs"])
    assert res003 is not None
    assert res003["source"] == "checker"
    assert "FastEthernet0/3" in res003["root_cause"]
    assert res003["osi_layer"] == "Physical"
    
    # NET-004
    net004 = cases_df[cases_df["case_id"] == "NET-004"].iloc[0]
    res004 = run_checker(net004["show_outputs"])
    assert res004 is not None
    assert res004["source"] == "checker"
    assert "VLAN 20" in res004["root_cause"]
    assert res004["osi_layer"] == "Data Link"
    
    # NET-005
    net005 = cases_df[cases_df["case_id"] == "NET-005"].iloc[0]
    res005 = run_checker(net005["show_outputs"])
    assert res005 is not None
    assert res005["source"] == "checker"
    assert "ACL 110" in res005["root_cause"]
    assert res005["osi_layer"] == "Network"
    
    # NET-006
    net006 = cases_df[cases_df["case_id"] == "NET-006"].iloc[0]
    res006 = run_checker(net006["show_outputs"])
    assert res006 is not None
    assert res006["source"] == "checker"
    assert "0.0.0.3" in res006["root_cause"]
    assert res006["osi_layer"] == "Network"
    
    # NET-007
    net007 = cases_df[cases_df["case_id"] == "NET-007"].iloc[0]
    res007 = run_checker(net007["show_outputs"])
    assert res007 is not None
    assert res007["source"] == "checker"
    assert "Missing default route" in res007["root_cause"]
    assert res007["osi_layer"] == "Network"

    # NET-011 (STP blocking - expected behavior, now handled as a no-fix rule)
    net011 = cases_df[cases_df["case_id"] == "NET-011"].iloc[0]
    res011 = run_checker(net011["show_outputs"])
    assert res011 is not None
    assert res011["source"] == "checker"
    assert "expected behavior" in res011["root_cause"]
