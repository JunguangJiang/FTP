from client import Client
import os
import threading
import util

class TaskThread(threading.Thread):
    '''数据传输线程'''
    def __init__(self,func,args=[], kwargs={}):
        super(TaskThread,self).__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.result = self.func(*self.args, **self.kwargs)

    def get_result(self):
        try:
            return self.result
        except Exception:
            return None


class TransferTask:
    '''数据传输任务'''
    def __init__(self):
        self.client = Client()
        self.type = None
        self.local_file = None
        self.remote_file = None
        self.local_zipped_file = None
        self.remote_zipped_file = None
        self.local_file_size = 0
        self.remote_file_size = 0
        self.thread = None  #用于数据传输的进程
        self.transfer_func= {
            "GET":self.client.get,
            "PUT":self.client.put,
            "REPUT":self.client.reput,
            "REGET":self.client.reget,
            "APPEND":self.client.append,
            "GET_FOLDER":self.client.get_folder,
            "PUT_FOLDER":self.client.put_folder
        }
        self.local_file_increase = 0  #本地文件大小增长
        self.remote_file_increase = 0  #远程文件大小增长
        self.origin_remote_file_size = 0  #记录APPEND下，远程文件的初始大小

    def connect(self, ip, port, user, password):
        '''建立连接，会返回连接是否成功'''
        if not self.client.open(ip, port):  # 连接失败
            print("Fail to create a new transfer task--Can not open the ip")
            return False
        self.client.user(user)
        reply = self.client.password(password)
        if reply.startswith("5"):  # 若登录失败
            print("Fail to login!")
            return False
        else:
            return True

    def disconnect(self):
        self.client.bye()
        self.client.close()

    def start_transfer(self, type, local_file, remote_file, remote_path):
        '''
        开始一个传输任务
        :param type: 任务类型
        :param local_file: 本地文件名
        :param remote_file: 远程文件名
        :param remote_path: 远程文件夹路径
        :return:
        '''
        self.type = type
        self.local_file = local_file
        self.remote_file = remote_file
        self.client.cd(remote_path) #首先进入远程文件夹下

        if type != "GET_FOLDER" and type != "PUT_FOLDER":
            self.remote_file_size = self.client.size(self.remote_file)  # 首先获取远程文件大小
            self.origin_remote_file_size = self.remote_file_size
            self.local_file_size = util.get_local_file_size(self.local_file) # 获取本地文件大小
        elif type == "GET_FOLDER":
            self.remote_zipped_file = self.remote_file+".zip"
            self.local_zipped_file = util.get_zip_file_name(
                    folder_name=self.remote_file.split('/')[-1], zip_path=self.local_file)
        elif type == "PUT_FOLDER":
            self.remote_zipped_file = util.get_zip_file_name(
                    folder_name=self.local_file.split('/')[-1], zip_path=self.remote_file)
            self.local_zipped_file = self.local_file + ".zip"

        self.thread = TaskThread(func=self.wrapper_task,
                                 kwargs={'type': type, 'remote_file': remote_file, 'local_file': local_file})
        self.thread.start()  #在新进程中进行文件的传输

    def query_status(self, client):
        '''
        查询当前的传输状态
        :param client:一个闲置的ftp客户端
        :return: 传输状态以及附加信息
        '''
        if not self.thread:
            return "Not started", None  #尚未开始

        # 判断传输是否完成以及是否成功
        result = self.thread.get_result()
        if result is not None: #如果进程已经结束
            self.clear()
            succeed, msg = result
            if succeed:
                return "Success", None
            else:
                return "Fail", msg

        # 若传输尚未完成
        # GET/REGET/PUT/REPUT情况下，进度=目的文件大小/源文件大小
        if self.type == "GET" or self.type == "REGET":
            self.update_file_size("LOCAL", util.get_local_file_size(self.local_file))  #反复查询本地文件大小
            if self.local_file_size >= self.remote_file_size or self.remote_file_size == 0:
                progress = 1.0
            else:
                progress = float(self.local_file_size) / float(self.remote_file_size)
        elif self.type == "PUT" or self.type == "REPUT":
            self.update_file_size("REMOTE", client.size(self.remote_file))  #反复查询远程文件大小
            if self.remote_file_size >= self.local_file_size or self.local_file_size == 0:
                progress = 1.0
            else:
                progress = float(self.remote_file_size) / float(self.local_file_size)

        # APPEND情况下，进度=传输的字节数/总共需要传输的字节数
        elif self.type == "APPEND":
            self.update_file_size("REMOTE", client.size(self.remote_file))  #反复查询远程文件大小
            if self.local_file_size == 0:
                progress = 1.0
            else:
                progress = float(self.remote_file_size-self.origin_remote_file_size)/float(self.local_file_size)

        # PUT_FOLDER和GET_FOLDER情况下，进度=压缩后的文件传输的字节数/压缩后的文件大小
        elif self.type == "PUT_FOLDER":
            if self.local_file_size == 0:
                self.local_file_size = util.get_local_file_size(self.local_zipped_file)
            if self.local_file_size == 0:
                return "Going on", "ZIPPING"  #本地文件正在压缩中
            else:
                self.update_file_size("REMOTE", client.size(self.remote_zipped_file)) #反复查询远程压缩文件大小
                progress = float(self.remote_file_size)/float(self.local_file_size)
        elif self.type == "GET_FOLDER":
            if self.remote_file_size == 0:
                self.remote_file_size = client.size(self.remote_zipped_file)
            if self.remote_file_size == 0:
                return "Going on", "ZIPPING" #远程服务器正在压缩文件中
            else:
                self.update_file_size("LOCAL", util.get_local_file_size(self.local_zipped_file))  #反复查询本地压缩文件大小
                progress = float(self.local_file_size)/float(self.remote_file_size)
        return "Going on", progress

    def wrapper_task(self, type, remote_file, local_file):
        '''包装一个数据传输任务，返回是否成功和最新的回复'''
        func = self.transfer_func[type]
        succeed = func(remote_file=remote_file,local_file=local_file)
        return succeed, self.client.get_latest_response()

    def clear(self):
        '''完成一次任务后，对任务进行数据清理'''
        self.type = None
        self.local_file = None
        self.remote_file = None
        self.local_zipped_file = None
        self.remote_zipped_file = None
        self.local_file_size = 0
        self.remote_file_size = 0
        self.thread = None  # 用于数据传输的进程
        self.origin_remote_file_size = 0

    def get_local_file_increase(self):
        '''获取本地文件大小增长，获取后立刻清零'''
        tmp = max(self.local_file_increase,0)
        self.local_file_increase = 0
        return tmp

    def get_remote_file_increase(self):
        '''获取远程文件大小增长，获取后立刻清零'''
        tmp = max(self.remote_file_increase,0)
        self.remote_file_increase = 0
        return tmp

    def update_file_size(self, type, new_file_size):
        '''更新文件大小'''
        if type == "LOCAL": #本地文件
            self.local_file_increase = new_file_size - self.local_file_size
            self.local_file_size = new_file_size
        elif type == "REMOTE": #远程文件
            self.remote_file_increase = new_file_size - self.remote_file_size
            self.remote_file_size = new_file_size

