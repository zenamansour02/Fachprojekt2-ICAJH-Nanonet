
#!/usr/bin/env python3
from node import *

class ICAWeights13(Topo):
    def build(self):
        # Core + gateway nodes
        self.add_node("0")
        self.add_node("1")
        self.add_node("2")
        self.add_node("3")
        self.add_node("4")
        # Source nodes
        self.add_node("11")
        self.add_node("12")
        self.add_node("13")
        self.add_node("14")
        # Receiver nodes
        self.add_node("21")
        self.add_node("22")
        self.add_node("23")
        self.add_node("24")
        # Core chain (800 Mbps = 8 units × 100 Mbps/unit, w=1)
        self.add_link_name("0", "1", cost=1000, delay=0.2, bw=800000, directed=True)
        self.add_link_name("1", "0", cost=1000, delay=0.2, bw=800000, directed=True)
        self.add_link_name("1", "2", cost=1000, delay=0.2, bw=800000, directed=True)
        self.add_link_name("2", "1", cost=1000, delay=0.2, bw=800000, directed=True)
        self.add_link_name("2", "3", cost=1000, delay=0.2, bw=800000, directed=True)
        self.add_link_name("3", "2", cost=1000, delay=0.2, bw=800000, directed=True)
        # Gateway ingress — ECMP weights: w(0->4)=2, w(1->4)=1; (0→4)=100 Mbps, (1→4)=200 Mbps
        self.add_link_name("0", "4", cost=2000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("4", "0", cost=4000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("1", "4", cost=1000, delay=0.2, bw=200000, directed=True)
        self.add_link_name("4", "1", cost=4000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("2", "4", cost=4000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("4", "2", cost=4000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("3", "4", cost=4000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("4", "3", cost=4000, delay=0.2, bw=100000, directed=True)
        # Source links (100 Mbps = 1 unit × 100 Mbps/unit, w=1)
        self.add_link_name("11", "0", cost=1000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("12", "0", cost=1000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("13", "0", cost=1000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("14", "0", cost=1000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("0", "11", cost=1000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("0", "12", cost=1000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("0", "13", cost=1000, delay=0.2, bw=100000, directed=True)
        self.add_link_name("0", "14", cost=1000, delay=0.2, bw=100000, directed=True)
        # Receiver links (10 Gbps, non-bottleneck, w=1)
        self.add_link_name("4", "21", cost=1000, delay=0.2, bw=10000000, directed=True)
        self.add_link_name("21", "4", cost=1000, delay=0.2, bw=10000000, directed=True)
        self.add_link_name("4", "22", cost=1000, delay=0.2, bw=10000000, directed=True)
        self.add_link_name("22", "4", cost=1000, delay=0.2, bw=10000000, directed=True)
        self.add_link_name("4", "23", cost=1000, delay=0.2, bw=10000000, directed=True)
        self.add_link_name("23", "4", cost=1000, delay=0.2, bw=10000000, directed=True)
        self.add_link_name("4", "24", cost=1000, delay=0.2, bw=10000000, directed=True)
        self.add_link_name("24", "4", cost=1000, delay=0.2, bw=10000000, directed=True)

    def dijkstra_computed(self):
        # Demand 11->21 (no SRv6 — ECMP weights baseline)
        build_str = ""
        nhlist = self.get_dijkstra_route_by_name("11", "21")
        for nh in nhlist:
            build_str += f" nexthop via {nh.nh} " + f" weight {int(100/len(nhlist))} "
        self.add_command("11", f"ip -6 route add {{21}} metric 1 table 1 src {{11}}  {build_str}")
        # Demand 12->22 (no SRv6)
        build_str = ""
        nhlist = self.get_dijkstra_route_by_name("12", "22")
        for nh in nhlist:
            build_str += f" nexthop via {nh.nh} " + f" weight {int(100/len(nhlist))} "
        self.add_command("12", f"ip -6 route add {{22}} metric 1 table 1 src {{12}}  {build_str}")
        # Demand 13->23 (no SRv6)
        build_str = ""
        nhlist = self.get_dijkstra_route_by_name("13", "23")
        for nh in nhlist:
            build_str += f" nexthop via {nh.nh} " + f" weight {int(100/len(nhlist))} "
        self.add_command("13", f"ip -6 route add {{23}} metric 1 table 1 src {{13}}  {build_str}")
        # Demand 14->24 (no SRv6)
        build_str = ""
        nhlist = self.get_dijkstra_route_by_name("14", "24")
        for nh in nhlist:
            build_str += f" nexthop via {nh.nh} " + f" weight {int(100/len(nhlist))} "
        self.add_command("14", f"ip -6 route add {{24}} metric 1 table 1 src {{14}}  {build_str}")
        self.add_command("11", "ip -6 rule add to {21/} iif lo table 1")
        self.add_command("12", "ip -6 rule add to {22/} iif lo table 1")
        self.add_command("13", "ip -6 rule add to {23/} iif lo table 1")
        self.add_command("14", "ip -6 rule add to {24/} iif lo table 1")
        # nuttcp servers on receiver nodes
        self.add_command("21", "nuttcp -6 -S")
        self.add_command("22", "nuttcp -6 -S")
        self.add_command("23", "nuttcp -6 -S")
        self.add_command("24", "nuttcp -6 -S")
        # nuttcp clients: TIME=120s, NSTREAMS=8
        self.add_command("11", 'echo bash -c \\\"START=\\\\\$SECONDS\; DEADLINE=\\\\\$\(\( START + 150 \)\)\; while \! ip netns exec 11 nuttcp -T120 -i1 -R10000 -N8 {21} \>\>flow_11-21.txt 2\>\&1 \; do \[ \\\\\$SECONDS -ge \\\\\$DEADLINE \] \&\& \{ echo TIMEOUT\: \\\\\$SECONDS \>\>flow_11-21.txt\; break\; \}\; sleep 1\; echo RTY\: \\\\\$SECONDS \>\>flow_11-21.txt\; done\\\" | at now+2min')
        self.add_command("12", 'echo bash -c \\\"START=\\\\\$SECONDS\; DEADLINE=\\\\\$\(\( START + 150 \)\)\; while \! ip netns exec 12 nuttcp -T120 -i1 -R10000 -N8 {22} \>\>flow_12-22.txt 2\>\&1 \; do \[ \\\\\$SECONDS -ge \\\\\$DEADLINE \] \&\& \{ echo TIMEOUT\: \\\\\$SECONDS \>\>flow_12-22.txt\; break\; \}\; sleep 1\; echo RTY\: \\\\\$SECONDS \>\>flow_12-22.txt\; done\\\" | at now+2min')
        self.add_command("13", 'echo bash -c \\\"START=\\\\\$SECONDS\; DEADLINE=\\\\\$\(\( START + 150 \)\)\; while \! ip netns exec 13 nuttcp -T120 -i1 -R10000 -N8 {23} \>\>flow_13-23.txt 2\>\&1 \; do \[ \\\\\$SECONDS -ge \\\\\$DEADLINE \] \&\& \{ echo TIMEOUT\: \\\\\$SECONDS \>\>flow_13-23.txt\; break\; \}\; sleep 1\; echo RTY\: \\\\\$SECONDS \>\>flow_13-23.txt\; done\\\" | at now+2min')
        self.add_command("14", 'echo bash -c \\\"START=\\\\\$SECONDS\; DEADLINE=\\\\\$\(\( START + 150 \)\)\; while \! ip netns exec 14 nuttcp -T120 -i1 -R10000 -N8 {24} \>\>flow_14-24.txt 2\>\&1 \; do \[ \\\\\$SECONDS -ge \\\\\$DEADLINE \] \&\& \{ echo TIMEOUT\: \\\\\$SECONDS \>\>flow_14-24.txt\; break\; \}\; sleep 1\; echo RTY\: \\\\\$SECONDS \>\>flow_14-24.txt\; done\\\" | at now+2min')

        self.enable_throughput()
        for node in ["0", "1", "2", "3", "4", "11", "12", "13", "14"]:
            self.add_command(node, "sysctl net.ipv6.fib_multipath_hash_policy=1")

topos = {'ICAWeights13': (lambda: ICAWeights13())}
