import docker
import tarfile
import io
import os

from l3ns.base import BaseNode
from l3ns.ldc.utils import docker_client
from l3ns.ldc.subnet import DockerSubnet


class DockerNode(BaseNode):
    lock_filepath = '/var/run/l3ns.lock'

    def __init__(self, name=None, **docker_kwargs):
        self._client = docker_client
        self._docker_kwargs = docker_kwargs
        self.container = None
        self.image = None  # not a name, but docker-py object
        super(DockerNode, self).__init__(name=name)

    def _connect_subnet(self, subnet, ip):
        self._client.networks.get(subnet.name).connect(self.container, ipv4_address=ip)

    @staticmethod
    def _shell_entrypoint(entrypoint):

        if not entrypoint or type(entrypoint) is str:
            return entrypoint

        else:
            return ' '.join(entrypoint)

    def _make_entrypoint(self):
        entrypoint = ('entrypoint' in self._docker_kwargs and self._docker_kwargs['entrypoint']) \
                     or self.image.attrs['Config']['Entrypoint']
        cmd = ('command' in self._docker_kwargs and self._docker_kwargs['command']) \
              or self.image.attrs['Config']['Cmd']

        waiting_cmd = 'while [ ! -f {lock_file} ]; do sleep 1; done; '.format(lock_file=self.lock_filepath)

        ret_entrypoint = ['/bin/sh', '-c']

        ret_cmd = waiting_cmd

        if not entrypoint:
            ret_cmd += self._shell_entrypoint(cmd)

        elif type(entrypoint) is str:
            ret_cmd += entrypoint

        elif 'sh' in entrypoint[0] and entrypoint[1] == '-c':

            ret_entrypoint = entrypoint[:2]

            ret_cmd += self._shell_entrypoint(entrypoint[2:])

            if cmd:
                ret_cmd += self._shell_entrypoint(cmd)

        else:
            ret_cmd += self._shell_entrypoint(entrypoint)

            if cmd:
                ret_cmd += self._shell_entrypoint(cmd)

        # for some reason docker messes up while loop if cmd is a string
        return ret_entrypoint, [ret_cmd]

    def _start(self, dc=None):

        if dc:
            self._client = dc
        else:
            dc = self._client

        if self.started:
            return self.container

        networking_kwargs = {}

        try:
            self.image = dc.images.get(self._docker_kwargs['image'])
        except docker.errors.ImageNotFound:
            print('No {} image found locally, trying to pull...'.format(self._docker_kwargs['image']))
            self.image = dc.images.pull(self._docker_kwargs['image'], tag='latest')

        self._docker_kwargs['entrypoint'], self._docker_kwargs['command'] = self._make_entrypoint()

        if 'cap_add' in self._docker_kwargs:
            try:
                self._docker_kwargs['cap_add'].append('NET_ADMIN')
            except AttributeError:
                self._docker_kwargs['cap_add'] = ['NET_ADMIN', self._docker_kwargs['cap_add']]
        else:
            self._docker_kwargs['cap_add'] = 'NET_ADMIN'

        # print(self.name, self._docker_kwargs['entrypoint'] + self._docker_kwargs['command'], sep=': ')

        self.container = dc.containers.run(
            name=self.name,
            detach=True,
            **networking_kwargs,
            **self._docker_kwargs)
        self.started = True
        self.loaded = True

        try:
            default_net = next(iter(self.container.attrs['NetworkSettings']['Networks'].keys()))
        except StopIteration:
            raise Exception('Container {} has no initial net, check docker config')

        if self._interfaces or self.connect_to_internet:
            dc.networks.get(default_net).disconnect(self.container)

        for path, string in self._files.items():
            self.put_sting(path, string)

        self.put_sting(self.lock_filepath, '')

        return self.container

    def load(self, dc=None):

        dc = dc or self._client

        try:
            self.container = dc.containers.get(self.name)
            self.loaded = True
        except docker.errors.NotFound:
            pass

    def stop(self, dc=None):

        dc = dc or self._client

        if not self.loaded:
            self.load(dc=dc)

        try:
            self.container.remove(force=True)
            print('node', self.name, 'stopped')
        except Exception as e:
            print('error while removing node {}: {}'.format(self.name, e))

    def put_sting(self, path, string):
        if self.loaded:

            tar = tarfile.TarFile(mode='w', fileobj=io.BytesIO())

            filename = os.path.basename(path)
            dirname = os.path.dirname(path)

            file_like = io.BytesIO(string.encode())

            info = tarfile.TarInfo(name=filename)
            info.size = len(file_like.getbuffer())

            tar.addfile(tarinfo=info, fileobj=file_like)

            self.container.put_archive(dirname, tar.fileobj.getvalue())

        else:
            self._files[path] = string

    def _deploy_routes(self):

        if any([isinstance(n, DockerSubnet) for n in self.subnets]) and not self.connect_to_internet:
            status_code, output = self.container.exec_run('ip route delete default')

            if status_code:
                print('Error({2}) while removing default docker route for {0}:\n{1}'.format(
                    self.name, output.decode(), status_code))

        for ip_range, gateway in self._routes.items():
            status_code, output = self.container.exec_run('ip route add {} via '.format(ip_range) + gateway)
            if status_code:
                print('Error({2}) while setting routes for {0}:\n{1}'.format(self.name, output.decode(), status_code))


