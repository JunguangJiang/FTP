'''
FTP客户端的命令行程序
'''

from client import Client
import getpass
import sys

DEBUG_MODE=False

class ClientCmd:
    '''ftp客户端命令行程序'''
    def __init__(self, ip='127.0.0.1', port=21):
        self.client = Client()
        self.command_map = {
            "get": self.client.get,
            "reget": self.client.reget,
            "put": self.client.put,
            "reput": self.client.reput,
            "append": self.client.append,
            "ls": self.client.ls,
            "cd": self.client.cd,
            "mkdir": self.client.mkdir,
            "pwd": self.client.pwd,
            "rmdir": self.client.rmdir,
            "system": self.client.system,
            "rename": self.client.rename,
            "sendport": self.client.sendport,
            "passive": self.client.passive,
            "bye": self.client.bye,
            "quit":self.client.bye,
            "size":self.client.size,
            "delete":self.client.delete,
            "open": self.__open,
            "close": self.client.close,
            "zip": self.client.zip,
            "unzip": self.client.unzip,
            "put_folder":self.client.put_folder,
            "get_folder":self.client.get_folder
        }
        self.ip = ip
        self.port = port

    def __login(self):
        '''
        登录的交互过程
        :return:返回登录是否成功
        '''
        username = input('Username:')
        response = self.client.user(username)
        if response.startswith("331"):
            password = getpass.getpass('Password:')
            response = self.client.password(password)
            return response.startswith("230")
        return False

    def __open(self, ip='127.0.0.1', port=21):
        '''为了在打开连接后，提示用户输入用户名、密码等信息，需要对client提供的open进一步封装'''
        self.client.open(ip, port)
        self.__login()

    def __parse_input(self, input):
        '''
        对输入命令进行解析
        :param input: 输入数据
        :return: 如果输入合法，则返回需要调用的方法和传递给方法的参数；否则返回均为空
        '''
        args = input.split()
        if(len(args) == 0):
            return (None, None)
        cmd = self.command_map.get(args[0])
        if cmd: #存在该命令
            return (cmd, args[1:])
        else: #不存在该命令
            return (None, None)

    def __run_func(self, func, args):
        '''
        运行某个函数
        :param func: 函数
        :param args: 函数参数
        :return:
        '''
        if func:
            try:
                func(*args)
            except:
                print("?Invalid argument")
        else:
            print("?Invalid command")

    def run(self):
        '''运行程序'''
        welcome = self.client.open(self.ip, self.port)
        if not welcome:
            return

        if DEBUG_MODE:
            self.client.user("anonymous")
            self.client.password("33")
        else:
            self.__login()  # 登录界面

        while True:
            data = input('ftp>')
            cmd_func, args = self.__parse_input(data)
            self.__run_func(cmd_func, args)
            if data.startswith("bye") or data.startswith("quit"):
                break


if __name__ == '__main__':
    import sys
    argv = sys.argv
    ip = '127.0.0.1'
    port = 21
    if(len(argv) >= 3):
        port = int(argv[2])
    if(len(argv) >= 2):
        ip = argv[1]
    clientCmd = ClientCmd(ip, port)
    clientCmd.run()

