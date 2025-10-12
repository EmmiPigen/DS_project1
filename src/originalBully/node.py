#!/usr/bin python3

# src/originalBully/node.py

# Node class for the bully algorithm.
from src.message import Message
import time
import json
import threading
import socket
from re import S
import os
import sys

sys.path.append(os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..')))


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

  def listen(self):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("localhost", PORT_BASE + self.id))
    server.listen()

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
      time.sleep(1)  # Small delay to avoid message clumping

    # Wait up to timeout seconds
    timeout = 10
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
        time.sleep(1)  # Small delay to avoid message clumping
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

    # Step 1: prepare for response tracking
    timeout = 3  # seconds to wait for a reply
    self.gotReply = False
    self.expectedReplyFrom = targetId

    # Check if we are sending a REQUEST to the current leader
    is_leader = (targetId == self.leaderId) and (msg.msgType == "REQUEST")

    #
    if is_leader:
      with self.stateLock:
        self.responseEvent.clear()
        self.requestSentTime = time.time()

      print(f"Node {self.id} sending REQUEST to leader Node {targetId} and awaiting REPLY...")

    # 2. Send the message to the target node
    self.sendMessage(targetId, msg)

    # 3. Wait for the response if it was a leader check
    if is_leader:
      event_set = self.responseEvent.wait(timeout=timeout)

      with self.stateLock:
        # 4. Check if we got the expected reply
        if not event_set or not self.gotReply:
          print(f"Node {self.id} failed to get REPLY from leader Node {targetId} within {timeout}s.")
          self.leaderId = None

          if self.status != "Election":
          # Leader failure detected!
            print(f"Node {self.id} starting election due to leader unresponsiveness.")
            threading.Thread(target=self.startElection, args=(self.knownNodes,), daemon=True).start()
          else:
            print(f"Node {self.id} is already in an election, not starting another.")
        else:
          print(f"Node {self.id} successfully received REPLY from leader Node {targetId}.")
      
      return self.gotReply  # Return success/failure
    
    return True  # For non-REQUEST messages or non-leader targets, we assume success after send

  def restart(self):
    """Function to restart a failed node. (For testing purposes)"""
    if self.alive:
      print(f"Node {self.id} is already running.")
      return

    self.alive = True
    self.status = "Normal"
    # Restart listening and processing threads
    threading.Thread(target=self.processMessages, daemon=True).start()

    print(f"Node {self.id} has restarted.")

    # Since node was restarted, an election should be started to find current leader
    self.startElection(self.knownNodes)

  def fail(self):
    """Function to simulate a node failure. (For testing purposes)"""
    self.alive = False
    self.leaderId = None
    self.status = "Down"
    print(f"Node {self.id} is shutting down.")
    # Shutdown listening and processing threads


if __name__ == "__main__":
  if len(sys.argv) < 3:
    print("Usage: python node.py <nodeId> <numberOfKnownNodes>")
    sys.exit(1)

  nodeId = int(sys.argv[1])
  knownNodes = list(range(1, int(sys.argv[2]) + 1))  # Nodes are numbered 1..N

  node = Node(nodeId, knownNodes)

  # Manual control loop
  try:
    while True:
      full_cmd = input(f"Node {nodeId} > ").strip().split()

      if not full_cmd:
        continue

      cmd = full_cmd[0].lower()

      # autopep8: off
      if cmd == "election":
        threading.Thread(target=node.startElection, args=(node.knownNodes,), daemon=True).start()
      # autopep8: on

      elif cmd == "status":
        print(f" \
              Node: {nodeId},\n \
              Known nodes: {node.knownNodes},\n \
              status: {node.status},\n \
              Alive: {node.alive},\n \
              Leader: {node.leaderId}")

      elif cmd == "die":
        node.fail()

      elif cmd == "revive":
        if not node.alive:
          node.restart()
        else:
          print(f"Node {nodeId} is already alive.")

      elif cmd == "contact":
        if len(full_cmd) < 2 or not full_cmd[1].isdigit():
          print("Usage: contact <targetNodeId>")
          continue

        try:
          targetId = int(full_cmd[1])
          node.sendAndWaitForReply(targetId, Message("REQUEST", nodeId, targetId))
        except ValueError:
          print("Invalid target node ID.")

      elif cmd == "exit":
        node.alive = False
        break

      else:
        print("Invalid command")

  except KeyboardInterrupt:
    node.alive = False
    print(f"\nNode {nodeId} is shutting down.")
