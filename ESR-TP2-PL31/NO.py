import socket
import json
import time 
from Server import Server
from Cliente import Cliente
from Intermediario import Intermediario
from RP import RP
import threading
import ast

name = socket.gethostname()
f = open("config/"+name+'.json')
config = json.load(f)
role = config['role']

"""
implementar a arvore 
"""
def test_score():
    if(role=="intermediario"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            #print("bind1...",end=" ")
            #print((config['ip'], config['port']))
            s.bind((config['ip'], config['port']))
            s.listen()
            while True:
                conn, addr = s.accept()
                with conn: 
                    data = conn.recv(1024)
                    if(data):
                        content = data.decode('utf-8')
                        #print("conteudo:")
                        #print(content)
                            
                        datacontent = content.split("-")
                        begin = content.split("-")[0]
                        path = datacontent[1].split(";")
                        #print("path received")
                        #print(path)

                        if len(path) > 0:
                            path.pop(0)
                            if len(path) > 0:
                                node_data = path[0]
                                iport = node_data.split(">")[1]
                                ip = iport.split(",")[0]
                                port = iport.split(",")[1]
                                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                                    #print("bind2...",end=" ")
                                    #print((ip,int(port)))
                                    s2.connect((ip,int(port)))
                                    allpath = '; '.join([f'{item.split(">")[0]}>{item.split(">")[1].split(",")[0]},{item.split(">")[1].split(",")[1]}' for item in path])
                                    s2.sendall((begin+'-'+allpath).encode('utf-8'))
                                    s2.close()
    
    if(role=="client"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            #print("bind ...")
            #print((config['ip'], config['port']))
            s.bind((config['ip'], config['port']))
            s.listen()
            while True:
                conn, addr = s.accept()
                with conn:        
                    data = conn.recv(1024)
                    if(data):
                        content = data.decode('utf-8')
                        #print("conteudo:")
                        #print(content)
                        contentdata = content.split("-")[0]
                        iport = contentdata.split(":")
                        ip = iport[0]
                        port = int(iport[1])
                        send = True
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                            while send==True:
                                try:
                                    s2.connect((ip, port))
                                    finish = time.time_ns()
                                    #print("time "+str(finish))
                                    s2.sendall(str(finish).encode('utf-8'))
                                    send=False
                                    s2.close()
                                except Exception as e:
                                    send=True

if(role=="client"):
    closest = config['closest_neighbour']
    clientip= config['ip']
    clientport= config['port']
    streamport= config['stream_port']

    t1 = threading.Thread(target=Cliente.runClient,args=(clientip,clientport,closest['ip'],closest['port'],streamport,name,))#substituir pelo nó mais próximo que está a transmitir  
    t1.start()
    t2 = threading.Thread(target=test_score,args=())
    t2.start()
    #t3 = threading.Thread(target=Cliente.receiveRTP,args=(clientip,config['stream_port'],))
    #t3.start()

if(role=="rp"):
    rpip = config['ip']
    portClients = config['portClients']
    portServers = config['portServers']
    RP.runRP(rpip,portServers,portClients)

if(role=="server"):
    hostip = config['ip']
    hostport = config['port']
    conteudos = config['conteudos']
    t3 = threading.Thread(target=Server.unicastRP,args=(hostip,hostport,conteudos,config['rp']['ip'], config['rp']['port'],))
    t4 = threading.Thread(target=Server.waitforsend,args=(hostip,))
    t3.start()
    t4.start()

if(role=="intermediario"):
    ip = config['ip']
    port1 = config['portClients']
    port2 = config['stream_port']
    t4 = threading.Thread(target=Intermediario.listening,args=(ip,port1,))
    t5 = threading.Thread(target=test_score,args=())
    t6 = threading.Thread(target=Intermediario.receive_extract_forward,args=(ip,port2,))
    port3= port2+20
    t7 = threading.Thread(target=Intermediario.waiToRead,args=(ip,port3,))

    t4.start()
    t5.start()
    t6.start()
    t7.start()