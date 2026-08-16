import sys
import os
import pandas as pd

# Add src to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import diagnose

def test_engine_diagnose_sample_cases():
    # Test NET-001 (should resolve via checker)
    res_001 = diagnose("NET-001")
    assert res_001["case_id"] == "NET-001"
    assert res_001["source"] == "checker"
    assert res_001["confidence"] == 1.0
    assert len(res_001["fix_steps"]) > 0
    
    # Test NET-011 (expected STP blocking behavior should resolve without LLM/API access)
    res_011 = diagnose("NET-011")
    assert res_011["case_id"] == "NET-011"
    assert res_011["source"] == "checker"
    assert 0.0 <= res_011["confidence"] <= 1.0
    assert "expected behavior" in res_011["root_cause"]

def test_engine_all_cases():
    cases_df = pd.read_csv("data/cases.csv")
    
    for _, row in cases_df.iterrows():
        case_id = row["case_id"]
        res = diagnose(case_id)
        
        # Verify schema conformant
        assert isinstance(res, dict)
        assert "case_id" in res
        assert "root_cause" in res
        assert "osi_layer" in res
        assert "confidence" in res
        assert "evidence" in res
        assert "next_command" in res
        assert "fix_steps" in res
        assert "source" in res
        
        assert res["case_id"] == case_id
        assert res["source"] == "checker"
        assert isinstance(res["confidence"], float)
        assert 0.0 <= res["confidence"] <= 1.0
        assert isinstance(res["fix_steps"], list)
        
        print(f"Case {case_id} diagnosed successfully via {res['source']}.")
