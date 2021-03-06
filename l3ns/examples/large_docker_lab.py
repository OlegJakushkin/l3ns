from l3ns.ldc import DockerNode, DockerSubnet
from l3ns.base.network import Network, NetworkConcurrent
from l3ns import defaults

import sys

if sys.argv[2] == 'c':
    defaults.network = NetworkConcurrent('15.0.0.0/16', max_workers=8)
else:
    defaults.network = Network('15.0.0.0/16')

N = int(sys.argv[1])

s = DockerSubnet(name='polygon', size=N+10)

nodes = []


for i in range(N):
    n = DockerNode(
        'l3ns_node_' + str(i + 1),
        image='l3ns/ts_ping',
        command='tail -f /dev/null' if not len(nodes)
                else 'ping {} | ts "[%H:%M:%S]"'.format(nodes[int(i/10)].get_ip()))
    nodes.append(n)
    s.add_node(n)

defaults.network.start(interactive=True)
