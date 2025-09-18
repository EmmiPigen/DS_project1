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
        server.bind(("localhost", PORT_BASE + self.id))
        server.listen()

        print(
            f"[{self.getTime()}] Node {self.id} is listening on Port {PORT_BASE + self.id}"
        )

        server.settimeout(1.0)  # Timeout to periodically check self.alive
        while self.alive:
            try:
                conn, _ = server.accept()
                msg = json.loads(conn.recv(1024).decode("utf-8"))
                receivedDict = Message(msg["type"], msg["senderId"], msg["targetId"])
                print(
                    f"[{self.getTime()}] Queued message: {receivedDict.msgType} from Node {receivedDict.senderId}"
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
        print(f"[{self.getTime()}] Node {self.id} is setting itself as leader.")
        if self.isLeader:
            return  # Already leader
        self.status = "Leader"
        self.isLeader = True
        self.leaderId = self.id

        print(f"[{self.getTime()}] Node {self.id} broadcasting COORDINATOR message.")
        self.broadcast(Message("COORDINATOR", self.id, None))

    def startElection(self, knownNodes):
      with self.stateLock:
        if self.status == "Election":
            print(f"[{self.getTime()}] Node {self.id} is already in an election.")
            return
        self.status = "Election"
        self.receivedOk = False
        self.leaderId = None

      higherNodes = [n for n in knownNodes if n > self.id]
      if not higherNodes:
        self.setCurrentLeader()
        return

      # Event to wait for OK or COORDINATOR
      self.electionEvent = threading.Event()

      # Send ELECTION messages
      for highnode in higherNodes:
        self.sendMessage(highnode, Message("ELECTION", self.id, highnode))

      # Wait up to timeout seconds
      timeout = 5
      event_set = self.electionEvent.wait(timeout=timeout)

      with self.stateLock:
        if self.leaderId is None and not self.receivedOk:
          # No higher node responded
          print(f"[{self.getTime()}] Node {self.id} did not receive any OK messages.")
          self.setCurrentLeader()
        self.status = "Normal"


    # def startElection(self, knownNodes):
    #     print(f"[{self.getTime()}] Node {self.id} is initializing an election")
    #     self.status = "Election"
    #     self.receivedOk = False
    #     self.leaderId = None

    #     # Getting all nodes with higher ID than self
    #     higherNodes = [n for n in knownNodes if n > self.id]
    #     if not higherNodes:
    #         self.setCurrentLeader()
    #         return

    #     for highnode in higherNodes:
    #         self.sendMessage(highnode, Message("ELECTION", self.id, highnode))

    #     timeout = 5  # seconds
    #     start_time = time.time()
    #     while time.time() - start_time < timeout:
    #       time.sleep(0.1)
    #       with self.stateLock:
    #         # If no OK received within timeout, declare self as leader
    #         if self.leaderId is not None:
    #             return  # Leader has been set by COORDINATOR message

    #     #Timeout reached
    #     with self.stateLock:
    #       if self.leaderId is None:
    #         print(f"[{self.getTime()}] Node {self.id} did not receive any OK messages.")
    #         self.setCurrentLeader()

    def acknowledgeElection(self, senderId):
        print(
            f"[{self.getTime()}] Node {self.id} acknowledges election from Node {senderId}."
        )
        self.sendMessage(senderId, Message("OK", self.id, senderId))
        time.sleep(1)  # Give time for OK to be sent before starting own election

    def receiveMessage(self, msg):
      if msg.msgType == "ELECTION":
        if self.id > msg.senderId:
            self.sendMessage(msg.senderId, Message("OK", self.id, msg.senderId))
            # Only start election if not already in one
            threading.Thread(target=self.startElection, args=(self.knownNodes,), daemon=True).start()
        else:
            print(f"[{self.getTime()}] Node {self.id} received ELECTION from Node {msg.senderId}, waiting for COORDINATOR.")


      elif msg.msgType == "OK":
            # Wait for COORDINATOR message as higher node is alive
            print(
                f"[{self.getTime()}] Node {self.id} received OK from Node {msg.senderId}."
            )
            self.receivedOk = True

      elif msg.msgType == "COORDINATOR":
            # Set the sender as leader as it has the highest ID
            self.leaderId = msg.senderId
            self.status = "Normal"
            self.isLeader = self.id == msg.senderId
            print(
                f"[{self.getTime()}] Node {self.id} acknowledges Node {msg.senderId} as leader."
            )

    def sendMessage(self, targetId, msg):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("localhost", PORT_BASE + targetId))
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
        print(f"[{self.getTime()}] Node {self.id} broadcasting message: {msg.msgType}")
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
