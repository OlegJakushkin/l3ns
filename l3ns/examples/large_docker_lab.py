from l3ns.ldc import DockerNode, DockerSubnet
from l3ns.base.network import Network, NetworkConcurrent
from l3ns import defaults

import sys

if sys.argv[2] == 'c':
    defaults.network = NetworkConcurrent('15.0.0.0/16', max_workers=2)
else:
    defaults.network = Network('15.0.0.0/16')

N = int(sys.argv[1])

s = DockerSubnet(name='polygon', size=N+10)

nodes = []


for i in range(N):
    n = DockerNode(image='alpine', command='tail -f /dev/null' if not len(nodes) else 'ping {}'.format(nodes[-1].get_ip()), name='l3ns_node_' + str(i+1))
    nodes.append(n)
    s.add_node(n)

defaults.network.start(interactive=True)
