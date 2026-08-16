# Fault Taxonomy — Symptom → OSI Layer → Fix Reference

This is the shared knowledge base behind both `checker.py`'s regex rules and the LLM's
few-shot examples. Every case in `cases.csv` should map to one row here.

| Fault | OSI Layer | Typical `show` evidence | Typical fix (CLI) |
|---|---|---|---|
| Interface administratively down | L1/L2 | `GigabitEthernet0/0.X is administratively down, line protocol is down` | `configure terminal` → `interface X` → `no shutdown` |
| Interface up but line protocol down | L1 | `... is up, line protocol is down` | Check cabling/encapsulation; `no shutdown` on both ends; verify duplex/speed match |
| VLAN ID mismatch (switch vs. router sub-interface) | L2 | `show vlan brief` shows VLAN 30 on switch; router sub-interface configured with `encapsulation dot1Q 20` | `interface X.Y` → `encapsulation dot1Q <correct_vlan>` |
| Missing/incorrect ACL entry | L3 | `show access-lists` missing a `permit` line for required traffic, or implicit deny catching it | `configure terminal` → `ip access-list extended NAME` → `permit ...` |
| Incorrect wildcard mask in ACL/OSPF | L3 | ACL or `router ospf` network statement using wrong wildcard (e.g., `255.255.255.0` instead of `0.0.0.255`) | Re-enter statement with corrected inverse mask |
| Missing/incorrect default route | L3 | `show ip route` has no `0.0.0.0/0` entry, or `show ip interface brief` shows correct interfaces but no route table entry | `ip route 0.0.0.0 0.0.0.0 <next-hop>` |
| Trunk port not configured / access mode mismatch | L2 | `show interfaces trunk` missing expected port; `switchport mode access` where trunk expected | `switchport mode trunk` → `switchport trunk allowed vlan add X` |
| Duplicate/conflicting IP address | L3 | `show ip interface brief` two interfaces with same subnet or overlapping addressing | Correct IP addressing plan; reassign one interface |
| NAT overload missing/misconfigured | L3 | `show ip nat translations` empty when expected; `show run` missing `ip nat inside`/`outside` or overload statement | `ip nat inside source list X interface Y overload` |
| Spanning-tree blocking expected port | L2 | `show spanning-tree` port state `BLK` unexpectedly | Verify root bridge priority / port cost / correct root selection |
| STP loop / missing portfast (edge case) | L2 | Excessive topology changes in `show spanning-tree detail` | `spanning-tree portfast` on access ports (with caution) |
| DHCP not assigning addresses | L3/App | PC shows APIPA `169.254.x.x`; `show ip dhcp binding` empty | Verify `ip helper-address`, DHCP pool config, `no shutdown` on relevant interface |

## Notes for `checker.py` implementation
- Match on distinctive substrings first (e.g., `"administratively down"`) — these are
  near-unambiguous and safe for deterministic rules.
- Wildcard mask and VLAN mismatch errors require *comparing two pieces of output*
  (e.g., switch VLAN table vs. router sub-interface config) — these may need slightly
  more logic than a single regex, but are still fully deterministic.
- Anything requiring judgment about *intent* (e.g., "is this address plan a mistake or
  intentional?") should route to the LLM rather than be force-fit into a rule.

## Notes for `diagnose_prompt.md` few-shot examples
- Pick 2-3 examples from this table that are NOT covered by `checker.py`'s rules, so the
  LLM's few-shot examples demonstrate genuinely LLM-required reasoning (ambiguous or
  multi-symptom cases), not duplicate what the deterministic engine already handles.
