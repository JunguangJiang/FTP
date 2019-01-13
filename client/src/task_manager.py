import queue
from task import TransferTask


class TaskInfo:
    '''任务信息'''
    def __init__(self, id, type, local_file, remote_file, remote_path, task=None):
        self.id = id
        self.type = type
        self.local_file = local_file
        self.remote_file = remote_file
        self.remote_path = remote_path
        self.status = "Waiting"
        self.task = task

    def start(self, task):
        '''
        开始任务传输
        :param task: 一个传输任务类
        :return:
        '''
        self.task = task
        if task:
            self.status = "Going on"
            self.task.start_transfer(type=self.type, local_file=self.local_file, remote_file=self.remote_file,
                                remote_path=self.remote_path)  # 开始数据传输

    def debug(self):
        print(self.id, self.type, self.local_file, self.remote_file, self.remote_path, self.status, self.task)


class TaskManager:
    '''任务工厂'''
    def __init__(self, ip, port, user, password):
        self.ip = ip
        self.port = port
        self.user = user
        self.password = password
        self.going_on_tasks= []  #所有正在执行的任务
        self.waiting_tasks = []  #等待任务队列
        self.id_to_task = {}  # 将id映射成任务的一张表
        self.next_id = 0  # 接下来创建的任务的id
        self.max_occurs = 1  # 最大并发数

    def create_task(self,type, local_file, remote_file, remote_path):
        '''创建一个新任务'''
        taskInfo = TaskInfo(str(self.next_id), type, local_file, remote_file, remote_path)
        if not self.is_task_valid(taskInfo): #如果是一个无效任务
            taskInfo.status = "Invalid"
        elif len(self.going_on_tasks) >= self.max_occurs:  # 若任务总数已经超过max_occurs
            taskInfo.status = "Waiting"
            self.waiting_tasks.append(taskInfo)
        else:
            task = TransferTask()  #则创建一个新任务
            if not task.connect(self.ip, self.port, self.user, self.password):
                task.disconnect()
                taskInfo.status = "Failed"
            else:
                taskInfo.start(task)
                self.going_on_tasks.append(taskInfo)

        self.id_to_task[str(self.next_id)] = taskInfo
        self.next_id += 1
        self.debug()
        return taskInfo

    def recycle_task(self, taskInfo):
        '''回收一个任务,taskInfo是其任务信息'''
        taskInfo.status = "Finished"
        self.going_on_tasks.remove(taskInfo)
        task = taskInfo.task
        if len(self.waiting_tasks) > 0:
            new_taskInfo = self.waiting_tasks.pop(0)
            new_taskInfo.start(task)  # 开始数据传输
            self.going_on_tasks.append(new_taskInfo)
        else:
            task.disconnect()
        taskInfo.task = None
        self.debug()

    def get_task_by_id(self, id):
        '''根据任务编号获取对应的任务信息，如果任务不存在，则返回None'''
        return self.id_to_task.get(id, None)

    def __del__(self):
        for taskInfo in self.going_on_tasks:
            taskInfo.task.disconnect()

    def is_task_valid(self, taskInfo):
        '''如果和正在执行的任务或者等待的任务相冲突（远程文件名+路径相同）或者（本地文件名相同），则返回False'''
        list = self.waiting_tasks + self.going_on_tasks
        for t in list:
            if (taskInfo.remote_file == t.remote_file and taskInfo.remote_path == t.remote_path) or\
                    taskInfo.local_file == t.local_file:
                return False
        return True

    def debug(self):
        print("waiting task")
        for t in self.waiting_tasks:
            t.debug()
        print("going on task")
        for t in self.going_on_tasks:
            t.debug()

    def calculate_data_tranfer_rate(self, interval):
        '''
        计算传输速率
        :param interval: 查询时间间隔，以ms为单位
        :return: 返回下载速率和上传速率，单位为Mb/s
        '''
        local_file_increase = 0
        remote_file_increase = 0
        for taskInfo in self.going_on_tasks:
            task = taskInfo.task
            if taskInfo.type in ["GET", "REGET" , "GET_FOLDER"]:
                local_file_increase += task.get_local_file_increase()
            else:
                remote_file_increase += task.get_remote_file_increase()
        return float(local_file_increase)/1e3/interval, float(remote_file_increase)/1e3/interval
