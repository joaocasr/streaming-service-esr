import socket
import json
from RtpPacket import RtpPacket
from ServerWorker import ServerWorker
import threading
import time

ip_next = None
port_next = None
stream_lock = threading.Lock()
STREAMING = False
current_PACKET = None

class Intermediario:

    neighbors = []

    def handle_neighbor(neighbor_socket, neighbor_name):
        while True:
            data = neighbor_socket.recv(1024).decode()
            if not data:
                break
            print(f"Received data from {neighbor_name}: {data}")

    def configureNeighborSockets(sender):
        name = socket.gethostname()
        #print("RECEIVER NAME "+sender)
        f = open("config/"+name+'.json')
        config = json.load(f)
        f.close()
        for n in config["neighbors"]:
            if n!=sender:
                print("flood to "+n)
                fv = open("config/"+n+'.json')
                configv = json.load(fv)
                fv.close()
                neighbor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    neighbor_socket.connect((configv["ip"], configv["portClients"]))
                    Intermediario.neighbors.append((name, neighbor_socket))
                except Exception as e2:
                    print(e2)

    def propagateMsg(message):
        neighbors = Intermediario.neighbors
        #for name, neighbor_socket in neighbors:
        #    neighbor_handler = threading.Thread(target=Intermediario.handle_neighbor, args=(neighbor_socket, name))
        #    neighbor_handler.start()
        for name, neighbor_socket in neighbors:
            msgjson = json.loads(message)
            msgjson["Name"] = socket.gethostname()
            json_data = json.dumps(msgjson)
            print("(REQUEST CLIENT FLOOD):"+json_data)
            neighbor_socket.send(json_data.encode())

    def handle_msg(conn):
        #print("is node streaming? "+str(STREAMING))
        data = conn.recv(1024)
        if not data:
            return
        contentdata = data.decode('utf-8')
        info = json.loads(contentdata)
        name = info["Name"]
        print("> received from "+name)
        if(STREAMING==False):
            Intermediario.configureNeighborSockets(name)
            Intermediario.propagateMsg(contentdata)
        else:
            print("redirecting")
            if data:
                while True:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as send_socket:
                        try:
                            send_socket.connect((info["IP_Stream"], info["Port_Stream"]))
                            #with stream_lock:
                            send_socket.sendall(current_PACKET)
                            send_socket.close()
                            time.sleep(0.1)
                        except Exception as e:
                            forward_error=1
                            print(e)
        conn.close()

    def listening(myaddr,myport):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((myaddr,myport))
            s.listen()
            while True:
                conn, addr = s.accept()
                rcvthread = threading.Thread(target=Intermediario.handle_msg, args=(conn,))
                rcvthread.start()

    def waiToRead(ip,porta):
        global ip_next, port_next
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((ip,porta))
            s.listen()
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024)
                if(data):
                    if data.decode('utf-8')=="READY":
                        print("received ready")
                        name = socket.gethostname()
                        try:
                            f=open("config/" + name + '.json')
                            config = json.load(f)
                            ip_next = config['next_hop_ip']
                            port_next = config['next_hop_port']
                            f.close()
                        except Exception as e:
                            print(f"Error loading configuration: {e}")                        

    def handle_packet(conn,ip,port):
        global current_PACKET,STREAMING
        try:
            data = conn.recv(20480)
            if(data):
                rtpPacket = RtpPacket()
                rtpPacket.decode(data)
                seq = rtpPacket.seqNum()
                #print("seq num:"+str(seq))
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as forward_socket:
                    try:
                        #print("next:")
                        #print((ip,port))
                        forward_socket.connect((ip,port))
                        forward_socket.sendall(rtpPacket.getPacket())
                        #with stream_lock:
                        current_PACKET=rtpPacket.getPacket()
                        STREAMING=True
                        time.sleep(0.1)
                    except Exception as e:
                        forward_error=1
        except Exception as e:
                print(f"Error handling packet: {e}")
        finally:
            conn.close()

    def receive_extract_forward(ip,myport):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as receive_socket:
            receive_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            receive_socket.bind((ip, myport))
            print("à escuta de rtp packets")
            receive_socket.listen()

            while True:
                conn, addr = receive_socket.accept()
                #client_thread = threading.Thread(target=Intermediario.handle_packet, args=(conn,ip_next,port_next,))
                Intermediario.handle_packet(conn,ip_next,port_next)
                #client_thread.start()