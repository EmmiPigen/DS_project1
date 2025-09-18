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
    def __init__(self, nodeId, knownNodes, network):
        self.id = nodeId
        self.status = "Normal"
        self.isLeader = False
        self.knownNodes = knownNodes
        self.messageQueue = []
        self.leaderId = None
        self.network = network
        self.alive = True
        self.receivedOk = False

        self.port = PORT_BASE + nodeId
        threading.Thread(
            target=self.listen, daemon=True
        ).start()  # For testing purposes, daemon=True so it exits when main thread exits

    def listen(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("localhost", PORT_BASE + self.id))
        server.listen()

        print(f"[{self.getTime()}] Node {self.id} is listening on Port {PORT_BASE + self.id}")

        server.settimeout(1.0)  # Timeout to periodically check self.alive
        while self.alive:
          try:
            conn, _ = server.accept()
            msg = json.loads(conn.recv(1024).decode("utf-8"))
            receivedDict = Message(msg["type"], msg["senderId"], msg["targetId"])
            print(f"[{self.getTime()}] Queued message: {receivedDict.msgType} from Node {receivedDict.senderId}")
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
        self.status = "Leader"
        self.isLeader = True
        self.leaderId = self.id

        print(f"[{self.getTime()}] Node {self.id} broadcasting COORDINATOR message.")
        self.broadcast(Message("COORDINATOR", self.id, None))

    def startElection(self, knownNodes):
        print(f"[{self.getTime()}] Node {self.id} is initializing an election")
        self.status = "Election"
        self.receivedOk = False
        self.leaderId = None

        # Getting all nodes with higher ID than self
        higherNodes = [n for n in knownNodes if n > self.id]
        if not higherNodes:
            self.setCurrentLeader()
            return

        for highnode in higherNodes:
            self.sendMessage(highnode, Message("ELECTION", self.id, highnode))
        
        time.sleep(5)  # Wait for OK messages
        if not self.receivedOk:
          print(f"[{self.getTime()}] Node {self.id} did not receive any OK messages.")
          self.setCurrentLeader()
        else:
          # Wait for COORDINATOR message
          print(f"[{self.getTime()}] Node {self.id} received OK, waiting for COORDINATOR message.")
          coord_timeout = 5
          coord_startTime = time.time()
          while (time.time() - coord_startTime) < coord_timeout:
              time.sleep(0.1)
              # The leaderId is set by receiveMessage when COORDINATOR arrives
              if self.leaderId is not None:
                  return # Election successfully deferred to higher node
        
        
        #timeout = 5  # seconds
        #startTime = time.time()
        # while (time.time() - startTime) < timeout:
        #   # ADD: Allow background message processing to run
        #   time.sleep(0.1) 
          
        #   if self.receivedOk:
        #     break
        
        # if self.receivedOk:
        #   print(f"[{self.getTime()}] Node {self.id} received OK, waiting for COORDINATOR message.")
          
        #   # ADD: Wait for the COORDINATOR message
        #   coord_timeout = 5
        #   coord_startTime = time.time()
          
        #   while (time.time() - coord_startTime) < coord_timeout:
        #       time.sleep(0.1)
        #       # The leaderId is set by receiveMessage when COORDINATOR arrives
        #       if self.leaderId is not None:
        #           return # Election successfully deferred to higher node
          
        #   # If the timeout is reached, the higher node failed after sending OK.
        #   print(f"[{self.getTime()}] Node {self.id} timed out waiting for COORDINATOR. Re-starting election.")
        #   self.startElection(self.knownNodes) # Re-initiate election
          
        # else:
        #   self.setCurrentLeader()
            
    def acknowledgeElection(self, senderId):
        print(f"[{self.getTime()}] Node {self.id} acknowledges election from Node {senderId}.")
        self.sendMessage(senderId, Message("OK", self.id, senderId))
        time.sleep(1)  # Give time for OK to be sent before starting own election

    def receiveMessage(self, msg):
        if msg.msgType == "ELECTION":
            if self.id > msg.senderId:
              # Respond with OK and start own election as node is higher than sender
                self.acknowledgeElection(msg.senderId)
                self.startElection(self.knownNodes)
            else:
              # Node is higher than sender, wait for COORDINATOR message
              print(f"[{self.getTime()}] Node {self.id} received ELECTION from Node {msg.senderId}, but is higher. Waiting for COORDINATOR message.")

        elif msg.msgType == "OK":
            # Wait for COORDINATOR message as higher node is alive
            print(f"[{self.getTime()}] Node {self.id} received OK from Node {msg.senderId}.")
            self.receivedOk = True

        elif msg.msgType == "COORDINATOR":
            if self.leaderId is not None and self.leaderId > msg.senderId:
               print(f"[{self.getTime()}] Node {self.id} ignored lower-ID COORDINATOR from Node {msg.senderId}.")
               return
             
            #Set the sender as leader as it has the highest ID
            self.leaderId = msg.senderId
            self.status = "Normal"
            self.isLeader = self.id == msg.senderId
            print(f"[{self.getTime()}] Node {self.id} acknowledges Node {msg.senderId} as leader.")

    def sendMessage(self, targetId, msg):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("localhost", PORT_BASE + targetId))
            s.sendall(json.dumps(msg.to_dict()).encode("utf-8"))              
            s.close()
            print(f"[{self.getTime()}] Node {self.id} sent {msg.msgType} to Node {targetId}.")
        
        except ConnectionRefusedError:
            print(f"[{self.getTime()}] Node {self.id}: Node {targetId} is unreachable.")
            
            #If target is leader and unreachable, start election
            if self.leaderId == targetId:
              print(f"[{self.getTime()}] Node {self.id} detected leader failure. Starting election.")
              self.leaderId = None
              
              threading.Thread(target=self.startElection, args=(self.knownNodes,), daemon=True).start()
    
    def broadcast(self, msg):
        print(f"[{self.getTime()}] Node {self.id} broadcasting message: {msg.msgType}")
        for n in self.knownNodes:
          if n != self.id:
            try:      
              self.sendMessage(n, msg)
            except ConnectionRefusedError:
              print(f"Node {self.id}: Node {n} is unreachable.")
    
    def processMessages(self):
      while self.alive:
        if self.messageQueue:
          msg = self.messageQueue.pop(0)
          self.receiveMessage(msg)
        time.sleep(0.1)  # Avoid busy waiting
        
    def getTime(self):
        return time.strftime("%H:%M:%S", time.localtime())
      
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python node.py <nodeId> <knownNode1> <knownNode2> ...")
        sys.exit(1)

    nodeId = int(sys.argv[1])
    knownNodes = list(map(int, sys.argv[2:]))

    node = Node(nodeId, knownNodes, None)
    threading.Thread(target=node.processMessages, daemon=True).start()
    
    # Manual control loop
    while True:
        cmd = input(f"Node {nodeId} > ").strip()
        if cmd == "election":
          threading.Thread(target=node.startElection, args=(node.knownNodes,), daemon=True).start()
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
                if node.isLeader:
                    node.broadcast(Message("COORDINATOR", node.id, None))
                    node.leaderId = node.id
                    node.status = "Leader"
                    
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
