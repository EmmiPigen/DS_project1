#!/usr/bin python3

# src/originalBully/node.py

# Node class for the bully algorithm.
import time
import json
import threading
import socket
from re import S
import os
import sys

sys.path.append(os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..')))
from src.message import Message


PORT_BASE = 5000
SIM_PORT = 6000


class Node:
  def __init__(self, nodeId, knownNodes):
    self.id = nodeId
    self.knownNodes = knownNodes

    self.status = "Normal"
    self.isLeader = False
    self.leaderId = None
    self.receivedOk = False
    self.alive = True

    self.requestSentTime = 0.0
    self.responseEvent = threading.Event()  # Event to signal response received
    self.expectedReplyFrom = None  # ID of node we expect a reply from
    self.gotReply = False  # Flag to indicate if we got the expected reply

    self.messageQueue = []
    self.queueLock = threading.Lock()
    self.stateLock = threading.Lock()

    # Start listening and processing threads
    threading.Thread(target=self.listen, daemon=True).start()
    threading.Thread(target=self.processMessages, daemon=True).start()

    # Startup logic
    time.sleep(5)  # Wait for other nodes to start
    if self.id == max(self.knownNodes):
      self.setCurrentLeader()

  def listen(self):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("localhost", PORT_BASE + self.id))
    server.listen()
    server.settimeout(1.0)

    print(f"Node {self.id} is listening on Port {PORT_BASE + self.id}")

    while self.alive:
      try:
        conn, _ = server.accept()
        msg = json.loads(conn.recv(1024).decode("utf-8"))
        msgObj = Message(msg["type"], msg["senderId"], msg["targetId"])
        with self.queueLock:
          self.messageQueue.append(msgObj)
        conn.close()
      except socket.timeout:
        continue

  def getId(self):
    return self.id

  def isCurrentLeader(self):
    return self.isLeader

  def setCurrentLeader(self):
    if self.isLeader:
      return
    self.status = "Leader"
    self.isLeader = True
    self.leaderId = self.id
    print(f"Node {self.id} is now the leader.")
    self.broadcast(Message("COORDINATOR", self.id, None))

  def startElection(self, knownNodes):
    with self.stateLock:
      if self.status == "Election":
        print(f"Node {self.id} is already in an election.")
        return
      self.status = "Election"
      self.receivedOk = False
      self.leaderId = None
      self.electionEvent = threading.Event()  # Event to signal election result

    higherNodes = [n for n in knownNodes if n > self.id]
    if not higherNodes:
      self.setCurrentLeader()
      return

    # Send ELECTION messages
    for highnode in higherNodes:
      self.sendMessage(highnode, Message("ELECTION", self.id, highnode))

    # Wait up to timeout seconds
    timeout = 15
    event_set = self.electionEvent.wait(timeout=timeout)

    with self.stateLock:
      # Check 1: Did we receive an COORDINATOR message?
      if self.leaderId is not None:
        print(
            f"Node {self.id} received COORDINATOR message from Node {self.leaderId}."
        )
        self.status = "Normal"
        return

      # Check 2: Did we receive any OK messages?
      if self.receivedOk:
        print(
            f"Node {self.id} received OK message, waiting for COORDINATOR.")
        self.status = "Normal"
        return

      # Check 3: Timeout reached without any OK or COORDINATOR messages
      print(
          f"Node {self.id} did not receive any OK messages or COORDINATOR within timeout.")
      self.setCurrentLeader()
      self.status = "Normal"

  def acknowledgeElection(self, senderId):
    self.sendMessage(senderId, Message("OK", self.id, senderId))
    # Give time for OK to be sent before starting own election
    time.sleep(2)

  def handleMessage(self, msg):
    match msg.msgType:

      case "ELECTION":
        if self.id > msg.senderId:
          self.acknowledgeElection(msg.senderId)

          if self.isLeader and self.id == max(self.knownNodes):
            # If already leader and highest node, respond with COORDINATOR

            # autopep8: off
            self.sendMessage(msg.senderId, Message("COORDINATOR", self.id, msg.senderId))
            return

          threading.Thread(target=self.startElection, args=(self.knownNodes,), daemon=True).start()

          # autopep8: on

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
        print(
            f"Node {self.id} acknowledges Node {msg.senderId} as leader.")
        with self.stateLock:
          if self.status == "Election":
            self.electionEvent.set()  # Stop waiting for election

      case "REQUEST":
        # Recieved a request from another node, reply back to message
        print(
            f"Node {self.id} received REQUEST from Node {msg.senderId}.")
        self.sendMessage(msg.senderId, Message(
            "REPLY", self.id, msg.senderId))

      case "REPLY":
        print(
            f"Node {self.id} received REPLY from Node {msg.senderId}.")
        with self.stateLock:
          if msg.senderId == self.expectedReplyFrom:
            self.gotReply = True
            self.responseEvent.set()  # Signal that we got the expected reply

  def sendMessage(self, targetId, msg):
    try:
      s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      s.connect(("localhost", SIM_PORT))

      s.sendall(json.dumps(msg.to_dict()).encode("utf-8"))
      s.close()

      print(
          f"[{self.getTime()}] Node {self.id} sent {msg.msgType} to Node {targetId}."
      )

    except (ConnectionRefusedError, OSError):
      print(f"Node {self.id}: Network Simulator is unreachable.")

  def broadcast(self, msg):
    print(f"Node {self.id} broadcasting message: {msg.msgType}")
    for n in self.knownNodes:
      if n != self.id:
        targetMessage = Message(msg.msgType, msg.senderId, n)
        self.sendMessage(n, targetMessage)

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

  def sendAndWaitForReply(self, targetId, msg):
    """
    Sends a message and waits for a REPLY. If target is the leader and
    no reply is received, it triggers an election.
    """

    # 1. Prepare for response tracking
    is_leader_check = (targetId == self.leaderId) and (
        msg.msgType == "REQUEST")
    timeout = 7  # seconds to wait

    if is_leader_check:
      with self.stateLock:
        self.awaitingReplyFrom = targetId
        self.requestReceived = False
        self.responseEvent.clear()
        self.requestSentTime = time.time()
      print(
          f"Node {self.id} sending REQUEST to leader Node {targetId} and awaiting REPLY...")

    # 2. Send the message (using the existing, now    modified, sendMessage)
    self.sendMessage(targetId, msg)

    # 3. Wait for the response if it was a leader check
    if is_leader_check:
      event_set = self.responseEvent.wait(timeout=timeout)

      with self.stateLock:
        self.awaitingReplyFrom = None  # Clear expectation

        if not event_set or not self.requestReceived:
          # Leader failure detected!
          print(
              f"Node {self.id} failed to get REPLY from leader Node {targetId} within {timeout}s.")
          self.leaderId = None

          if self.status != "Election":
            print(
                f"Node {self.id} starting election due to leader unresponsiveness.")
            threading.Thread(
                target=self.startElection, args=(self.knownNodes,), daemon=True
            ).start()
        else:
          print(
              f"Node {self.id} successfully received REPLY from leader Node {targetId}.")

      return self.requestReceived  # Return success/failure

    return True  # For non-REQUEST messages or non-leader targets, we assume success after send


if __name__ == "__main__":
  if len(sys.argv) < 3:
    print("Usage: python node.py <nodeId> <knownNode1> <knownNode2> ...")
    sys.exit(1)

  nodeId = int(sys.argv[1])
  knownNodes = list(map(int, sys.argv[2:]))

  node = Node(nodeId, knownNodes)

  # Manual control loop
  while True:
    cmd = input(f"Node {nodeId} > ").strip()

    if cmd == "election":
      threading.Thread(
          target=node.startElection, args=(node.knownNodes,), daemon=True
      ).start()

    elif cmd == "status":
      print(f"Node {nodeId} status: {node.status}, Leader: {node.leaderId}")
      print(f"Known nodes: {node.knownNodes}")

    elif cmd == "die":
      node.alive = False
      node.leaderId = None
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
        else:  # Node was not highest, start election to find current leader
          node.startElection(node.knownNodes)

      else:
        print(f"Node {nodeId} is already alive.")

    elif cmd == "contact":
      targetId = int(input("Enter target node ID: "))
      node.sendAndWaitForReply(targetId, Message("REQUEST", nodeId, targetId))

    elif cmd == "exit":
      node.alive = False
      break

    else:
      print("Invalid command")
