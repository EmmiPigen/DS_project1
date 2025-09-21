#!/usr/bin python3

# src/bully/node.py

# Node class for the bully algorithm.
import socket
import sys
import threading
import json
import time
from message import Message

PORT_BASE = 5000


class Node:
    def __init__(self, nodeId, knownNodes, hostMap):
        self.id = nodeId
        self.status = "Normal"
        self.isLeader = False
        self.knownNodes = knownNodes
        self.hostMap = hostMap
        self.messageQueue = []
        self.queueLock = threading.Lock()
        self.stateLock = threading.Lock()
        self.leaderId = None
        self.alive = True
        self.receivedOk = False

        self.port = PORT_BASE + nodeId
        threading.Thread(
            target=self.listen, daemon=True
        ).start()  # For testing purposes, daemon=True so it exits when main thread exits
        threading.Thread(target=self.processMessages, daemon=True).start()

    def listen(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("0.0.0.0", PORT_BASE + self.id))
        server.listen()

        print(
            f"Node {self.id} is listening on Port {PORT_BASE + self.id}"
        )

        server.settimeout(1.0)  # Timeout to periodically check self.alive
        while self.alive:
            try:
                conn, _ = server.accept()
                msg = json.loads(conn.recv(1024).decode("utf-8"))
                receivedDict = Message(msg["type"], msg["senderId"], msg["targetId"])
                print(
                    f"Queued message: {receivedDict.msgType} from Node {receivedDict.senderId}"
                )
                with self.queueLock:
                    self.messageQueue.append(receivedDict)
                conn.close()
            except socket.timeout:
                continue

    def getId(self):
        return self.id

    def isCurrentLeader(self):
        return self.isLeader

    def setCurrentLeader(self):
        # Set self as leader
      if not self.isLeader:
        self.status = "Leader"
        print(f"Node {self.id} is setting itself as leader.")
        self.isLeader = True
        self.leaderId = self.id

        print(f"Node {self.id} broadcasting COORDINATOR message.")
        self.broadcast(Message("COORDINATOR", self.id, None))

    def startElection(self, knownNodes):
      with self.stateLock:
        if self.status == "Election":
            print(f"Node {self.id} is already in an election.")
            return
        self.status = "Election"
        self.receivedOk = False
        self.leaderId = None
        self.electionEvent = threading.Event() # Event to signal election result

      higherNodes = [n for n in knownNodes if n > self.id]
      if not higherNodes:
        self.setCurrentLeader()
        return

      # Send ELECTION messages
      for highnode in higherNodes:
        self.sendMessage(highnode, Message("ELECTION", self.id, highnode))

      # Wait up to timeout seconds
      timeout = 10
      event_set = self.electionEvent.wait(timeout=timeout)

      with self.stateLock:
        #Check 1: Did we receive an COORDINATOR message?
        if self.leaderId is not None:
          print(f"Node {self.id} received COORDINATOR message from Node {self.leaderId}.")
          self.status = "Normal"
          return
        
        #Check 2: Did we receive any OK messages?
        if self.receivedOk:
          print(f"Node {self.id} received OK messages, waiting for COORDINATOR.")
          self.status = "Normal"
          return
        
        #Check 3: Timeout reached without any OK or COORDINATOR messages
        print(f"Node {self.id} did not receive any OK messages or COORDINATOR within timeout.")
        self.setCurrentLeader()
        self.status = "Normal"
                
    def acknowledgeElection(self, senderId):
        print(
            f"Node {self.id} acknowledges election from Node {senderId}."
        )
        self.sendMessage(senderId, Message("OK", self.id, senderId))
        time.sleep(1)  # Give time for OK to be sent before starting own election

    def handleMessage(self, msg):
      match msg.msgType:
        
        case "ELECTION":
          if self.id > msg.senderId:
            self.acknowledgeElection(msg.senderId)
            
            if self.isLeader:
              #If already leader, no need to start another election
              self.sendMessage(msg.senderId, Message("COORDINATOR", self.id, msg.senderId))
              return
              
            threading.Thread(target=self.startElection, args=(self.knownNodes,), daemon=True).start()
        
        case "OK":
          print(f"Node {self.id} received OK from Node {msg.senderId}.")
          with self.stateLock:
            self.receivedOk = True
            if self.status == "Election":
              self.electionEvent.set()  # Stop waiting for election
        
        case "COORDINATOR":
          self.leaderId = msg.senderId
          self.status = "Normal"
          self.isLeader = False
          print(f"Node {self.id} acknowledges Node {msg.senderId} as leader.")
          with self.stateLock:
            if self.status == "Election":
              self.electionEvent.set()  # Stop waiting for election
        
        case "REQUEST":
          #Recieved a request from another node, reply back to message
          print(f"Node {self.id} received REQUEST from Node {msg.senderId}.")
          self.sendMessage(msg.senderId, Message("REPLY", self.id, msg.senderId))
        
        case "REPLY":
          print(f"Node {self.id} received REPLY from Node {msg.senderId}.")
          
    def sendMessage(self, targetId, msg):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.hostMap[targetId], PORT_BASE + targetId))
            s.sendall(json.dumps(msg.to_dict()).encode("utf-8"))
            s.close()
            print(
                f"[{self.getTime()}] Node {self.id} sent {msg.msgType} to Node {targetId}."
            )

        except ConnectionRefusedError:
            print(f"[{self.getTime()}] Node {self.id}: Node {targetId} is unreachable.")

            # If target is leader and unreachable, start election
            if self.leaderId == targetId:
                print(
                    f"[{self.getTime()}] Node {self.id} detected leader failure. Starting election."
                )
                self.leaderId = None

                threading.Thread(
                    target=self.startElection, args=(self.knownNodes,), daemon=True
                ).start()

    def broadcast(self, msg):
        print(f"Node {self.id} broadcasting message: {msg.msgType}")
        for n in self.knownNodes:
            if n != self.id:
                try:
                    self.sendMessage(n, msg)
                except ConnectionRefusedError:
                    print(f"Node {self.id}: Node {n} is unreachable.")

    def processMessages(self):
        while self.alive:
            msg = None
            with self.queueLock:
                if self.messageQueue:
                    msg = self.messageQueue.pop(0)
            if msg:
                self.handleMessage(msg)

    def getTime(self):
        return time.strftime("%H:%M:%S", time.localtime())


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python node.py <nodeId> <knownNode1> <knownNode2> ...")
        sys.exit(1)

    nodeId = int(sys.argv[1])
    knownNodes = list(map(int, sys.argv[2:]))

    node = Node(nodeId, knownNodes, None)

    # Manual control loop
    while True:
        cmd = input(f"Node {nodeId} > ").strip()
        if cmd == "election":
            threading.Thread(
                target=node.startElection, args=(node.knownNodes,), daemon=True
            ).start()
        elif cmd == "status":
            print(f"Node {nodeId} status: {node.status}, Leader: {node.leaderId}")
        elif cmd == "die":
            node.alive = False
            print(f"Node {nodeId} is shutting down.")
            node.status = "Down"
        elif cmd == "revive":
            if not node.alive:
                node.alive = True
                node.status = "Normal"
                threading.Thread(target=node.listen, daemon=True).start()
                threading.Thread(target=node.processMessages, daemon=True).start()
                print(f"Node {nodeId} has revived.")
                # On revival, if node was leader before, it should send COORDINATOR message as well
                if node.id == max(node.knownNodes):
                    node.broadcast(Message("COORDINATOR", node.id, None))
                    node.leaderId = node.id
                    node.status = "Leader"
                else: #Node was not highest, start election to find current leader
                    node.startElection(node.knownNodes)

            else:
                print(f"Node {nodeId} is already alive.")
        elif cmd == "contact":
            targetId = int(input("Enter target node ID: "))
            node.sendMessage(targetId, Message("REQUEST", nodeId, targetId))

        elif cmd == "exit":
            node.alive = False
            break
        else:
            print("Invalid command")
