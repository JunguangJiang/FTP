CC=gcc
CFLAGS=-c -Wall
LDFLAGS=-lm
SOURCES=util.c handle.c server.c 
OBJECTS=$(SOURCES:.cpp=.o)
EXECUTABLE=./server

$(EXECUTABLE): $(OBJECTS) 
	$(CC) $(LDFLAGS) $(OBJECTS) -o $@

.cpp.o:
	$(CC) $(CFLAGS) $< -o $@

clean: 
	rm -rf *.o ./server