import hashlib, getpass, json
from shiboken6 import isValid
from PySide6.QtCore import QObject, Signal, QTimer, QLockFile
from PySide6.QtNetwork import QLocalServer, QLocalSocket

class SingleInstance(QObject):
    request=Signal(dict)
    def __init__(self,root,parent=None):
        super().__init__(parent)
        self.name="LaunchFlow-"+hashlib.sha256((getpass.getuser()+str(root)).encode()).hexdigest()[:24]
        self.lock=QLockFile(str(root/"instance.lock")); self.lock.setStaleLockTime(30000)
        self.server=QLocalServer(self);self.sockets={}
        self.server.newConnection.connect(self.accept)
    def acquire(self,args):
        if not self.lock.tryLock(0):
            socket=QLocalSocket();socket.connectToServer(self.name)
            if not socket.waitForConnected(3000):raise RuntimeError("已有实例正在启动或无法连接，请稍后重试")
            socket.write((json.dumps(args)+"\n").encode());socket.waitForBytesWritten(3000)
            if not socket.waitForReadyRead(3000):raise RuntimeError("已有实例未确认请求，请稍后重试")
            socket.disconnectFromServer();return False
        QLocalServer.removeServer(self.name)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        if not self.server.listen(self.name):raise RuntimeError("无法建立本地实例通信")
        return True
    def accept(self):
        while self.server.hasPendingConnections():
            socket=self.server.nextPendingConnection();self.sockets[socket]=bytearray()
            socket.readyRead.connect(lambda s=socket:self.read(s))
            socket.disconnected.connect(lambda s=socket:self.cleanup(s))
            QTimer.singleShot(5000,lambda s=socket:s.disconnectFromServer() if s in self.sockets and isValid(s) else None)
            self.read(socket)
    def cleanup(self,socket):
        self.sockets.pop(socket,None)
        if isValid(socket): socket.deleteLater()
    def read(self,socket):
        buffer=self.sockets.get(socket)
        if buffer is None:return
        buffer.extend(bytes(socket.readAll()))
        if len(buffer)>8192:socket.abort();return
        if b"\n" in buffer:
            try:
                data=json.loads(bytes(buffer).split(b"\n",1)[0])
                if not isinstance(data,dict):raise ValueError()
                self.request.emit(data);socket.write(b"ok");socket.flush()
            except (ValueError,TypeError):socket.abort()
            buffer.clear()
