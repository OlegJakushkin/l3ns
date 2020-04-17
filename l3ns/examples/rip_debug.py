
import sys
sys.path.append('/home/panda')


from l3ns.ldc import DockerNode, DockerSubnet
from l3ns import defaults, net


defaults.subnet_class = DockerSubnet

config_template ='''router rip
network {ip_range}

redistribute kernel
redistribute static
redistribute connected
'''

routers = [DockerNode(
    image='frrouting/frr',
    entrypoint="sed -i 's/ripd=no/ripd=yes/' /etc/frr/daemons && /usr/lib/frr/docker-start",
    name='router_%d' % (i+1),
    privileged=True
) for i in range(2)]

nodes = [DockerNode(image='alpine', command='tail -f /dev/null', name='node_%d' % (i+1)) for i in range(2)]

router_net = net.create_subnet('router_net', routers, size=4)

for node in routers:
    node.is_router = True

routers[0].put_sting('/etc/frr/ripd.conf', config_template.format(ip_range=router_net.get_ip_range()))
routers[1].put_sting('/etc/frr/ripd.conf', config_template.format(ip_range=router_net.get_ip_range()))

for n, r in zip(nodes, routers):
    n.connect_to(r)

net.start(interactive=True)
