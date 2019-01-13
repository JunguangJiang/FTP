#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <errno.h>
#include <ctype.h>
#include <string.h>
#include <memory.h>
#include <stdio.h>
#include <stdlib.h>

#include "util.h"
#include "handle.h"

//Set up a server with port
void server(int port, char *root)
{
    int listenfd = create_listen_socket(port);
    struct sockaddr_in client_address;
    socklen_t len = sizeof(client_address);
    int connectionfd, pid, bytes_read;

    while(1){
        if((connectionfd = accept(listenfd, (struct sockaddr*)&client_address, &len)) == -1){
            fprintf(stderr, "Error accept(): %s(%d)\n", strerror(errno), errno);
            continue;
        }
        char buffer[BUFFER_SIZE];
        memset(buffer, 0, BUFFER_SIZE);

        pid = fork();
        if(pid < 0){
            close(listenfd);
            close(connectionfd);
            fprintf(stderr, "Cannot create child process");
            exit(EXIT_FAILURE);
        }else if(pid == 0){//the child process
            close(listenfd);

            //客户端状态的初始化
            Command *command = malloc(sizeof(Command));
            State *state = malloc(sizeof(State));
            if(chdir(root) != 0){
                fprintf(stderr, "Error enter %s\n", root);
                exit(EXIT_FAILURE);
            }
            char pwd[BUFFER_SIZE];//根目录的绝对路径
            memset(pwd, 0, BUFFER_SIZE);
            getcwd(pwd, BUFFER_SIZE);
            memcpy(state->root, pwd, BUFFER_SIZE);
            
            //Write welcome message
            char welcome[BUFFER_SIZE] = "220 Anonymous FTP server ready.\r\n";
            write(connectionfd, welcome, strlen(welcome));
            state->command_connection = connectionfd;//is this code here right?

            //Read commands from client
            while((bytes_read = read(connectionfd, buffer, BUFFER_SIZE)) > 0){

                if(bytes_read < BUFFER_SIZE){
                    buffer[BUFFER_SIZE-1] = '\0';
                    printf("User %s sends command: %s\n", (state->username == 0)?"unknown":state->username, buffer);
                    
                    //process the command
                    convert_string_to_command(buffer, command);

                    //respond to the client
                    response(command, state);

                    memset(buffer, 0, BUFFER_SIZE);
                    memset(command, 0, sizeof(Command));
                }else{
                    perror("server:read");
                }
            }
            close(connectionfd);
            close(state->passive_connection);
            
            printf("Client command connection disconnected.\n");

            free(command);
            free(state);
            exit(0);
        }else{// the father process
            close(connectionfd);
        }
    }
    close(listenfd);
}

int main(int argc, char *argv[])
{
    int port = 21;
    char root[BUFFER_SIZE] = "/tmp";
    if(argc >= 3){
        if(strcmp(argv[1],"-port") == 0){
            sscanf(argv[2], "%d", &port);
        }else if(strcmp(argv[1], "-root") == 0){
            sscanf(argv[2], "%s", root);
        }
    }
    if(argc == 5){
        if(strcmp(argv[3],"-port") == 0){
            sscanf(argv[4], "%d", &port);
        }else if(strcmp(argv[3], "-root") == 0){
            sscanf(argv[4], "%s", root);
        }
    }
    server(port, root);
    return 0;
}
