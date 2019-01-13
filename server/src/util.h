/*
util.h声明了和ftp相关的结构体和常用的函数
*/
#ifndef SERVER_H
#define SERVER_H

#define BUFFER_SIZE 1024

//端口号
typedef struct Port
{
    int p1;
    int p2;
} Port;

//ftp命令
typedef struct Command{
    char command[7];
    char arg[BUFFER_SIZE];
} Command;

//不同的数据传输模式
typedef enum Data_connection_mode{
    DEFAULT_MODE,//nothing to transfer
    PASV_MODE,
    PORT_MODE
} Data_connection_mode;

//服务器上需要为每个客户端记录一个状态
typedef struct State
{    
    int logged_in;//用户是否已经登录
    char *username;//用户名
    int username_valid;//用户名是否合法

    char *message;//Response message to client

    int command_connection;//控制连接的套接字

    Data_connection_mode data_connection_mode;//数据传输模式

    int passive_connection;//PASS模式下，等待客户端连接的套接字

    int port_ip[4];//PORT模式下客户端的ip地址
    int port_port;//和端口号

    char root[BUFFER_SIZE];//远程用户登录时的根目录，在服务器上的相应路径

    //以下用于rnfr和rnto中修改文件名
    int old_name_sent;//是否已经发送旧名字
    char old_name[BUFFER_SIZE];//旧名字

    int rest_start;//REST命令指定的文件起始地址
}State;

//ftp命令种类
typedef enum Command_type{
    USER, PASS, RETR, STOR, QUIT, 
    SYST, TYPE, PORT, PASV, MKD, 
    CWD, PWD, LIST, RMD, ABOR,
    RNFR, RNTO,REST,APPE,STAT,
    DELE, ZIP, UNZIP
} Command_type;

//与之对应的命令字符串
static const char *command_strings[] = {
    "USER", "PASS", "RETR", "STOR", "QUIT", 
    "SYST", "TYPE", "PORT", "PASV", "MKD", 
    "CWD", "PWD", "LIST", "RMD", "ABOR",
    "RNFR", "RNTO","REST","APPE","STAT",
    "DELE", "ZIP", "UNZIP"
};
static const int command_count = 23;//命令总数

//在某个端口上监听连接,返回该监听连接的套接字
int create_listen_socket(int port);

//Port模式主动下连接到客户端，返回连接的套接字
int connect_to_client(State *state);

//将FTP命令字符串转化为命令结构体
void convert_string_to_command(char* command_string, Command *command);


//将FTP命令字符串转化为对应的编号
//返回command_count意味着没有对应的命令
int command_string_to_type(char* command_string);

//write current state to the client
// void write_state(State *state);

//send a message to a client
void write_message(State *state, const char *format,...);

//向网络连接发送文件
//in_fp: the local file pointer
//out_fd: socket to the client
int send_file(FILE *in_fp, int out_fd);

//从网络连接接受文件
//in_fp: the local file pointer
//out_fd: socket to the client
int receive_file(FILE *in_fp, int out_fd);

//将文件的绝对路径从服务器下转换到客户端下
void file_path_from_server_to_client(const char *host_file_path, char *client_file_path, char *root);

//将文件的路径从客户端下转换到服务器下
//前提：client_file_path非空
void file_path_from_client_to_server(const char *client_file_path, char *server_file_path, char *root);

//路径查看
//client_path是相对于客户端的目录
//返回1表示成功
int get_current_path_of_client(State *state, char *client_path);

//路径跳转
//client_path是相对于客户端的路径
//返回1表示成功
int change_current_path_of_client(State *state, char *client_path);

//判断当前上的port端口是否被占用
//返回1表示被占用；返回0表示未被占用
int is_port_used(Port *port);

//随机生成一个端口号
void generate_random_port(Port *port);

//从一个网络连接中获取本机的ip地址
void get_ip(int socket, int *ip);

//判断客户端是否已经登录，并作出响应处理
//返回0，表示没有登录；返回1表示已经登录
int check_logged_in(State* state);

//根据此前的连接模式建立数据连接
//返回连接的套接字
//返回-2表示连接模式错误
//返回-1表示没有接受到连接
int establish_data_connectioin(State *state);

//获取文件存取权限字符串
void get_file_access_string(mode_t st_mode, char *access_string);

//获取当前时间格式化后的字符串
void convert_time_to_string(time_t rawtime, char *string);

//获取文件大小，返回文件的字节数
//如果文件不存在，则返回-1
long get_file_size(char *file_name);

//获取文件信息，并将其存入file_info中
//如果成功返回1；否则返回0
int get_file_info(char *file_name, char *file_info);

//判断串s1是否是串s2的前缀
int is_prefix(char *s1, char *s2);
#endif