from collections import defaultdict
import socket
import threading
from Server import Server
from ClienteGUI import ClienteGUI
from RtpPacket import RtpPacket
from Intermediario import Intermediario
import json
import time

server_connections_lock = threading.Lock()
clients_lock = threading.Lock()
# armazenar as conexoes dos servidores e seus conteudos
# {"fonte":host,"port":port, "timestamp": timestamp,"duration": duration , "conteudos":[conteudo], "Estado": "Ativo" }
server_connections = {}
best_paths = {}
graph = defaultdict(list)
visited_nodes = set()
clients=[]
current_PACKET = None
STREAMING = False

class RP:
    # RP HANDLES CONNECTION WITH A SERVER FROM UNICAST REQUEST
    def handle_servers(conn):
        while True:
            data = conn.recv(1024)
            if not data:
                return
            contentdata = data.decode('utf-8')
            info = json.loads(contentdata)
            now = time.time_ns()
            duration = now - info["timestamp"]
            info["duration"] = duration
            # print(info)
            with server_connections_lock:
                server_connections[info["fonte"]] = info
                #print("storing server connection message from "+info["fonte"]+" : "+str(info))

    # RP LISTENS FOR SERVERS IN ORDER TO RECEIVE THEIR UNICAST
    def Serverlistening(ip, porta):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((ip, porta))
            s.listen()
            print("Listening on port " + str(porta))

            while True:
                conn, addr = s.accept()
                client_thread = threading.Thread(target=RP.handle_servers, args=(conn,))
                client_thread.start()

    # RP CHOOSES CLOSEST SERVER
    def getClosestServer(conteudo):
        closest = None
        with server_connections_lock:
            if not server_connections:
                return None

            # Initialize closest with the first server in the dictionary
            closest = list(server_connections.keys())[0]

            for server, info in server_connections.items():
                if info['duration'] < server_connections[closest]['duration'] and (conteudo in info['conteudos']) and (info['Estado'] == "Ativo"):
                    closest = server

            return closest

    # RP SHOULD CHOOSE THE BEST NODE TO SERVE CLIENT BASED ON HIS REQUEST
    def handle_client(conn):
        data = conn.recv(1024)
        if not data:
            return
        contentdata = data.decode('utf-8')
        info = json.loads(contentdata)
        video = info["Video"]
        with clients_lock:
            if info["Cliente"] not in clients:
                serverip = RP.getClosestServer(video)
                print("request from client:")
                print(info)
                print(info["Cliente"])
                print(STREAMING)
                if(info["Cliente"]=="c2" and STREAMING==True):
                    threading.Thread(target=RP.sendStreamC2, args=(info["IP_Stream"],info["Port_Stream"],)).start()    
                threading.Thread(target=RP.requestToServer, args=(serverip,video,7778,)).start()
                clients.append(info["Cliente"])
        conn.close()

    def requestToServer(serverip,video,porta):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                print(">>>>")
                print((serverip, porta))
                s.connect((serverip, porta))
                message = video
                msg = message.encode('utf-8')
                s.sendall(msg)
            except Exception as e:
                failed=1

    # RP LISTENS FOR CLIENTS REQUESTS
    def requestListening(ip, porta):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((ip, porta))
            s.listen()
            while True:
                conn, addr = s.accept()
                client_thread = threading.Thread(target=RP.handle_client, args=(conn,))
                client_thread.start()

    # as servers send messages at each 10secs we just need to compare if the entry's timestamp is bigger than 10secs
    def updateStatus():
        while True:
            with server_connections_lock:
                for server, info in server_connections.items():
                    if (time.time_ns() - server_connections[server]['timestamp']) > 10000000000:
                        server_connections[server]['Estado'] = "Desativado"
            time.sleep(10)

    # RP PRINTS EACH 10s THE CLOSEST SERVER WHICH HAS THE CONTENT PRETENDED
    def checkClosestServer(content):
        while True:
            closest_server = RP.getClosestServer(content)
            if closest_server:
                print("Closest server to get "+ content +":", closest_server)
            time.sleep(10)

    # SEND RTP PACKETS TO CLIENT (NEXT HOP)
    def forwardRtpPackets(ip,receivePort):
        global current_PACKET,STREAMING
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as receive_socket:
            print("escuta "+str(receivePort))
            receive_socket.bind((ip, receivePort))       
            receive_socket.listen()
            getbestpath=True
            conn, addr = receive_socket.accept()
            next_ip = None
            next_port = None
            with conn:
                while True:
                    data = conn.recv(20480)
                    if data:
                        rtpPacket = RtpPacket()
                        rtpPacket.decode(data)
                        current_PACKET=rtpPacket
                        if getbestpath:
                            # RP CHOOSES THE BEST PATH TO CLIENT
                            cliente = clients.pop(0)
                            best_path_thread = threading.Thread(target=RP.get_best_path,args=("r1",cliente,))
                            best_path_thread.start()
                            best_path_thread.join()
                            print("best path to:"+cliente)
                            print(best_paths[cliente])
                            STREAMING=True
                            getbestpath=False
                            RP.setup_path(best_paths[cliente])
                            name = socket.gethostname()
                            f = open("config/"+name+'.json')
                            config = json.load(f)
                            next_ip = config['next_hop_ip']
                            next_port = config['next_hop_port']
                            RP.requestToRead(best_paths[cliente])
                        # send each packet to next hopp
                        #print(str(rtpPacket.seqNum()))
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as forward_socket:
                            try:
                                forward_socket.connect((next_ip, next_port))
                                forward_socket.sendall(rtpPacket.getPacket())
                                time.sleep(0.1)
                            except Exception as e:
                                print(e)
                receive_socket.close()
            
    def setup_path(best_path):
        init = socket.gethostname()
        with open("config/" + init + '.json', 'r') as file:
            config = json.load(file)
            config['next_hop_ip'] = best_path[0][1][0]
            config['next_hop_port'] = best_path[0][1][1]
        with open("config/" + init + '.json', 'w') as file:
            json.dump(config, file, indent=2)

        for index in range(len(best_path) - 1):
            current_node_name = best_path[index][0]
            next_node_name = best_path[index + 1][0]

            with open("config/" + current_node_name + '.json', 'r') as file:
                config = json.load(file)
                config['next_hop_ip'] = best_path[index + 1][1][0]
                config['next_hop_port'] = best_path[index + 1][1][1]

            with open("config/" + current_node_name + '.json', 'w') as file:
                json.dump(config, file, indent=2)

    def sendStreamC2(ip,port):
        print("entrou")
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as forward_socket:
                try:
                    rtpPacket = current_PACKET
                    forward_socket.connect((ip,port))
                    forward_socket.sendall(rtpPacket.getPacket())
                    time.sleep(0.1)
                except Exception as e:
                    forward_error=1
                    print(e)

    def requestToRead(lista):
        for node in lista:
            threading.Thread(target=RP.sendRequest, args=(node[1][0],node[1][1]+20,)).start()
    
    def sendRequest(serverip, porta):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((serverip, porta))
                message = "READY"
                msg = message.encode('utf-8')
                s.sendall(msg)
            except Exception as e:
                failed=1

    def build_topology(node):
        with open('config/' + node + '.json', 'r') as json_file:
            entry_data = json.load(json_file)
            RP.add_neighbors(entry_data)

    def add_neighbors(node):
        node_name = node["name"]
        neighbors = node["neighbors"]
        aux = []
        for n in neighbors:
            f = open("config/"+n+'.json')
            config = json.load(f)
            aux.append((config["name"],(config["ip"],config["port"])))


        graph[node_name] = aux
        visited_nodes.add(node_name)


        for neighbor in neighbors:
            if neighbor not in visited_nodes:
                with open('config/' + neighbor + '.json', 'r') as json_file:
                    neighbor_data = json.load(json_file)
                    RP.build_topology(neighbor_data["name"])

    def all_get_path(name_from, name_to, paths, current_path=None):
        if current_path is None:
            current_path = []
        json_file =  open('config/' + name_from + '.json')
        config = json.load(json_file)
        ip = config["ip"]
        port = config["port"]
        current_path.append((name_from,(ip,port)))

        if name_from == name_to:
            paths.append(list(current_path))
        else:
            for neighbor in graph.get(name_from, []):
                if neighbor not in current_path:
                    RP.all_get_path(neighbor[0], name_to, paths, current_path)

        current_path.pop()

    def get_all_paths(name_from, name_to):
        paths = []
        RP.all_get_path(name_from, name_to, paths)
        return paths

    def test_paths(paths):
        scored_paths = []
        score = 0
        #print("all paths:")
        #print(paths)
        n = 0
        for path in paths:
            n+=1
            #print("testing new path "+str(n))
            #print(path)
            ini = time.time_ns()
            node_data = path[0]
            names, (start, start_port) = node_data

            node_data = path[1]
            names, (next, next_port) = node_data

            node_data = path[-1]
            names, (end, end_port) = node_data
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    #print("sending to:")
                    #print((next, next_port))
                    s.connect((next, int(next_port)))
                    path.pop(0)
                    allpath = ';'.join([f'{item[0]}>{item[1][0]},{item[1][1]}' for item in path])
                    s.sendall((start + ':' + str(start_port) + '-' + allpath).encode('utf-8'))
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s3:
                        #print("listening last one:")
                        #print((start, int(start_port)))
                        s3.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        s3.bind((start, int(start_port)))
                        s3.listen()
                        conn, addr = s3.accept()
                        receiving = True
                        with conn:
                            while receiving:
                                data = conn.recv(1024)
                                if(data):
                                    #print("data receiiived")
                                    received = data.decode('utf-8')
                                    #print(received)
                                    score = int(received) - ini
                                    #print("score: "+str(score))
                                    receiving=False
                            s3.close()
                except ConnectionRefusedError as e1:
                    score = -1
            scored_paths.append((path, score))

        return scored_paths

    def get_best_path(src,dest):
        paths = RP.get_all_paths(src,dest)
        scored_paths = RP.test_paths(paths)
        print("scored paths:")
        print(scored_paths)
        positive_scored_paths = [(n,v) for (n,v) in scored_paths if v>0]
        if not positive_scored_paths:
            return None
        best_path = min(positive_scored_paths, key=lambda x: x[1])
        index=0
        stream_path=[]
        for (name,(ip,port)) in best_path[0]:
            f = open("config/"+name+'.json')
            config = json.load(f)
            streamport = config["stream_port"]
            stream_path.append(((name,(ip,streamport))))
        best_paths[dest] = stream_path

    def runRP(ip,port1, port2):
        host = '0.0.0.0'  # Listen on all available network interfaces
        threading.Thread(target=RP.Serverlistening, args=(host, port1,)).start()
        threading.Thread(target=RP.requestListening, args=(host, port2,)).start()

        # thread in which RP updates the status of the servers connections stored
        closest_status_thread = threading.Thread(target=RP.updateStatus)
        closest_status_thread.start()

        # thread receives the server data and forwards to next hop in the best path
        receivedataserver_thread = threading.Thread(target=RP.forwardRtpPackets, args=(ip,7777,))
        receivedataserver_thread.start()

        testpath_thread = threading.Thread(target=RP.build_topology, args=("r1",))
        testpath_thread.start()
        time.sleep(3)
        print("arvore")
        print(json.dumps(dict(graph), indent=2))

"""
****** DEBUG *****
    def showAll():
        while True:
            print(server_connections)
            time.sleep(10)
            # print all connections
"""