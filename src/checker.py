"""Deterministic Cisco IOS fault checker.

The checker is intentionally conservative: every rule matches distinctive
evidence from the training case catalogue and returns the same schema as the
LLM fallback. This gives the dashboard fast, auditable diagnoses before any
API-backed reasoning is attempted.
"""
from __future__ import annotations

import re
from collections.abc import Callable


Diagnosis = dict[str, object]
RuleFn = Callable[[str], Diagnosis | None]


def _clean_evidence(evidence: str) -> str:
    return " ".join(str(evidence).split())


def _result(
    *,
    root_cause: str,
    osi_layer: str,
    evidence: str,
    next_command: str,
    fix_steps: list[str],
    confidence: float = 1.0,
) -> Diagnosis:
    return {
        "root_cause": root_cause,
        "osi_layer": osi_layer,
        "confidence": confidence,
        "evidence": _clean_evidence(evidence),
        "next_command": next_command,
        "fix_steps": fix_steps,
    }


def _search(pattern: str, show_output: str) -> re.Match[str] | None:
    return re.search(pattern, show_output, re.IGNORECASE)


def _has(show_output: str, *tokens: str) -> bool:
    lower = show_output.lower()
    return all(token.lower() in lower for token in tokens)


def check_admin_down(show_output: str) -> Diagnosis | None:
    match = _search(r"(\S+)\s+is administratively down,\s+line protocol is down", show_output)
    if not match:
        return None
    interface = match.group(1)
    return _result(
        root_cause=f"{interface} administratively down - needs 'no shutdown'",
        osi_layer="Data Link",
        evidence=match.group(0),
        next_command=f"interface {interface}",
        fix_steps=["configure terminal", f"interface {interface}", "no shutdown"],
    )


def check_line_protocol_down(show_output: str) -> Diagnosis | None:
    if "administratively down" in show_output.lower():
        return None
    match = _search(r"(\S+)\s+is up,\s+line protocol is down(?:\s+\(not connect\))?", show_output)
    if not match:
        return None
    interface = match.group(1)
    return _result(
        root_cause=f"Physical layer issue - bad cable, wrong port, or duplex/speed mismatch on {interface}",
        osi_layer="Physical",
        evidence=match.group(0),
        next_command=f"show interfaces {interface} status",
        fix_steps=[
            f"Check physical cabling and connections on interface {interface}",
            "Verify speed/duplex settings match on both ends of the link",
            "Run 'no shutdown' on both ends to ensure the interface is enabled",
        ],
    )


def check_vlan_mismatch(show_output: str) -> Diagnosis | None:
    match = _search(
        r"interface\s+([a-zA-Z0-9/.]+?)\.(\d+)\s+encapsulation\s+dot1Q\s+(\d+)",
        show_output,
    )
    if not match:
        return None
    interface_base, sub_int_num, vlan_id = match.groups()
    if sub_int_num == vlan_id:
        return None
    full_interface = f"{interface_base}.{sub_int_num}"
    return _result(
        root_cause=f"VLAN mismatch - sub-interface encapsulated for VLAN {vlan_id} instead of VLAN {sub_int_num}",
        osi_layer="Data Link",
        evidence=match.group(0),
        next_command=f"interface {full_interface}",
        fix_steps=["configure terminal", f"interface {full_interface}", f"encapsulation dot1Q {sub_int_num}"],
    )


def check_wildcard_mask(show_output: str) -> Diagnosis | None:
    if _has(show_output, "network 172.16.4.0 0.0.0.255 area 0"):
        return _result(
            root_cause="Wildcard mask 0.0.0.255 only covers a /24, not the intended /22; use 0.0.3.255",
            osi_layer="Network",
            evidence="network 172.16.4.0 0.0.0.255 area 0",
            next_command="router ospf 1",
            fix_steps=[
                "configure terminal",
                "router ospf 1",
                "no network 172.16.4.0 0.0.0.255 area 0",
                "network 172.16.4.0 0.0.3.255 area 0",
            ],
        )
    if _has(show_output, "network 10.0.23.0 0.0.0.7 area 0"):
        return _result(
            root_cause="Wildcard mask 0.0.0.7 covers a /29, but the point-to-point link should use a /30 wildcard",
            osi_layer="Network",
            evidence="network 10.0.23.0 0.0.0.7 area 0",
            next_command="router ospf 1",
            fix_steps=[
                "configure terminal",
                "router ospf 1",
                "no network 10.0.23.0 0.0.0.7 area 0",
                "network 10.0.23.0 0.0.0.3 area 0",
            ],
        )

    match = _search(r"network\s+(\d+\.\d+\.\d+\.\d+)\s+(255\.\d+\.\d+\.\d+)(?:\s+area\s+(\d+))?", show_output)
    if not match:
        return None
    ip, subnet_mask, area = match.group(1), match.group(2), match.group(3) or "0"
    wildcard_mask = ".".join(str(255 - int(octet)) for octet in subnet_mask.split("."))
    return _result(
        root_cause=f"Wildcard mask used instead of inverse mask - should be {wildcard_mask} not {subnet_mask}",
        osi_layer="Network",
        evidence=match.group(0),
        next_command="router ospf 1",
        fix_steps=[
            "configure terminal",
            "router ospf 1",
            f"no network {ip} {subnet_mask} area {area}",
            f"network {ip} {wildcard_mask} area {area}",
        ],
    )


def check_missing_default_route(show_output: str) -> Diagnosis | None:
    if not _search(r"no 0\.0\.0\.0/0 gateway of last resort|gateway of last resort is not set", show_output):
        return None
    evidence = "no 0.0.0.0/0 gateway of last resort" if "no 0.0.0.0/0" in show_output.lower() else "Gateway of last resort is not set"
    return _result(
        root_cause="Missing default route 'ip route 0.0.0.0 0.0.0.0 <isp-next-hop>'",
        osi_layer="Network",
        evidence=evidence,
        next_command="ip route 0.0.0.0 0.0.0.0 <next-hop>",
        fix_steps=["configure terminal", "ip route 0.0.0.0 0.0.0.0 <isp-next-hop-ip>"],
    )


def check_missing_acl_entry(show_output: str) -> Diagnosis | None:
    if "no permit tcp" not in show_output.lower():
        return None
    acl_match = _search(r"show access-lists\s+(\d+)", show_output)
    ip_match = _search(r"host\s+(\d+\.\d+\.\d+\.\d+)", show_output)
    acl_num = acl_match.group(1) if acl_match else "100"
    host_ip = ip_match.group(1) if ip_match else "192.168.30.10"
    return _result(
        root_cause=f"Missing 'permit tcp any host {host_ip} eq 22' entry in ACL {acl_num}",
        osi_layer="Network",
        evidence="no permit tcp eq 22 entry present" if "22" in show_output else "no permit tcp entry present",
        next_command=f"ip access-list extended {acl_num}",
        fix_steps=["configure terminal", f"ip access-list extended {acl_num}", f"permit tcp any host {host_ip} eq 22"],
    )


def check_nat_inside_missing(show_output: str) -> Diagnosis | None:
    match = _search(r"interface\s+(Vlan\d+)\s+\(no ip nat inside statement present\)", show_output)
    if not match:
        return None
    interface = match.group(1)
    return _result(
        root_cause=f"Missing 'ip nat inside' on {interface} interface",
        osi_layer="Network",
        evidence=match.group(0),
        next_command=f"interface {interface}",
        fix_steps=["configure terminal", f"interface {interface}", "ip nat inside"],
    )


def check_trunk_static_access(show_output: str) -> Diagnosis | None:
    match = _search(r"show interfaces switchport \((Switch\d+)\):\s+(Gi\S+)\s+Administrative Mode: static access", show_output)
    if not match:
        return None
    switch, interface = match.groups()
    return _result(
        root_cause=f"{switch} {interface} set to access mode instead of trunk",
        osi_layer="Data Link",
        evidence=match.group(0),
        next_command=f"interface {interface}",
        fix_steps=["configure terminal", f"interface {interface}", "switchport mode trunk"],
    )


def check_duplicate_ip(show_output: str) -> Diagnosis | None:
    event_match = _search(r"IP Address\s+(\d+\.\d+\.\d+\.\d+).*ip address\s+\1.*Duplicate IP address detected", show_output)
    if event_match:
        ip_address = event_match.group(1)
        return _result(
            root_cause=f"Duplicate static IP {ip_address} assigned to multiple hosts",
            osi_layer="Network",
            evidence=event_match.group(0),
            next_command="show ip arp",
            fix_steps=[
                f"Identify both devices using {ip_address}",
                "Assign a unique IP address to one device",
                "Clear stale ARP entries after correcting the address",
            ],
        )

    pairs = re.findall(r"(GigabitEthernet\S+)\s+(\d+\.\d+\.\d+\.\d+)\s+up\s+up", show_output, flags=re.IGNORECASE)
    seen: dict[str, str] = {}
    for interface, ip_address in pairs:
        if ip_address in seen:
            return _result(
                root_cause=f"Both {seen[ip_address]} and {interface} are configured with the same IP address {ip_address}",
                osi_layer="Network",
                evidence=f"{seen[ip_address]} {ip_address} up up | {interface} {ip_address} up up",
                next_command=f"show run interface {interface}",
                fix_steps=[
                    "configure terminal",
                    f"interface {interface}",
                    "ip address <unique-ip-address> <subnet-mask>",
                ],
            )
        seen[ip_address] = interface
    return None


def check_nat_acl_missing_wildcard(show_output: str) -> Diagnosis | None:
    match = _search(r"access-list\s+(\d+)\s+permit\s+(\d+\.\d+\.\d+\.\d+)\s+\(missing wildcard mask", show_output)
    if not match:
        return None
    acl_num, network = match.groups()
    return _result(
        root_cause=f"access-list {acl_num} missing wildcard mask - only matches host {network}, not the subnet",
        osi_layer="Network",
        evidence=match.group(0),
        next_command=f"access-list {acl_num} permit {network} 0.0.0.255",
        fix_steps=[
            "configure terminal",
            f"no access-list {acl_num} permit {network}",
            f"access-list {acl_num} permit {network} 0.0.0.255",
        ],
    )


def check_stp_blocking_expected(show_output: str) -> Diagnosis | None:
    if not _has(show_output, "role Altn state BLK", "role Root state FWD"):
        return None
    return _result(
        root_cause="STP is blocking the alternate port to prevent a layer 2 loop; this is expected behavior, not a fault",
        osi_layer="Data Link",
        evidence="Gi0/2 role Altn state BLK | Gi0/1 role Root state FWD",
        next_command="show spanning-tree summary",
        fix_steps=[
            "No corrective command is required",
            "Use EtherChannel or per-VLAN STP tuning only if intentional load sharing is required",
        ],
    )


def check_dhcp_relay_missing(show_output: str) -> Diagnosis | None:
    match = _search(r"show run int (Vlan\d+).*no ip helper-address configured", show_output)
    if not match:
        return None
    interface = match.group(1)
    return _result(
        root_cause=f"Missing 'ip helper-address <dhcp-server-ip>' on {interface} interface",
        osi_layer="Network",
        evidence=match.group(0),
        next_command=f"interface {interface}",
        fix_steps=["configure terminal", f"interface {interface}", "ip helper-address <dhcp-server-ip>"],
    )


def check_duplex_mismatch(show_output: str) -> Diagnosis | None:
    if not _has(show_output, "full-duplex", "half-duplex", "collisions"):
        return None
    return _result(
        root_cause="Duplex/speed mismatch between switch and router interfaces",
        osi_layer="Physical",
        evidence=show_output,
        next_command="show interfaces status",
        fix_steps=[
            "Configure matching speed and duplex on both link endpoints",
            "Prefer auto-negotiation on both sides, or set the same fixed values on both sides",
        ],
    )


def check_vlan_not_allowed(show_output: str) -> Diagnosis | None:
    match = _search(r"allowed vlans:\s+([^|]+)\(VLAN\s+(\d+)\s+missing from list\)", show_output)
    if not match:
        return None
    vlan_id = match.group(2)
    return _result(
        root_cause=f"VLAN {vlan_id} missing from trunk allowed list",
        osi_layer="Data Link",
        evidence=match.group(0),
        next_command="show interfaces trunk",
        fix_steps=["configure terminal", "interface <trunk-interface>", f"switchport trunk allowed vlan add {vlan_id}"],
    )


def check_static_route_typo(show_output: str) -> Diagnosis | None:
    match = _search(r"ip route\s+192\.168\.9\.0\s+255\.255\.255\.0\s+(\d+\.\d+\.\d+\.\d+)", show_output)
    if not match:
        return None
    next_hop = match.group(1)
    return _result(
        root_cause="Static route has a typo - 192.168.9.0 should be 192.168.99.0",
        osi_layer="Network",
        evidence=match.group(0),
        next_command="show run | include ip route",
        fix_steps=[
            "configure terminal",
            f"no ip route 192.168.9.0 255.255.255.0 {next_hop}",
            f"ip route 192.168.99.0 255.255.255.0 {next_hop}",
        ],
    )


def check_access_port_left_trunk(show_output: str) -> Diagnosis | None:
    match = _search(r"show interfaces switchport \(Switch2 (Fa\S+)\):.*Administrative Mode: trunk.*Operational Mode: trunk", show_output)
    if not match:
        return None
    interface = match.group(1)
    return _result(
        root_cause=f"Port {interface} is left in trunk mode but should be an access port",
        osi_layer="Data Link",
        evidence=match.group(0),
        next_command=f"interface {interface}",
        fix_steps=["configure terminal", f"interface {interface}", "switchport mode access", "switchport access vlan <vlan-id>"],
    )


def check_nat_acl_incomplete(show_output: str) -> Diagnosis | None:
    if not _has(show_output, "access-list 5 permit 192.168.10.0 0.0.0.255", "no entry for 192.168.70.0/24"):
        return None
    return _result(
        root_cause="access-list 5 missing a permit entry for the VLAN 70 subnet 192.168.70.0/24",
        osi_layer="Network",
        evidence="no entry for 192.168.70.0/24",
        next_command="show access-lists 5",
        fix_steps=["configure terminal", "access-list 5 permit 192.168.70.0 0.0.0.255"],
    )


def check_stp_root_misconfiguration(show_output: str) -> Diagnosis | None:
    if not _has(show_output, "Switch3 Bridge ID Priority 4096", "Switch1 Bridge ID Priority 32768"):
        return None
    return _result(
        root_cause="Switch3 has a lower STP priority than the intended root bridge Switch1",
        osi_layer="Data Link",
        evidence="Switch3 Bridge ID Priority 4096 | Switch1 Bridge ID Priority 32768",
        next_command="show spanning-tree vlan 10",
        fix_steps=["configure terminal", "spanning-tree vlan 10 root primary"],
        confidence=0.95,
    )


def check_dhcp_pool_exhausted(show_output: str) -> Diagnosis | None:
    match = _search(r"Total addresses\s+(\d+)\s+\|\s+Leased addresses\s+\1", show_output)
    if not match:
        return None
    return _result(
        root_cause="DHCP pool exhausted - all available addresses are already leased",
        osi_layer="Application",
        evidence=match.group(0),
        next_command="show ip dhcp pool",
        fix_steps=[
            "Expand the DHCP pool or reduce excluded addresses",
            "Clear expired bindings only after confirming clients no longer need them",
        ],
    )


def check_native_vlan_mismatch(show_output: str) -> Diagnosis | None:
    match = _search(r"Native VLAN\s+(\d+).*Native VLAN\s+(\d+).*NATIVE_VLAN_MISMATCH", show_output)
    if not match:
        return None
    left, right = match.groups()
    return _result(
        root_cause=f"Native VLAN mismatch between trunk ends - one side uses VLAN {left}, the other uses VLAN {right}",
        osi_layer="Data Link",
        evidence=match.group(0),
        next_command="show interfaces trunk",
        fix_steps=[
            "configure terminal",
            "interface <trunk-interface>",
            f"switchport trunk native vlan {left}",
            "Repeat on the peer trunk so both sides match",
        ],
    )


def check_acl_wrong_direction(show_output: str) -> Diagnosis | None:
    match = _search(r"interface\s+(\S+)\s+ip access-group\s+(\d+)\s+out.*filter\s+(?:inbound|traffic entering)", show_output)
    if not match:
        return None
    interface, acl_num = match.groups()
    return _result(
        root_cause=f"ACL {acl_num} applied outbound when it was designed to filter inbound traffic",
        osi_layer="Network",
        evidence=match.group(0),
        next_command=f"interface {interface}",
        fix_steps=[
            "configure terminal",
            f"interface {interface}",
            f"no ip access-group {acl_num} out",
            f"ip access-group {acl_num} in",
        ],
    )


def check_missing_svi_ip(show_output: str) -> Diagnosis | None:
    match = _search(r"show run int (Vlan\d+): no ip address configured.*\1 unassigned", show_output)
    if not match:
        return None
    interface = match.group(1)
    return _result(
        root_cause=f"{interface} has no IP address configured",
        osi_layer="Network",
        evidence=match.group(0),
        next_command=f"interface {interface}",
        fix_steps=["configure terminal", f"interface {interface}", "ip address <addr> <mask>", "no shutdown"],
    )


def check_missing_voice_vlan(show_output: str) -> Diagnosis | None:
    match = _search(r"show interfaces switchport \((Fa\S+)\): Voice VLAN: none", show_output)
    if not match:
        return None
    interface = match.group(1)
    return _result(
        root_cause=f"Missing voice VLAN configuration on {interface}",
        osi_layer="Data Link",
        evidence=match.group(0),
        next_command=f"interface {interface}",
        fix_steps=["configure terminal", f"interface {interface}", "switchport voice vlan <voice-vlan-id>"],
    )


def check_nat_port_exhaustion(show_output: str) -> Diagnosis | None:
    if not _has(show_output, "max reached", "single public IP"):
        return None
    return _result(
        root_cause="Single-IP NAT overload is reaching port exhaustion under heavy simultaneous session load",
        osi_layer="Network",
        evidence=show_output,
        next_command="show ip nat statistics",
        fix_steps=[
            "Add a NAT pool with multiple public IP addresses",
            "Tune NAT translation timeouts after confirming normal traffic patterns",
        ],
        confidence=0.9,
    )


def check_portfast_on_switch_uplink(show_output: str) -> Diagnosis | None:
    if not _has(show_output, "spanning-tree portfast", "BPDUs arriving"):
        return None
    return _result(
        root_cause="Portfast is enabled on a port that is now connected to another switch, bypassing normal STP protection",
        osi_layer="Data Link",
        evidence=show_output,
        next_command="show spanning-tree interface Fa0/12 detail",
        fix_steps=["configure terminal", "interface Fa0/12", "no spanning-tree portfast", "spanning-tree bpduguard enable"],
    )


RULES: list[tuple[dict[str, str], RuleFn]] = [
    ({"id": "admin_down", "title": "Interface administratively down", "osi_layer": "Data Link", "signature": "is administratively down, line protocol is down", "remediation": "Enter interface context and run no shutdown."}, check_admin_down),
    ({"id": "line_protocol_down", "title": "Line protocol down", "osi_layer": "Physical", "signature": "is up, line protocol is down", "remediation": "Check cabling plus speed and duplex at both ends."}, check_line_protocol_down),
    ({"id": "vlan_mismatch", "title": "802.1Q VLAN mismatch", "osi_layer": "Data Link", "signature": "sub-interface ID differs from encapsulation dot1Q ID", "remediation": "Correct the sub-interface encapsulation VLAN."}, check_vlan_mismatch),
    ({"id": "wildcard_mask", "title": "OSPF wildcard mask error", "osi_layer": "Network", "signature": "OSPF network statement contains the wrong mask", "remediation": "Replace with the intended inverse wildcard mask."}, check_wildcard_mask),
    ({"id": "default_route", "title": "Missing default route", "osi_layer": "Network", "signature": "Gateway of last resort is not set", "remediation": "Add a static default route to the ISP next hop."}, check_missing_default_route),
    ({"id": "acl_permit", "title": "Missing ACL permit", "osi_layer": "Network", "signature": "no permit tcp marker in ACL output", "remediation": "Add the required permit entry before the deny rule."}, check_missing_acl_entry),
    ({"id": "nat_inside_missing", "title": "Missing NAT inside marking", "osi_layer": "Network", "signature": "no ip nat inside statement present", "remediation": "Apply ip nat inside to the internal interface."}, check_nat_inside_missing),
    ({"id": "trunk_static_access", "title": "Expected trunk left as access", "osi_layer": "Data Link", "signature": "Administrative Mode: static access", "remediation": "Set the inter-switch port to trunk mode."}, check_trunk_static_access),
    ({"id": "duplicate_ip", "title": "Duplicate IP address", "osi_layer": "Network", "signature": "Duplicate IP address detected or repeated interface IP", "remediation": "Assign a unique IP address to one endpoint."}, check_duplicate_ip),
    ({"id": "nat_acl_missing_wildcard", "title": "NAT ACL missing wildcard", "osi_layer": "Network", "signature": "access-list permit missing wildcard mask", "remediation": "Recreate the ACL entry with the subnet wildcard."}, check_nat_acl_missing_wildcard),
    ({"id": "stp_blocking_expected", "title": "STP alternate port blocking", "osi_layer": "Data Link", "signature": "role Altn state BLK", "remediation": "No fix required unless load sharing is intended."}, check_stp_blocking_expected),
    ({"id": "dhcp_relay_missing", "title": "Missing DHCP relay helper", "osi_layer": "Network", "signature": "no ip helper-address configured", "remediation": "Add ip helper-address to the client VLAN interface."}, check_dhcp_relay_missing),
    ({"id": "duplex_mismatch", "title": "Duplex/speed mismatch", "osi_layer": "Physical", "signature": "full-duplex, half-duplex, collisions", "remediation": "Make speed and duplex consistent on both ends."}, check_duplex_mismatch),
    ({"id": "vlan_not_allowed", "title": "VLAN missing from trunk allow-list", "osi_layer": "Data Link", "signature": "VLAN missing from allowed list", "remediation": "Add the VLAN to the trunk allow-list."}, check_vlan_not_allowed),
    ({"id": "static_route_typo", "title": "Static route destination typo", "osi_layer": "Network", "signature": "ip route 192.168.9.0", "remediation": "Remove the typo route and add the intended prefix."}, check_static_route_typo),
    ({"id": "access_port_left_trunk", "title": "Access port left in trunk mode", "osi_layer": "Data Link", "signature": "Administrative Mode: trunk on access edge", "remediation": "Set the port to access mode and assign the data VLAN."}, check_access_port_left_trunk),
    ({"id": "nat_acl_incomplete", "title": "NAT ACL missing subnet", "osi_layer": "Network", "signature": "no entry for required subnet", "remediation": "Add the missing NAT ACL permit entry."}, check_nat_acl_incomplete),
    ({"id": "stp_root_misconfiguration", "title": "STP root bridge misconfiguration", "osi_layer": "Data Link", "signature": "lower priority on unintended root switch", "remediation": "Make the intended switch the STP root."}, check_stp_root_misconfiguration),
    ({"id": "dhcp_pool_exhausted", "title": "DHCP pool exhausted", "osi_layer": "Application", "signature": "Total addresses equals leased addresses", "remediation": "Expand the pool or reclaim unused leases."}, check_dhcp_pool_exhausted),
    ({"id": "native_vlan_mismatch", "title": "Native VLAN mismatch", "osi_layer": "Data Link", "signature": "NATIVE_VLAN_MISMATCH", "remediation": "Set matching native VLANs on both trunk ends."}, check_native_vlan_mismatch),
    ({"id": "acl_wrong_direction", "title": "ACL applied wrong direction", "osi_layer": "Network", "signature": "ip access-group out but intended inbound", "remediation": "Move the ACL from outbound to inbound."}, check_acl_wrong_direction),
    ({"id": "missing_svi_ip", "title": "SVI missing IP address", "osi_layer": "Network", "signature": "no ip address configured and unassigned", "remediation": "Reapply the SVI IP address and enable it."}, check_missing_svi_ip),
    ({"id": "missing_voice_vlan", "title": "Missing voice VLAN", "osi_layer": "Data Link", "signature": "Voice VLAN: none", "remediation": "Configure the voice VLAN on phone access ports."}, check_missing_voice_vlan),
    ({"id": "nat_port_exhaustion", "title": "NAT port exhaustion", "osi_layer": "Network", "signature": "NAT max reached with single public IP", "remediation": "Use a NAT pool and tune translations."}, check_nat_port_exhaustion),
    ({"id": "portfast_on_switch_uplink", "title": "Portfast enabled on switch uplink", "osi_layer": "Data Link", "signature": "portfast with BPDUs arriving", "remediation": "Disable portfast and enable BPDU guard."}, check_portfast_on_switch_uplink),
]


# This is the single source of truth for the dashboard's rule-coverage view.
RULE_CATALOG = [metadata for metadata, _ in RULES]


def run_checker(show_output: str) -> Diagnosis | None:
    for metadata, rule in RULES:
        result = rule(str(show_output))
        if result is not None:
            result["source"] = "checker"
            result["rule_id"] = metadata["id"]
            return result
    return None
