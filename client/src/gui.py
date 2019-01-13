import sys,mainwindow
from PyQt5.QtWidgets import *
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from util import human_readable_size,get_file_type
from client import Client
from task_manager import TaskManager

class ClientWindow(mainwindow.Ui_MainWindow):
    '''客户端窗口类'''
    def __init__(self):
        MainWindow = QMainWindow()
        self.setupUi(MainWindow)

        self.client = Client()
        self.task_manager = None  #传输任务工厂
        self.timer = QtCore.QTimer()  #计时器，用于不断刷新数据传输进度
        self.interval = 100  #刷新间隔，以ms为单位
        self.timer.timeout.connect(self.update_tasks_progress)

        self.status_label = QLabel(self.statusbar) #由于显示数据传输信息

        self.has_connected = False  #是否已经建立连接
        self.establish_signals_ans_slots()

        self.menubar.setEnabled(False)
        self.statusbar.setEnabled(False)

        MainWindow.closeEvent = self.closeEvent
        MainWindow.show()
        sys.exit(app.exec_())

    def establish_signals_ans_slots(self):
        '''建立窗体中的信号与槽'''
        # 文件浏览窗体
        self.folderWidget.customContextMenuRequested[QtCore.QPoint].connect(self.folder_right_menu_show)  #鼠标右键单击
        self.folderWidget.itemDoubleClicked.connect(self.on_go_action)  #鼠标左键双击
        self.folderWidget.setMouseTracking(True)
        self.folderWidget.itemEntered.connect(lambda item: self.on_look_action(item, self.folderWidget))  #鼠标悬浮

        # 任务浏览窗体
        self.tasksWidget.setMouseTracking(True)
        self.tasksWidget.itemEntered.connect(lambda item: self.on_look_action(item, self.tasksWidget))  #鼠标悬浮

        self.connectButton.clicked.connect(self.on_connect_button_clicked)  # 点击"连接"按钮
        self.goButton.clicked.connect(self.on_go_button)  # 点击"跳转"按钮

        self.menuSetting.setToolTipsVisible(True)

        self.actionNew_folder.triggered.connect(self.on_mkdir_action)
        self.actionNew_folder.setText("创建文件夹")
        self.actionPut_file.triggered.connect(lambda: self.on_put_action(is_folder=False))
        self.actionPut_file.setText("上传文件")
        self.actionPut_folder.triggered.connect(lambda: self.on_put_action(is_folder=True))
        self.actionPut_folder.setText("上传文件夹")

        self.actionMax_Occurs.triggered.connect(self.on_action_max_occurs_triggered)
        self.actionMax_Occurs.setText("设置同时传输最大任务数")
        self.actionPort.triggered.connect(self.on_action_port_triggered)
        self.actionPassive.triggered.connect(self.on_action_passive_triggered)

        self.actionSystem.triggered.connect(self.on_action_system_triggered)
        self.actionType.triggered.connect(self.on_action_type_triggered)


    def on_connect_button_clicked(self):
        '''当连接按钮按下时'''
        if self.has_connected == False:  #尚未建立连接
            # 则根据输入的ip、port、user、password连接到服务器
            ip = self.ipInput.text()
            port = self.portInput.text()
            user = self.userInput.text()
            password = self.passwordInput.text()
            if not self.client.open(ip, port):  #连接失败
                QMessageBox.information(self.centralwidget, "连接错误","ip或者port错误",QMessageBox.Yes)
                return
            self.client.user(user)
            reply = self.client.password(password)
            if reply.startswith("5"):  #若登录失败
                QMessageBox.information(self.centralwidget, "连接错误", "user或者password错误", QMessageBox.Yes)
            else:  #登录成功
                self.update_folder()  #更新文件浏览窗体
                self.connectButton.setText("disconnect")
                self.has_connected = True

                self.task_manager = TaskManager(ip, port, user, password)  #创建任务工厂
                self.timer.start(self.interval)  #开始刷新数据传输进度

                self.menubar.setEnabled(True)
                self.statusbar.setEnabled(True)
        else:  #如果已经建立连接
            self.timer.stop() #停止数据传输进度的刷新
            # 则客户端断开连接
            self.client.bye()
            self.client.close()
            self.connectButton.setText("connect")
            self.has_connected = False
            del self.task_manager
            self.task_manager = None

            self.menubar.setEnabled(False)
            self.statusbar.setEnabled(False)

    def closeEvent(self, event):
        '''单击退出时响应'''
        self.timer.stop()
        if self.has_connected:
            self.client.bye()
            self.client.close()
        del self.task_manager

    def update_navigation_bar(self):
        '''更新导航栏'''
        reply = self.client.pwd()  # 获取当前路径
        if reply.startswith("257"):
            self.navigationBar.setText(reply[5:-2])

    def update_folder(self):
        '''更新文件浏览窗口'''
        ls_file = "ls.txt"
        reply = self.client.ls(local_file=ls_file) #获取当前文件夹下的所有文件信息
        if reply == True:
            self.folderWidget.clearContents()
            self.folderWidget.setRowCount(len(open(ls_file,'r').readlines()))
            i = 0
            with open(ls_file, "r") as f:
                for line in f:
                    list = line.split()
                    #文件名
                    name_item = QTableWidgetItem(list[8])
                    name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    self.folderWidget.setItem(i, 0, name_item)
                    #文件类型
                    type = get_file_type(file_name=list[8], access_string=list[0])
                    type_item = QTableWidgetItem(type)
                    type_item.setFlags(Qt.NoItemFlags)
                    self.folderWidget.setItem(i, 1, type_item)
                    #文件大小
                    if type == "folder":
                        size = "--"
                    else:
                        size = human_readable_size(list[4])
                    size_item = QTableWidgetItem(size)
                    size_item.setFlags(Qt.NoItemFlags)
                    self.folderWidget.setItem(i, 2, size_item)
                    #文件的最近修改时间
                    time_item = QTableWidgetItem(" ".join(list[5:8]))
                    time_item.setFlags(Qt.NoItemFlags)
                    self.folderWidget.setItem(i, 3, time_item)
                    i += 1

    def folder_right_menu_show(self, point):
        '''当右键点击文件浏览窗口时，根据选中项弹出相关操作'''
        if not self.has_connected:
            return
        popMenu = QMenu()
        index = self.folderWidget.indexAt(point)
        row = index.row()
        column = index.column()
        if row >= 0 and column == 0: #如果右键文件名一列
            file_name = self.folderWidget.item(row, 0).text()
            file_type = self.folderWidget.item(row, 1).text()
            # 无论是否为文件夹
            popMenu.addAction(QAction(text="rename 重命名", parent=popMenu, triggered=lambda: self.on_rename_action(old_name=file_name)))
            popMenu.addAction(QAction(text="get 下载", parent=popMenu, triggered=lambda: self.on_get_action(file_name)))
            if file_type == "folder": #如果该文件是文件夹
                popMenu.addAction(QAction(text="rmdir 删除文件夹", parent=popMenu, triggered=lambda: self.on_rmdir_action(file_name)))
                popMenu.addAction(QAction(text='zip 压缩', parent=popMenu, triggered=lambda :self.on_zip_action(file_name)))
            else: #如果该文件不是文件夹
                popMenu.addAction(QAction(text="reget 断点下载", parent=popMenu, triggered=lambda: self.on_reget_action(file_name)))
                popMenu.addAction(QAction(text="reput 断点上传", parent=popMenu, triggered=lambda: self.on_reput_action(file_name)))
                popMenu.addAction(QAction(text="append 追加内容", parent=popMenu, triggered=lambda: self.on_append_action(file_name)))
                popMenu.addAction(QAction(text="delete 删除文件", parent=popMenu, triggered=lambda: self.on_delete_action(file_name)))
                if file_type == 'zip': #如果是压缩文件
                    popMenu.addAction(QAction(text='unzip 解压', parent=popMenu, triggered=lambda :self.on_unzip_action(file_name)))
        else: #其余情况
            popMenu.addAction(QAction(text="mkdir 创建文件夹", parent=popMenu, triggered=lambda: self.on_mkdir_action()))
            popMenu.addAction(QAction(text="put 上传文件", parent=popMenu, triggered=lambda: self.on_put_action(is_folder=False)))
            popMenu.addAction(QAction(text="put(folder) 上传文件夹", parent=popMenu, triggered=lambda: self.on_put_action(is_folder=True)))
        popMenu.exec_(QtGui.QCursor.pos())

    def on_get_action(self, file_name):
        '''使用get下载文件file_name'''
        path = QFileDialog.getExistingDirectory(self.centralwidget, '下载文件', './')
        if path:
            indexes = self.folderWidget.selectedIndexes()
            for r in indexes:
                file_name = self.folderWidget.item(r.row(), 0).text()
                file_type = self.folderWidget.item(r.row(), 1).text()
                if file_type != "folder":
                    self.create_transfer_tasks(type="GET", local_file=path+"/"+file_name, remote_file=file_name)
                else:
                    self.create_transfer_tasks(type="GET_FOLDER", local_file=path, remote_file=file_name)

    def on_reget_action(self, file_name):
        '''使用reget重新下载文件'''
        local_file, ftype = QFileDialog.getOpenFileName(self.centralwidget, "下载文件 断点续传", './')
        if local_file:
            self.create_transfer_tasks(type="REGET", local_file=local_file, remote_file=file_name)

    def on_append_action(self, file_name):
        '''使用append上传文件（追加模式）'''
        local_file, ftype = QFileDialog.getOpenFileName(self.centralwidget, "上传文件 追加内容", './')
        if local_file:
            self.create_transfer_tasks(type="APPEND", local_file=local_file, remote_file=file_name)

    def on_reput_action(self, file_name):
        local_file, ftype = QFileDialog.getOpenFileName(self.centralwidget, "上传文件 断点续传", './')
        if local_file:
            self.create_transfer_tasks(type="REPUT", local_file=local_file, remote_file=file_name)

    def on_put_action(self, is_folder=False):
        '''使用put下载文件'''
        if is_folder:
            local_folder = QFileDialog.getExistingDirectory(self.centralwidget, "上传文件夹","./")
            self.create_transfer_tasks(type="PUT_FOLDER", local_file=local_folder, remote_file='.')
        else:
            local_files, ftype = QFileDialog.getOpenFileNames(self.centralwidget, "上传文件", './')
            for f in local_files:
                if not f:
                    continue
                self.create_transfer_tasks(type="PUT", local_file=f, remote_file=f.split('/')[-1])
        self.update_folder()


    def on_mkdir_action(self):
        '''使用mkdir创建文件夹'''
        dir, ok = QInputDialog.getText(self.centralwidget, "新建文件夹","新文件夹名")
        if ok:
            reply = self.client.mkdir(dir)
            if reply.startswith("550"):
                QMessageBox.information(self.centralwidget, "错误", "创建文件夹{}失败".format(dir), QMessageBox.Yes)
            else:
                self.update_folder()

    def on_rmdir_action(self, file_name):
        '''使用rmdir删除文件夹file_name，目前只支持删除里面没有内容的文件夹'''
        reply = self.client.rmdir(file_name)
        if reply.startswith("550"):
            QMessageBox.information(self.centralwidget, "错误", "删除文件夹{}失败".format(file_name), QMessageBox.Yes)
        else:
            self.update_folder()

    def on_delete_action(self,file_name):
        '''使用delete删除文件file_name'''
        reply = self.client.delete(file_name)
        if not reply.startswith("250"):
            QMessageBox.information(self.centralwidget, "错误", "删除文件{}失败".format(file_name), QMessageBox.Yes)
        else:
            self.update_folder()

    def on_rename_action(self,old_name):
        '''使用rename修改文件名'''
        new_name, ok = QInputDialog.getText(self.centralwidget, "修改文件名", "新文件名")
        if ok:
            reply = self.client.rename(from_name=old_name, to_name=new_name)
            if not reply.startswith("250"):
                QMessageBox.information(self.centralwidget, "错误", "修改文件{}的名字失败".format(old_name), QMessageBox.Yes)
            else:
                self.update_folder()

    def on_zip_action(self, folder_name):
        '''使用zip压缩文件'''
        self.client.zip(folder_name)
        self.update_folder()

    def on_unzip_action(self, zip_file_name):
        '''使用unzip解压文件'''
        self.client.unzip(zip_file_name)
        self.update_folder()

    def on_look_action(self, item, widget):
        '''当鼠标经过时响应'''
        widget.setToolTip(item.text())

    def on_go_action(self, item):
        '''当双击文件夹时响应'''
        if not self.has_connected:
            return
        dir = item.text()
        type = self.folderWidget.item(item.row(), 1).text()
        if type == "folder":
            reply = self.client.cd(dir)
            if not reply.startswith("550"): #改变路径成功
                self.update_navigation_bar()
                self.update_folder()

    def on_go_button(self):
        '''当点击go button时响应'''
        if not self.has_connected:
            return
        dir = self.navigationBar.text()
        reply = self.client.cd(dir)
        if reply.startswith("550"): #改变路径失败
            QMessageBox.information(self.centralwidget, "错误", "不存在该路径{}".format(dir), QMessageBox.Yes)
        else:  #改变路径成功
            self.update_navigation_bar()
            self.update_folder()

    def create_transfer_tasks(self,type, local_file, remote_file):
        '''创建数据传输任务'''
        self.timer.stop()  #在创建数据传输的过程中，不进行任务进度的刷新
        remote_path = self.client.pwd()[5:-2]  #获取当前路径
        taskInfo = self.task_manager.create_task(type, local_file, remote_file, remote_path)  #创建一个新的任务

        # 将新的任务显示在GUI界面上
        self.tasksWidget.setRowCount(self.tasksWidget.rowCount()+1)
        contents = [str(taskInfo.id), local_file, remote_file, type]
        for j in range(len(contents)):
            item = QTableWidgetItem(contents[j])
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.tasksWidget.setItem(self.tasksWidget.rowCount()-1,j,item)

        if taskInfo.status == "Failed":
            item = QTableWidgetItem("任务失败")
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.tasksWidget.setItem(self.tasksWidget.rowCount() - 1, 4, item)
        elif taskInfo.status == "Invalid":
            QMessageBox.information(self.centralwidget, "错误", "与正在运行或者等待的任务冲突", QMessageBox.Yes)
            item = QTableWidgetItem("任务冲突")
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.tasksWidget.setItem(self.tasksWidget.rowCount() - 1, 4, item)
        else:
            progressBar = QProgressBar(self.tasksWidget)
            progressBar.setRange(0, 100)
            progressBar.setValue(0)
            progressBar.setToolTip("任务进度")
            progressBar.setStyleSheet(
                                    "QProgressBar {\
                                        border: 2px solid grey;\
                                        border-radius: 5px; \
                                        text-align:center; \
                                    }\
                                    QProgressBar::chunk {\
                                        background-color: #05B8CC;\
                                        width: 2px; \
                                    }")
            self.tasksWidget.setCellWidget(self.tasksWidget.rowCount() - 1, 4, progressBar)

        self.timer.start()

    def update_tasks_progress(self):
        '''刷新任务的进度'''
        if not self.has_connected:
            return

        #  在状态栏展示下载速度、上传速度、正在进行的任务数和等待任务数
        download_speed, upload_speed = self.task_manager.calculate_data_tranfer_rate(self.interval)
        going_on_tasks_size = len(self.task_manager.going_on_tasks)
        waiting_tasks_size = len(self.task_manager.waiting_tasks)

        status_inforation = "正在进行的任务数:{:2d}   等待任务数: {:2d}          下载速率:{:9.1f}Mb/s      上传速率:{:9.1f}Mb/s".format(
            going_on_tasks_size, waiting_tasks_size, download_speed, upload_speed)
        self.status_label.setText(status_inforation)
        self.status_label.adjustSize()

        for i in range(self.tasksWidget.rowCount()):
            id = self.tasksWidget.item(i,0).text()
            taskInfo = self.task_manager.get_task_by_id(id)
            if taskInfo.status == "Going on":  #如果该任务正在进行中
                task = taskInfo.task
                status, msg = task.query_status(self.client)
                if status == "Not started":
                    print("此处有bug！！！")
                elif status == "Fail": # 任务失败
                    item = QTableWidgetItem("任务失败")
                    item.setToolTip(msg)
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    self.tasksWidget.removeCellWidget(i, 4)
                    self.tasksWidget.setItem(i, 4, item)
                    self.task_manager.recycle_task(taskInfo)  #回收该任务
                    continue
                elif status == "Success":  #完成传输
                    self.task_manager.recycle_task(taskInfo)  #则回收该任务
                    self.update_folder()
                    progress = 1.0
                else: #正在进行传输
                    try:
                        progress = float(msg)
                    except:
                        progress = 0.0
                # 刷新进度条的显示
                progressBar = self.tasksWidget.cellWidget(i, 4)
                progressBar.setValue(100.0 * progress)
                progressBar.setToolTip(str(msg))
                progressBar.update()
        self.tasksWidget.scrollToBottom()


    def on_action_max_occurs_triggered(self):
        '''设置同时数据传输的最大并发个数'''
        if not self.has_connected:
            return
        number, ok = QInputDialog.getInt(self.centralwidget, "输入","请输入同时进行的数据传输的最大个数",
                                         self.task_manager.max_occurs, 1, 10)
        if ok:
            self.task_manager.max_occurs = number

    def on_action_port_triggered(self):
        '''设置port模式'''
        if not self.has_connected:
            return
        self.client.sendport()

    def on_action_passive_triggered(self):
        '''设置Passive模式'''
        if not self.has_connected:
            return
        self.client.passive()

    def on_action_system_triggered(self):
        '''查询system'''
        if not self.has_connected:
            return
        info = self.client.system()
        QMessageBox.information(self.centralwidget, "查询system信息", info, QMessageBox.Yes)

    def on_action_type_triggered(self):
        '''查询type信息'''
        if not self.has_connected:
            return
        info = self.client.type()
        QMessageBox.information(self.centralwidget, "查询type信息", info, QMessageBox.Yes)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    clientWindow = ClientWindow()