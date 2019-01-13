#include <stdio.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#include <ctype.h>
#include <memory.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdarg.h> 
#include <netinet/tcp.h>

#include "util.h"

//在某个端口上监听连接,返回该监听连接的套接字
int create_listen_socket(int port)
{
    int listenfd;
    struct sockaddr_in addr;

    //create a socket
    if((listenfd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)) == -1){
        fprintf(stderr, "Error create listen socket(): %s(%d)\n", strerror(errno), errno);
        exit(EXIT_FAILURE);
    }

    //set the ip and port
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    addr.sin_addr.s_addr = htonl(INADDR_ANY); //listen to all ips

    int reuse = 1;
    setsockopt(listenfd, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof reuse);//让端口释放后立即就可以被再次使用

    //bind the ip and port to the socket
    if(bind(listenfd, (struct sockaddr*)&addr, sizeof(addr)) == -1){
        fprintf(stderr, "Error bind(): %s(%d)\n", strerror(errno), errno);
        exit(EXIT_FAILURE);
    }

    //开始监听socket
	if (listen(listenfd, 10) == -1) {
		fprintf(stderr, "Error listen(): %s(%d)\n", strerror(errno), errno);
        exit(EXIT_FAILURE);
	}

    return listenfd;
}

//Port模式主动下连接到客户端，返回连接的套接字
int connect_to_client(State *state)
{
    int sockfd;
	struct sockaddr_in addr;

	//创建socket
	if ((sockfd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)) == -1) {
		printf("Error socket(): %s(%d)\n", strerror(errno), errno);
		return -1;
	}

	//设置目标主机的ip和port
	memset(&addr, 0, sizeof(addr));
	addr.sin_family = AF_INET;
	addr.sin_port = htons(state->port_port);
    char host[BUFFER_SIZE];
    memset(host, 0, BUFFER_SIZE);
    sprintf(host, "%d.%d.%d.%d", state->port_ip[0], state->port_ip[1],state->port_ip[2], state->port_ip[3]);

	if (inet_pton(AF_INET, host, &addr.sin_addr) <= 0) {//转换ip地址:点分十进制-->二进制
		printf("Error inet_pton(): %s(%d)\n", strerror(errno), errno);
		return -1;
	}

	//连接上目标主机（将socket和目标主机连接）-- 阻塞函数
	if (connect(sockfd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
		printf("Error connect(): %s(%d)\n", strerror(errno), errno);
		return -1;
	}
    return sockfd;
}

//将FTP命令字符串转化为命令结构体
void convert_string_to_command(char* command_string, Command *command)
{
    sscanf(command_string, "%s %s", command->command, command->arg);
}

//将FTP命令字符串转化为对应的编号
//返回command_count意味着没有对应的命令
int command_string_to_type(char* command_string){
    int i = 0;
    for(; i<command_count; i++){
        if(strcmp(command_string, command_strings[i]) == 0){
            break;
        }
    }
    return i;
}

//write current state to the client
void write_state(State *state)
{
    write(state->command_connection, state->message, strlen(state->message));
}

//send a message to a client
void write_message(State *state, const char *format,...)
{
    va_list arg ;
    va_start(arg, format);
    char buffer[BUFFER_SIZE];
    vsprintf(buffer, format, arg);
    va_end(arg);
    state->message = buffer;
    write_state(state);
}

//向网络连接发送文件
//in_fp: the local file pointer
//out_fd: socket to the client
int send_file(FILE *in_fp, int out_fd)
{
    char buffer[BUFFER_SIZE];
    bzero(buffer, BUFFER_SIZE);
    int send_count = 0;
    int length = 0;
    //repeat reading data and sending it to the client until the whole file is read
    while((length = fread(buffer, sizeof(char), BUFFER_SIZE, in_fp)) > 0){
        if(send(out_fd, buffer, length, 0) < 0){
            return -1;
        }
        send_count += length;
        bzero(buffer, BUFFER_SIZE);
    }
    return send_count;
}

//从网络连接接受文件
//in_fp: the local file pointer
//out_fd: socket to the client
int receive_file(FILE *in_fp, int out_fd)
{
    char buffer[BUFFER_SIZE];
    bzero(buffer, BUFFER_SIZE);
    int receive_count = 0;
    int length = 0;
    while((receive_count = read(out_fd, buffer, BUFFER_SIZE)) > 0){
        length += fwrite(buffer, sizeof(char), receive_count, in_fp);
        bzero(buffer, BUFFER_SIZE);
    }
    if(receive_count < 0){//if the network is broken
        return -1;
    }else{
        return length;
    }
}

//将文件的绝对路径从服务器下转换到客户端下
void file_path_from_server_to_client(const char *server_file_path, char *client_file_path, char *root)
{
    char format[BUFFER_SIZE];
    memset(format,0,BUFFER_SIZE);
    strcpy(format, root);
    strcat(format, "%s");
    sscanf(server_file_path, format, client_file_path);
    if(strlen(client_file_path) == 0){
        strcpy(client_file_path, "/");
    }
}

//将文件的路径从客户端下转换到服务器下
//前提：client_file_path非空
void file_path_from_client_to_server(const char *client_file_path, char *server_file_path, char *root)
{
    if(client_file_path[0] == '/'){//客户端下的路径是绝对路径
        strcpy(server_file_path, root);
        strcat(server_file_path, client_file_path);//返回的服务器路径也是绝对路径
    }else{//客户端下的路径是相对路径
        strcpy(server_file_path, client_file_path);//直接返回其即可
    }
}

//路径查看
//client_path是相对于客户端的目录
//返回1表示成功
int get_current_path_of_client(State *state, char *client_path)
{
    char server_path[BUFFER_SIZE];
    memset(server_path,0,BUFFER_SIZE);
    if(getcwd(server_path, BUFFER_SIZE) != NULL){//获得服务器上的绝对路径
        file_path_from_server_to_client(server_path, client_path, state->root);
        return 1;
    }else{
        return 0;
    }
}

//路径跳转
//client_path是相对于客户端的路径
//返回1表示成功
int change_current_path_of_client(State *state, char *client_path)
{
    if(strlen(client_path) == 0) return 0;
    char server_path[BUFFER_SIZE];
    memset(server_path, 0, BUFFER_SIZE);
    file_path_from_client_to_server(client_path, server_path, state->root);
    printf("change to server path:%s\n", server_path);
    int result = chdir(server_path);
    if(result == -1){//更改路径失败
        return 0;
    }else{//更改路径成功
        memset(server_path, 0, BUFFER_SIZE);
        getcwd(server_path, BUFFER_SIZE);//此时服务器上的路径
        if(!is_prefix(state->root, server_path)){//如果进入了非法的目录下
            chdir(state->root);//则默认回到客户端下的根目录
        }
        return 1;//更改路径成功
    }
}

//判断当前上的port端口是否被占用
//返回1表示被占用；返回0表示未被占用
int is_port_used(Port *port)
{
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port->p1*256+port->p2);
    inet_pton(AF_INET, "0.0.0.0", &addr.sin_addr);
    if (bind(fd, (struct sockaddr *) (&addr), sizeof(addr)) < 0) {
        close(fd);
        return 1;
    }else{
        close(fd);
        return 0;
    }
}

//随机生成一个端口号
void generate_random_port(Port *port)
{
    port->p1 = 128 + (rand() % 64);
    port->p2 = rand() % 256;
}

//从一个网络连接中获取本机的ip地址
void get_ip(int socket, int *ip)
{
    socklen_t addr_size = sizeof(struct sockaddr_in);
    struct sockaddr_in addr;
    getsockname(socket, (struct sockaddr *)&addr, &addr_size);

    char* host = inet_ntoa(addr.sin_addr);
    sscanf(host, "%d.%d.%d.%d", &ip[0], &ip[1], &ip[2], &ip[3]);
}

//判断客户端是否已经登录，并作出响应处理
//返回0，表示没有登录；返回1表示已经登录
int check_logged_in(State* state)
{
    if(state->logged_in){
        return 1;
    }else{
        state->message = "530 Please login with USER and PASS.\r\n";
        write_state(state);
        return 0;
    }
}

//根据此前的连接模式建立数据连接
//返回连接的套接字
//返回-2表示连接模式错误
//返回-1表示没有接受到连接
int establish_data_connectioin(State *state)
{
    int data_connection = -2;
    if(state->data_connection_mode == PASV_MODE){
        data_connection = accept(state->passive_connection, NULL, NULL);//wait for a connection from the client
        close(state->passive_connection);
    }else if(state->data_connection_mode == PORT_MODE){
        data_connection = connect_to_client(state);
    }else{//PASV和PORT都未发送
        write_message(state, "425 Use PASV or PORT first.\r\n");
    }
    if(data_connection == -1){//TCP连接尚未建立
        write_message(state, "425 No TCP connection was established.\r\n");
    }
    state->data_connection_mode = DEFAULT_MODE;//stop accepting new connections
    return data_connection;
}

//获取文件存取权限字符串
void get_file_access_string(mode_t st_mode, char *access_string)
{
    int i=8;
    while(i>=0){
        if((st_mode) & (1<<i)){
            switch(i % 3){
                case 2:strcat(access_string, "r");break;
                case 1:strcat(access_string, "w");break;
                case 0:strcat(access_string, "x");break;
            }
        }else{
            strcat(access_string, "-");
        }
        i--;
    }
}

//获取当前时间格式化后的字符串
void convert_time_to_string(time_t rawtime, char *string)
{
    struct tm *time = localtime(&rawtime);
    strftime(string, BUFFER_SIZE, "%a %d %H:%M", time);
}

//获取文件大小，返回文件的字节数
//如果文件不存在，则返回-1
long get_file_size(char *file_name)
{
    FILE* fp = fopen(file_name, "rb");
    if(fp){
        fseek(fp, 0, SEEK_END);//go to the end of the file
        long file_size = ftell(fp);//get the byte size of the file
        return file_size;
        fclose(fp);
    }else{
        return -1;
    }
}

//获取文件信息，并将其存入file_info中
//file_name必须是服务器下的绝对或者相对路径
//如果成功返回1；否则返回0
int get_file_info(char *file_name, char *file_info)
{
    struct stat statbuf;
    if(stat(file_name, &statbuf) == -1){
        fprintf(stderr, "Error reading file stats...\n");
        return 0;
    }else{
        char access_string[BUFFER_SIZE];
        memset(access_string, 0, BUFFER_SIZE);
        get_file_access_string(statbuf.st_mode, access_string);

        char time_string[BUFFER_SIZE];
        memset(time_string, 0, BUFFER_SIZE);
        convert_time_to_string(statbuf.st_mtime, time_string);

        sprintf(file_info, "%c%s %5ld %5d %5d %13ld %s %s\r\n",
        (S_ISDIR(statbuf.st_mode))?'d':'-',
        access_string,//文件访问权限
        statbuf.st_nlink,
        statbuf.st_uid,
        statbuf.st_gid,
        statbuf.st_size,//文件大小
        time_string,//最近修改时间
        file_name//文件名
        );

        return 1;
    }
}

//判断串s1是否是串s2的前缀
int is_prefix(char *s1, char *s2)
{
    char *s = strstr(s2,s1);//在s2中查找s1
    if(s && (s == s2)){//如果s1是s2的子串，并且首次发现位置在s2的开头
        return 1;
    }else{
        return 0;
    }
}