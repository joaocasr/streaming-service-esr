import socket
import threading
import time
import json

hostname = socket.gethostname()
f = open("config/"+hostname+'.json')
dic = json.load(f)
ip_addresssrc = dic[hostname]["ip"]
ip_addressdst = dic["vizinho"]["ip"]
HOST = ip_addresssrc

PORT1 = dic[hostname]["port"]
PORT2 = dic["vizinho"]["port"]

def snd_message(porta):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        while True:
            try:
                s.connect((ip_addressdst, porta))
                while True:
                    print("sending...")
                    message = "Hello friend.I'm "+hostname
                    msg = message.encode('utf-8')
                    s.sendall(msg)
                    time.sleep(3)
            except Exception as e:
                print("Destination not reached.")

def rcv_message(porta):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, porta))
        s.listen()
        print("Listening on port "+str(porta))
        conn, addr = s.accept()
        with conn:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                print("Received: " + data.decode('utf-8'))

if __name__ =="__main__":
    t1 = threading.Thread(target=rcv_message,args=(int(PORT1),))
    t2 = threading.Thread(target=snd_message,args=(int(PORT2),))
    
    t1.start()
    t2.start()
