'''
FTP客户端的核心逻辑代码
'''
import socket
import re
from util import *
import util
import os

BUFFER_SIZE=1024

class Client:
    def __init__(self):
        self.__command_connection = None #命令连接
        self.__data_connection = None #数据连接
        self.__listen_connection = None  #监听连接
        self.__data_connection_mode = "PORT" #默认传输模式是PASV模式
        self.__latest_response = None #最近接收到的一条消息
        self.transfer_bytes = 0#数据传输已经完成传输的字节数，在开始一次新的传输时会将其置零

    def open(self, ip='127.0.0.1', port=21):
        '''建立指定ftp服务器连接，可指定连接端口'''
        self.__command_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        addr = (ip, int(port))
        try:
            print("Connected to %s"%ip)
            self.__command_connection.connect(addr)
            self.__recv()
            return True
        except:
            print("Fail to connect %s"%ip)
            return False

    def close(self):
        '''中断与远程服务器的ftp会话(与open对应)'''
        if self.__listen_connection:  #如果正在进行监听
            self.__listen_connection.close()  #则关闭监听
        if self.__data_connection:  #如果正在进行文件传输
            print("Data connection closed")
            self.__data_connection.close()  #那么将文件传输也关闭
        if self.__command_connection:
            print("Close connection")
            self.__command_connection.close()
        else:
            print("No connection built")

    def __recv(self):
        '''从服务器接受数据'''
        f = self.__command_connection.makefile()
        line = f.readline()
        if line[3:4] == '-':
            code = line[:3]
            while True:
                nextline = f.readline()
                line = line +  nextline
                if nextline[:3] == code and nextline[3:4] != '-':
                    break
        self.__latest_response = line
        print(self.__latest_response,end="")
        return self.__latest_response

    def __send(self, data):
        '''向服务器发送数据data'''
        data+=("\r\n")
        self.__command_connection.send(data.encode('utf8'))

    def request(self,data):
        '''
        :param data: 向服务器发送的数据
        :return: 从服务器得到的响应
        '''
        self.__send(data)
        return self.__recv()

    def __create_PASV_data_connection(self):
        '''建立PASV模式下的数据连接。成功返回True'''
        response = self.request("PASV")
        m = re.search("\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)", response)
        if m:
            self.__passive_ip = "{0}.{1}.{2}.{3}".format(m.group(1), m.group(2), m.group(3), m.group(4))
            self.__passive_port = int(m.group(5)) * 256 + int(m.group(6))
            self.__data_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__data_connection.connect((self.__passive_ip, self.__passive_port))
            return True
        else:
            return False

    def __create_PORT_listen_connection(self):
        '''建立PORT模式下的监听。成功返回True'''
        ip = get_host_ip(self.__command_connection)
        p1, p2 = produce_random_port(ip)
        self.__listen_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__listen_connection.bind((ip, p1 * 256 + p2))
        self.__listen_connection.listen()
        ip = ip.replace('.', ',')
        response = self.request("PORT {0},{1},{2}".format(ip, p1, p2))
        return response.startswith("200")

    def __create_PORT_data_connection(self):
        '''建立PORT模式下的数据连接'''
        self.__data_connection,_ = self.__listen_connection.accept()
        self.__listen_connection.close()
        self.__listen_connection = None

    def user(self, username):
        '''发送用户名'''
        return self.request("USER {}".format(username))

    def password(self, password):
        '''发送密码'''
        return self.request("PASS {}".format(password))

    def __send_file(self, local_file, remote_file=None, mode="put"):
        '''
        将本地文件local-file传送至远程主机，由于put，reput，append命令的实现方式较为类似，因此对其统一实现
        :param local_file:
        :param remote_file:
        :param mode: 传送模式，有"put","reput","append"三种模式
        :return: 成功返回True，失败返回False
        '''
        if not remote_file:
            remote_file = local_file

        remote_file_size = 0
        if mode == "reput": #在reput模式下，需要将本地的读文件指针指向上次发送文件中断的位置
            remote_file_size = self.size(remote_file) #因此，需要获取远程文件的大小
            local_file_size = os.path.getsize(local_file)
            print("remote:{}, local:{}".format(remote_file_size, local_file_size))
            if local_file_size <= remote_file_size:
                print("远程文件不小于本地文件，reput失败")
                return False

        if mode == "put":
            command = "STOR {}"
        else:
            command = "APPE {}"

        if self.__data_connection_mode == "PASV": #PASV模式下
            if self.__create_PASV_data_connection(): #成功打开数据连接
                response = self.request(command.format(remote_file))
                if not response.startswith("150"):
                    return False
            else:
                return False
        else:#PORT模式下
            if self.__create_PORT_listen_connection():#首先打开监听连接
                response = self.request(command.format(remote_file))
                if not response.startswith("150"):
                    return False
                self.__create_PORT_data_connection()
            else:
                return False

        with open(local_file, "rb") as f:
            f.seek(remote_file_size)
            while True:
                data = f.read(BUFFER_SIZE)
                if not data:
                    break
                self.__data_connection.send(data)

        self.__data_connection.close()
        self.__data_connection = None
        self.__recv()
        return True

    def put(self, local_file, remote_file=None):
        '''将本地local_file传至远程主机，local_file是文件类型'''
        return self.__send_file(local_file,remote_file, "put")

    def put_folder(self, local_file, remote_file=None):
        '''将本地文件夹local_file传至远程主机的remote_file目录下'''
        if not os.path.exists(local_file): #文件不存在
            self.__latest_response = "{}文件不存在".format(local_file)
            return False
        local_zip_file_name = util.zip(local_file) #首先将本地的文件夹压缩
        if not remote_file:
            remote_file = '.'
        remote_zip_file_name = remote_file + "/" + local_file.split('/')[-1] + '.zip'
        if not self.put(local_file=local_zip_file_name,remote_file=remote_zip_file_name): #然后传输压缩后的文件
            return False
        if not self.unzip(remote_zip_file_name).startswith("250"): #在远程服务器上解压文件
            return False
        self.delete(remote_zip_file_name) #最后清理服务器上压缩文件
        os.remove(local_zip_file_name) #以及本地的文件
        return True

    def reput(self, local_file, remote_file=None):
        '''类似于put，但若remote-file存在，则从上次传输中断处续传'''
        return self.__send_file(local_file,remote_file,"reput")

    def append(self, local_file, remote_file=None):
        '''将本地文件追加到远程系统主机，若未指定远程系统文件名，则使用本地文件名'''
        return self.__send_file(local_file, remote_file, "append")

    def __receive_file(self, remote_file, local_file=None, mode="get"):
        '''
        将远程主机的文件remote_file传至本地硬盘的local_file
        :param remote_file:
        :param local_file:
        :param mode: 传输模式：有get和reget两种选择
        :return: 成功返回True，失败返回False
        '''
        if not local_file:
            local_file = remote_file.split('/')[-1]

        if not os.path.exists(local_file):
            rest_start = 0
        else:
            rest_start = os.path.getsize(local_file) #重传开始的位置

        if mode == "reget":
            response = self.request("REST {}".format(rest_start))
            if not response.startswith("350"):
                print("The server doesn't support REST!")
                return False

        if self.__data_connection_mode == "PASV": #PASV模式下
            if self.__create_PASV_data_connection(): #成功打开数据连接
                response = self.request("RETR {}".format(remote_file))
                if not response.startswith("150"):
                    return False
            else:
                return False
        else:#PORT模式下
            if self.__create_PORT_listen_connection():#首先打开监听连接
                response = self.request("RETR {}".format(remote_file))
                if not response.startswith("150"):
                    return False
                self.__create_PORT_data_connection()
            else:
                return False

        if mode == "get":
            write_mode = "wb"
        else:
            write_mode = "ab"
        with open(local_file, write_mode) as f:
            while True:
                data = self.__data_connection.recv(BUFFER_SIZE)
                f.write(data)
                if not data:
                    break

        self.__data_connection.close()
        self.__data_connection = None #数据连接
        self.__recv()
        return True

    def get(self, remote_file, local_file=None):
        '''将远程主机的文件remote-file传至本地硬盘的local-file，local_file是文件类型'''
        return self.__receive_file(remote_file, local_file, "get")

    def get_folder(self, remote_file, local_file=None):
        '''将远程主机的文件夹remote_file传至本地local_file文件夹下'''
        if not self.zip(remote_file).startswith("250"): #压缩远程文件夹
            return False

        if not local_file:
            local_file = "."
        elif not os.path.exists(local_file):
            os.mkdir(local_file)

        remote_zip_file_name = remote_file + ".zip"
        local_zip_file_name = local_file+"/"+remote_file.split('/')[-1]+".zip"
        if not self.get(remote_file=remote_zip_file_name, local_file=local_zip_file_name): #然后传输压缩后的文件
            return False
        util.unzip(local_zip_file_name, path=local_file) # 在本地解压文件
        self.delete(remote_zip_file_name) #最后清理服务器上压缩文件
        os.remove(local_zip_file_name) #以及本地的压缩文件
        return True


    def reget(self, remote_file, local_file=None):
        '''类似于get，但若local-file存在，则从上次传输中断处续传'''
        return self.__receive_file(remote_file, local_file, "reget")

    def delete(self, remote_file):
        '''删除远程主机文件'''
        return self.request("DELE {}".format(remote_file))

    def ls(self, remote_dir=None, local_file=None):
        '''
        显示远程目录remote_dir，并存入本地文件local_file。
        :return: ls是否成功
        '''
        if not remote_dir:
            remote_dir = "."

        if self.__data_connection_mode == "PASV": #PASV模式下
            if self.__create_PASV_data_connection(): #成功打开数据连接
                response = self.request("LIST {}".format(remote_dir))
                if not response.startswith("150"):
                    return False
            else:
                return False
        else:#PORT模式下
            if self.__create_PORT_listen_connection():#首先打开监听连接
                response = self.request("LIST {}".format(remote_dir))
                if not response.startswith("150"):
                    return False
                self.__create_PORT_data_connection()
            else:
                return False

        if local_file: #如果需要写入文件
            with open(local_file, "wb") as f:
                while True:
                    data = self.__data_connection.recv(BUFFER_SIZE)
                    f.write(data)
                    if not data:
                        break
        else:#如果不需要写入文件
            while True:
                data = self.__data_connection.recv(BUFFER_SIZE)
                print(data.decode('utf8'),end="")
                if not data:
                    break

        self.__data_connection.close()
        self.__data_connection = None
        self.__recv()
        return True

    def cd(self, remote_dir):
        '''进入远程主机目录'''
        return self.request("CWD {}".format(remote_dir))

    def mkdir(self, dir_name):
        '''在远程主机中建一目录'''
        return self.request("MKD {}".format(dir_name))

    def pwd(self):
        '''显示远程主机的当前工作目录'''
        return self.request("PWD")

    def rmdir(self, dir_name):
        '''删除远程主机目录'''
        return self.request("RMD {}".format(dir_name))

    def bye(self):
        '''退出ftp会话过程'''
        return self.request("QUIT")

    def system(self):
        '''显示远程主机的操作系统类型'''
        return self.request("SYST")

    def type(self):
        return self.request("TYPE I")

    def rename(self, from_name, to_name):
        '''
        更改远程主机文件名
        :param from_name:旧名字
        :param to_name:新名字
        :return: 更改是否成功
        '''
        self.request("RNFR {}".format(from_name))
        return self.request("RNTO {}".format(to_name))

    def sendport(self):
        '''设置PORT命令的使用'''
        self.__data_connection_mode = "PORT"
        print("Use of PORT cmds on.")

    def passive(self):
        '''进入被动传输方式'''
        self.__data_connection_mode = "PASV"
        print("Passive mode on")

    def size(self, file_name):
        '''显示远程主机文件大小。如果文件不存在，则返回大小为0'''
        response = self.request("STAT {}".format(file_name))
        m = re.search("(\d+)\s[A-Z][a-z]{2}\s[\s\d]\d", response)
        if m:
            size = int(m.group(1))
        else:
            size = 0
        return size

    def get_latest_response(self):
        '''获取最近的回复'''
        return self.__latest_response

    def zip(self, folder_name):
        '''压缩文件夹'''
        return self.request("ZIP {}".format(folder_name))

    def unzip(self, file_name):
        '''解压文件'''
        return self.request("UNZIP {}".format(file_name))