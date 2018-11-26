from dagon import Batch
from dagon.remote import RemoteTask
from dockercontainer.container import Container
from dockercontainer.docker_client import DockerClient
from dockercontainer.docker_client import DockerRemoteClient
from task import Task


class LocalDockerTask(Task):

    # Params:
    # 1) name: task name
    # 2) command: command to be executed
    # 3) image: docker image which the container is going to be created
    # 4) host: URL of the host, by default use the unix local host
    def __init__(self, name, command, image, container_id=None, working_dir=None, endpoint=None, remove=True):
        Task.__init__(self, name, command, working_dir=working_dir)
        self.command = command
        self.container_id = container_id
        self.working_dir = working_dir
        self.container = None
        self.remove = remove
        self.image = image
        self.endpoint = endpoint
        self.docker_client = DockerClient()

    def as_json(self):
        json_task = Task.as_json(self)
        json_task['command'] = self.command
        return json_task

    # process the command to execute
    """def process_body_command(self, body, arg, dst_path, local_path):
        print body
        body = Task.process_body_command(body, arg, dst_path, local_path)
        body = self.container.exec_in_cont(body)
        return body"""

    def include_command(self, body):
        body = super(LocalDockerTask, self).include_command(body)
        body = "cd " + self.working_dir + ";" + body
        body = self.container.exec_in_cont(body) + "\n"
        return body

    # Method execute
    def execute(self):
        if self.container is None:
            self.container_id = self.create_container() if self.container_id is None else self.container_id
            self.container = Container(self.container_id.rstrip(), self.docker_client)
        super(LocalDockerTask, self).execute()

    # Create a Docker container
    def create_container(self):
        command = DockerClient.form_string_cont_creation(image=self.image, detach=True,
                                                         volume={"host": self.workflow.get_scratch_dir_base(),
                                                                 "container": self.workflow.get_scratch_dir_base()})
        result = self.docker_client.exec_command(command)
        if result['code']:
            raise Exception(self.result["message"].rstrip())
        return result['output']

    def remove_container(self):
        self.container.stop()
        if self.remove:
            self.container.rm()

    def on_execute(self, launcher_script, script_name):
        # Invoke the base method
        Task.on_execute(self, launcher_script, script_name)
        return Batch.execute_command("bash " + self.working_dir + "/.dagon/" + script_name)
        # return self.docker_client.exec_command(self.working_dir + "/.dagon/" + script_name)"""

    def on_garbage(self):
        super(LocalDockerTask, self).on_garbage()
        self.remove_container()


class DockerRemoteTask(LocalDockerTask, RemoteTask):
    def __init__(self, name, command, image=None, container_id=None, ip=None, ssh_username=None, keypath=None,
                 working_dir=None, remove=True):
        LocalDockerTask.__init__(self, name, command, container_id=container_id, working_dir=working_dir, image=image,
                                 remove=remove)
        RemoteTask.__init__(self, name=name, ssh_username=ssh_username, keypath=keypath, command=command, ip=ip,
                            working_dir=working_dir)

        self.docker_client = DockerRemoteClient(self.ssh_connection)

    def on_execute(self, launcher_script, script_name):
        RemoteTask.on_execute(self, launcher_script, script_name)
        return self.ssh_connection.execute_command("bash " + self.working_dir + "/.dagon/" + script_name)

    def on_garbage(self):
        RemoteTask.on_garbage(self)
        self.remove_container()




class DockerTask(Task):

    def __init__(self, name, command, image,  container_id=None, ip=None, port=None, ssh_username=None, keypath=None,
                working_dir=None, local_working_dir=None, endpoint=None, remove=True):
        Task.__init__(self, name)

    def __new__(cls, name, command, image,  container_id=None, ip=None, port=None, ssh_username=None, keypath=None,
                working_dir=None, local_working_dir=None, endpoint=None, remove=True):
        is_remote = ip is not None
        if is_remote:
            return DockerRemoteTask(name, command, image=image, container_id=container_id, ip=ip,
                                    ssh_username=ssh_username, working_dir=working_dir, keypath=keypath, remove=remove)
        else:
            return LocalDockerTask(name, command, image, container_id=container_id, working_dir=working_dir,
                                   remove=remove)