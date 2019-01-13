/*
handle.c 中实现了对不同ftp命令的处理
*/
#include <string.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <errno.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <dirent.h>
#include "handle.h"


//Handle USER command
void handle_user(Command *cmd, State *state)
{
    if(strcmp(cmd->arg, "anonymous") == 0){
        write_message(state, "331 Guest login ok, send your complete e-mail address as password.\r\n");
        state->username_valid = 1;
    }else{
        write_message(state, "530 Invalid username\r\n");
    }
}

//Handle PASS command
void handle_pass(Command *cmd, State *state)
{
    if(state->username_valid == 1){
        //Here to test whether cmd->arg is an email address
        state->logged_in = 1;
        write_message(state,"230 Guest login ok, access restrictions apply.\r\n");
    }else{
        write_message(state, "530 Please login with USER and PASS.\r\n");
    }
}

//Handle PASV command
void handle_pasv(Command *cmd, State *state)
{
    if(!check_logged_in(state)) return;

    char ip_string[BUFFER_SIZE];
    memset(ip_string, 0, BUFFER_SIZE);

    int ip[4];
    Port *port = malloc(sizeof(Port));
    get_ip(state->command_connection, ip);
    generate_random_port(port);
    while(is_port_used(port)){//如果当前端口被占用
        generate_random_port(port);//则重新生成端口
    }

    close(state->passive_connection);//Close previous passive socket connection

    int port_number = (port->p1 * 256) + port->p2;
    state->passive_connection = create_listen_socket(port_number);
    state->data_connection_mode = PASV_MODE;

    write_message(state, "227 Entering Passive Mode (%d,%d,%d,%d,%d,%d).\r\n", ip[0], ip[1], ip[2], ip[3], port->p1, port->p2);
}

//Handle PORT command
void handle_port(Command *command, State *state)
{
    if(!check_logged_in(state)) return;

    Port *port = malloc(sizeof(Port));
    sscanf(command->arg, "%d,%d,%d,%d,%d,%d",&state->port_ip[0],&state->port_ip[1],&state->port_ip[2],&state->port_ip[3], &port->p1, &port->p2);
    state->port_port = port->p1 * 256 + port->p2;
    state->data_connection_mode = PORT_MODE;

    write_message(state, "200 Port command successful.\r\n");
}

//Handle RETR command
void handle_retr(Command *command, State *state)
{
    if(!check_logged_in(state)) return;
    
    write_message(state, "150 Opening BINARY mode data connection for %s.\r\n", command->arg);

    int data_connection = establish_data_connectioin(state);
    if(data_connection < 0) return;

    char server_file_path[BUFFER_SIZE];
    memset(server_file_path, 0, BUFFER_SIZE);
    file_path_from_client_to_server(command->arg, server_file_path, state->root);
    
    long file_size = get_file_size(server_file_path);//原先的文件大小
    FILE *fp;//local file pointer
    if( (access(server_file_path, R_OK) == 0) && //if can read the file
        (fp = fopen(server_file_path, "rb"))){//then open the file
        if(file_size < state->rest_start){//如果定位位置比文件大小还大
            printf("file_size:%ld,rest_start:%d\n", file_size, state->rest_start);
            write_message(state,"551 The file in the server is smaller than that in the client.\r\n");
        }else{
            fseek(fp, state->rest_start, SEEK_SET);//定位位置
            int send_count = send_file(fp, data_connection);//send the file through data_connection
            file_size = get_file_size(server_file_path);//新的文件大小
            if(send_count < 0){
                write_message(state, "426 TCP connection was broken by the client or by network failure.\r\n");
            }else{
                write_message(state, "226 Transfer complete.\r\n");
            }
        }
        fclose(fp);
    }else{//can not read the file
        fprintf(stderr, "Can not read the file");
        write_message(state,"551 Cannot read file from the disk.\r\n");
    }
    close(data_connection);
    state->rest_start = 0;//不论RETR命令是否成功，下一次文件下载开始位置都为0
}

//由于STOR命令和APPE命令非常相像，因此对其统一处理
//open_mode是打开的模式
void handle_stor_and_appe(Command *command, State *state, char *open_mode)
{
    if(!check_logged_in(state)) return;

    write_message(state, "150 Opening BINARY mode data connection for %s.\r\n", command->arg);

    int data_connection = establish_data_connectioin(state);
    if(data_connection < 0) return;
    
    char server_file_path[BUFFER_SIZE];
    memset(server_file_path, 0 ,BUFFER_SIZE);
    file_path_from_client_to_server(command->arg, server_file_path, state->root);
    FILE *fp;//local file pointer
    if((fp = fopen(server_file_path, open_mode))){//then open the file
        int receive_count = receive_file(fp, data_connection);
        if(receive_count < 0){
            write_message(state, "426 TCP connection was broken by the client or by network failure.\r\n");
        }else{
            write_message(state, "226 Transfer complete.\r\n");
        }
        fclose(fp);
    }else{//can not read the file
        fprintf(stderr, "Can not write the file");
        write_message(state, "451 Cannot write file to the disk.\r\n");
    }
    close(data_connection);
}

void handle_stor(Command *command, State *state)
{
    handle_stor_and_appe(command, state, "wb");
}

void handle_appe(Command *command, State *state)
{
    handle_stor_and_appe(command, state, "ab");
}

void handle_dele(Command *command, State *state)
{
    if(!check_logged_in(state)) return;
    
    char server_name[BUFFER_SIZE];
    memset(server_name, 0, BUFFER_SIZE);
    file_path_from_client_to_server(command->arg, server_name, state->root);

    if(remove(server_name) == 0){//文件删除成功
        write_message(state, "250 The file was successfully removed.\r\n");
    }else{
        write_message(state, "450 The removal failed.\r\n");
    }
}

void handle_quit(Command *command, State *state)
{
    write_message(state, "221 Goodbye\r\n");
    close(state->command_connection);
    close(state->passive_connection);
    exit(EXIT_SUCCESS);
}

void handle_type(Command *command, State *state)
{
    if(!check_logged_in(state)) return;

    if(strcmp(command->arg, "I") == 0){
        write_message(state, "200 Type set to I.\r\n");
    }else{
        write_message(state, "200 The server supports the verb but does not support the parameter.\r\n");//简化处理！
    }    
}

void handle_syst(Command *command, State *state)
{
    write_message(state, "215 UNIX Type: L8\r\n");
}

void handle_abor(Command *command, State *state)
{
    handle_quit(command, state);
}

void handle_cwd(Command *command, State *state)
{
    if(!check_logged_in(state)) return;

    if(change_current_path_of_client(state, command->arg)){
        write_message(state, "250 Okay.\r\n");
    }else{
        write_message(state,"550 %s: No such file or directory.\r\n", command->arg);
    }
}

void handle_pwd(Command *command, State* state)
{
    if(!check_logged_in(state)) return;

    char client_path[BUFFER_SIZE];
    memset(client_path, 0, BUFFER_SIZE);
    if(get_current_path_of_client(state, client_path)){
        write_message(state,"257 \"%s\"\r\n", client_path);
    }else{
        write_message(state, "550 Cannot get pwd.\r\n");
    }
}

void handle_mkd(Command *command, State *state)
{
    if(!check_logged_in(state)) return;

    if(strlen(command->arg) == 0){
        write_message(state, "550 MKD failed.\r\n");
    }else{
        char server_path[BUFFER_SIZE];
        memset(server_path, 0, BUFFER_SIZE);
        file_path_from_client_to_server(command->arg, server_path, state->root);

        if(mkdir(server_path, S_IRWXU | S_IRWXG | S_IROTH | S_IXOTH) == 0){//成功创建文件夹
            if(command->arg[0] == '/'){//客户端下的路径是绝对路径
                write_message(state, "257 \"%s\"\r\n", command->arg);
            }else{//客户端下的路径是相对路径
                char client_current_path[BUFFER_SIZE];
                memset(client_current_path, 0, BUFFER_SIZE);
                get_current_path_of_client(state, client_current_path);
                if(strcmp(client_current_path, "/")==0){
                    strcpy(client_current_path, "");
                }
                write_message(state, "257 \"%s/%s\"\r\n", client_current_path, command->arg);
            }
        }else{
            write_message(state, "550 MKD failed.\r\n");
        }
    }
}

void handle_list(Command *command, State *state)
{
    if(!check_logged_in(state)) return;

    write_message(state, "150 Opening BINARY mode data connection for listing %s.\r\n", command->arg);

    int data_connection = establish_data_connectioin(state);
    if(data_connection < 0) return;
    
    char server_path[BUFFER_SIZE];
    memset(server_path, 0, BUFFER_SIZE);
    if(strlen(command->arg) == 0){//默认列举当前文件夹
        strcpy(server_path, ".");
    }else{
        file_path_from_client_to_server(command->arg, server_path, state->root);
    } 

    DIR *dirptr = NULL;
    struct dirent *entry;
    struct stat statbuf;
    if((dirptr = opendir(server_path)) == NULL){
        write_message(state, "451 %s: No such file or directory.\r\n", server_path);
    }else{
        while((entry = readdir(dirptr))){
            char file_info[BUFFER_SIZE];
            memset(file_info, 0, BUFFER_SIZE);
            if(!get_file_info(entry->d_name, file_info)){
                fprintf(stderr, "Error reading %s\n", entry->d_name);
            }
            send(data_connection, file_info, strlen(file_info), 0);
        }
        // send(data_connection,EOF, strlen(EOF), 0);
        write_message(state, "226 The entire directory was successfully transmitted\r\n");
        closedir(dirptr);
    }
    close(data_connection);
}

void handle_rmd(Command *command, State *state)
{
    if(!check_logged_in(state)) return;

    char server_path[BUFFER_SIZE];
    memset(server_path, 0, BUFFER_SIZE);
    file_path_from_client_to_server(command->arg, server_path, state->root);

    char rm_command[BUFFER_SIZE];
    memset(rm_command, 0, BUFFER_SIZE);
    sprintf(rm_command, "sudo rm -r %s", server_path);
    
    if(system(rm_command) != -1){//成功删除文件夹
        write_message(state, "250 %s successfully removed.\r\n", server_path);
    }else{
        write_message(state, "550 The removal failed.\r\n");
    }
}

void handle_rnfr(Command *command, State *state)
{
    if(!check_logged_in(state)) return;

    memset(state->old_name, 0, BUFFER_SIZE);
    file_path_from_client_to_server(command->arg, state->old_name, state->root);

    if(access(state->old_name, F_OK) == 0){//文件存在
        write_message(state, "350 %s exists.\r\n", state->old_name);
        state->old_name_sent = 1;
    }else{
        write_message(state, "450 %s doesn't exist\r\n");
    }    
}

void handle_rnto(Command *command, State *state)
{
    if(!check_logged_in(state)) return;

    if(!state->old_name_sent){//如果旧的名字尚未发送
        write_message(state, "503 Please send RNFR first.\r\n");
    }else{
        char new_name[BUFFER_SIZE];
        memset(new_name, 0, BUFFER_SIZE);
        file_path_from_client_to_server(command->arg, new_name, state->root);
        if(rename(state->old_name, new_name) == 0){
            write_message(state, "250 %s was renamed successfully.\r\n", state->old_name);
        }else{
            write_message(state, "550 Fail to rename %s.\r\n", state->old_name);
        }
        state->old_name_sent = 0;
    }
}

void handle_rest(Command *command, State *state)
{
    if(!check_logged_in(state)) return;

    if(sscanf(command->arg, "%d", &state->rest_start) != -1){
        write_message(state, "350 Set the start position of file to %d\r\n", state->rest_start);
    }else{
        write_message(state, "500 The argument must be an integer.\r\n");
    }
}

//STAT命令支持对文件信息的查询
void handle_stat(Command *command, State *state)
{
    if(!check_logged_in(state)) return;

    char server_name[BUFFER_SIZE];
    memset(server_name, 0, BUFFER_SIZE);
    file_path_from_client_to_server(command->arg, server_name, state->root);

    char file_info[BUFFER_SIZE];
    memset(file_info, 0, BUFFER_SIZE);
    if(!get_file_info(server_name, file_info)){
        fprintf(stderr, "Error reading %s\n", command->arg);
        write_message(state, "500 The file %s doesn't exists.\r\n", command->arg);
    }else{
        write_message(state, "213-Status follows:\r\n%s213 End of status\r\n",file_info);
    }
}

//ZIP命令支持对文件夹的压缩
void handle_zip(Command *command, State *state)
{
    if(!check_logged_in(state)) return;

    char server_name[BUFFER_SIZE];
    memset(server_name, 0, BUFFER_SIZE);
    file_path_from_client_to_server(command->arg, server_name, state->root);

    if(access(server_name, F_OK) == 0){
        char zip_command[BUFFER_SIZE];
        sprintf(zip_command, "zip -r %s.zip %s", server_name, server_name);
        if(system(zip_command) != -1){
            write_message(state, "250 %s was zipped successfully.\r\n", command->arg);   
        }else{
            write_message(state, "451 Fail to zip %s.\r\n", command->arg);   
        }
    }else{
        write_message(state, "500 The file %s doesn't exists.\r\n", command->arg);
    }
}

//UNZIP命令支持对文件的解压
void handle_unzip(Command *command, State *state)
{
    if(!check_logged_in(state)) return;

    char server_name[BUFFER_SIZE];
    memset(server_name, 0, BUFFER_SIZE);
    file_path_from_client_to_server(command->arg, server_name, state->root);

    if(access(server_name, F_OK) == 0){
        char unzip_command[BUFFER_SIZE];
        sprintf(unzip_command, "unzip -o %s", server_name);
        if(system(unzip_command) != -1){
            write_message(state, "250 %s was unzipped successfully.\r\n", command->arg);   
        }else{
            write_message(state, "451 Fail to unzip %s.\r\n", command->arg);   
        }
    }else{
        write_message(state, "500 The file %s doesn't exists.\r\n", command->arg);
    }
}

//Generate response message to command
//current state is state
void response(Command *command, State *state)
{
    // printf("%s,%s\n",command->command, command->arg);
    int command_type = command_string_to_type(command->command);
    switch(command_type){
        case USER: handle_user(command, state); break;
        case PASS: handle_pass(command, state); break;
        case PASV: handle_pasv(command, state); break;
        case PORT: handle_port(command, state); break;
        case RETR: handle_retr(command, state); break;
        case STOR: handle_stor(command, state); break;
        case QUIT: handle_quit(command, state); break;
        case TYPE: handle_type(command, state); break;
        case PWD:  handle_pwd(command, state); break;
        case CWD: handle_cwd(command, state); break;
        case MKD: handle_mkd(command, state); break;
        case LIST: handle_list(command, state); break;
        case SYST: handle_syst(command, state); break;
        case ABOR: handle_abor(command, state); break;
        case RMD: handle_rmd(command, state); break;
        case RNFR: handle_rnfr(command, state); break;
        case RNTO: handle_rnto(command, state); break;
        case REST: handle_rest(command, state); break;
        case APPE: handle_appe(command, state); break;
        case STAT: handle_stat(command, state); break;
        case DELE: handle_dele(command, state); break;
        case ZIP: handle_zip(command, state); break;
        case UNZIP: handle_unzip(command, state); break;
        default: write_message(state, "500 Unknown command\r\n"); break;
    }
}
