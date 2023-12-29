import json
class Request:
    def __init__(self, rtype,rtspseq, video, name, port,host,portstream,ipstream,cliente):
        self.rtype = rtype
        self.video = video
        self.name = name
        self.port = port
        self.rtspseq = rtspseq
        self.host = host
        self.portStream = portstream
        self.hostStream = ipstream
        self.clientName = cliente

    def toJson(self):
        return json.dumps({"Type":self.rtype,"Seq":self.rtspseq,"Video": self.video, "Name": self.name, "Port": self.port,"IP":self.host,
                        "Port_Stream":self.portStream,"IP_Stream":self.hostStream,"Cliente":self.clientName}) 