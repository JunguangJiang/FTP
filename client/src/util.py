'''
与ftp实现相关的函数
'''

import socket
import random
import zipfile
import os


def get_host_ip(conn):
    '''
    :param conn: 是一个已经建立的连接
    :return: 本机ip地址
    '''
    return conn.getsockname()[0]


def is_port_used(ip, port):
    '''
    检查端口是否被占用
    :param ip:
    :param port:
    :return:
    '''
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, port))
        return True
    except OSError:
        return False
    finally:
        s.close()

def produce_random_port(ip):
    '''
    :param ip:主机的ip
    生成随机的端口号，且保证端口号未被占用
    :return:
    '''
    port = random.randint(20001, 65534)
    while is_port_used(ip, port):
        port = random.randint(20001, 65534)
    p1 = int(port / 256)
    p2 = port - p1 * 256
    return (p1, p2)


def human_readable_size(size):
    '''
    将以字节为单位的size转化为更加适合人阅读的大小
    :param size: 一个整数或者浮点数
    :return: 字符串
    '''
    exp = 0
    size = float(size)
    while size >= 1000 and exp < 3:
        exp += 1
        size = size/1000
    size = round(size, 2)
    units = ["B", "KB", "MB", "GB"]
    return '{:g}{}'.format(size, units[exp])


def get_file_type(file_name, access_string):
    '''根据文件名file_name和访问权限access_string获取文件类型'''
    if access_string.startswith("d"):
        return "folder"
    else:
        list = file_name.split(".")
        if len(list) == 2:
            return list[1]
        else:
            return "unknown file"


def unzip(file_name, path):
    '''
    解压文件
    :param file_name: 原压缩文件
    :param path: 解压路径
    :return:
    '''
    zip_file = zipfile.ZipFile(file_name)
    for names in zip_file.namelist():
        zip_file.extract(names, path)
    zip_file.close()


def zip(folder_name):
    '''压缩文件夹，并返回压缩后的文件名'''
    zip_file_name = folder_name+".zip"
    f = zipfile.ZipFile(zip_file_name, "w")
    root_path = os.path.abspath(folder_name)  #原文件夹的根路径
    new_root_path = folder_name.split('/')[-1]
    for current_path, subfolders, filesname in os.walk(folder_name):
        fpath = current_path.replace(root_path, new_root_path)
        print(fpath)
        for file in filesname:
            f.write(os.path.join(current_path, file),os.path.join(fpath,file))
    f.close()
    return zip_file_name


def get_local_file_size(file_name):
    '''获取本地文件大小，如果文件不存在，则返回0'''
    try:
        local_file_size = os.path.getsize(file_name)
    except:
        local_file_size = 0
    return local_file_size

def get_zip_file_name(folder_name, zip_path):
    '''
    获取压缩后的文件名
    :param folder_name:原文件夹
    :param zip_path: 压缩路径
    :return:
    '''
    return zip_path + "/" + folder_name + ".zip"
