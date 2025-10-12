import socket
import threading
import json
import time
import random
import sys

SIM_PORT = 6000
NODE_PORT_BASE = 5000
MIN_DELAY = 1.0
MAX_DELAY = 5.0


class NetworkSimulator:
  def __init__(self, knownNodes, minDelay=MIN_DELAY, maxDelay=MAX_DELAY):
    self.knownNodes = knownNodes
    self.messageQueue = []
    self.queueLock = threading.Lock()
    self.alive = True
    self.messageCount = 0
    self.countMessagesBool = False
    self.minDelay = minDelay
    self.maxDelay = maxDelay

    # Start listening and processing threads
    threading.Thread(target=self.listen, daemon=True).start()
    # Start thread that delivers messages
    threading.Thread(target=self.deliverMessages, daemon=True).start()

    print(
        f"Network Simulator is running on Port {SIM_PORT}, with nodes: {self.knownNodes}")

  def listen(self):
    """Receives all incoming messages from the connected nodes."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
      server.bind(("localhost", SIM_PORT))
      server.listen()
    except OSError as e:
      print(f"Error starting simulator: {e}")
      self.alive = False
      return

    server.settimeout(1.0)

    while self.alive:
      try:
        conn, _ = server.accept()
        raw_data = conn.recv(1024).decode("utf-8")
        conn.close()
        if self.countMessagesBool:
          self.messageCounter()
        self.scheduleDelivery(raw_data)
      except socket.timeout:
        continue
      except Exception as e:
        if self.alive:
          print(f"Simulator listener error: {e}")
        continue

  def scheduleDelivery(self, raw_msg):
    """Schedules a message for delivery with random delay and possible drop."""
    try:
      msg_data = json.loads(raw_msg)

      # Network conditions
      # if random.random() < DROP_RATE:
      # print(f"Simulator: Dropped message {msg_data}")
      # return

      delay = random.uniform(self.minDelay, self.maxDelay)
      deliveryTime = time.time() + delay

      with self.queueLock:
        # Store message, target ID and sending time
        self.messageQueue.append(
            {
                "data": raw_msg,
                "targetId": msg_data["targetId"],
                "deliveryTime": deliveryTime,
            }
        )

        self.messageQueue.sort(key=lambda x: x["deliveryTime"])

        # autopep8: off
        #print(f"[SCHEDULE] {msg_data['type']} from {msg_data['senderId']} to {msg_data['targetId']} scheduled for delivery in {delay:.2f}s.")
        # autopep8: on

    except json.JSONDecodeError:
      print(f"[SYSTEM] Received invalid JSON message: {raw_msg}")
    except Exception as e:
      print(f"[SYSTEM] Error scheduling message: {e}")

  def deliverMessages(self):
    """Sends messages once their scheduled time is reached."""
    while self.alive:
      now = time.time()
      delivered_indices = []

      with self.queueLock:
          # Check messages and mark for delivery
        for i, msg in enumerate(self.messageQueue):
          if msg["deliveryTime"] <= now:
            # Deliver the message using thread to allow concurrent deliveries
            threading.Thread(target=self._forwardMessage,
                             args=(msg,), daemon=True).start()
            delivered_indices.append(i)
          else:
            # Since the queue is sorted, we can stop checking
            break

          # Remove delivered messages (must be done in reverse for correct indexing)
          for index in sorted(delivered_indices, reverse=True):
            del self.messageQueue[index]

          time.sleep(0.01)  # Small sleep to prevent busy waiting

  def _forwardMessage(self, msg):
    """Internal helper to connect and send to the target node."""
    targetId = msg["targetId"]
    targetPort = NODE_PORT_BASE + targetId
    msg_data = json.loads(msg["data"])

    try:
      s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      s.connect(("localhost", targetPort))
      s.sendall(msg["data"].encode("utf-8"))
      s.close()
      print(f"[{self.getTime()}] [DELIVERED] {msg_data['type']} to Node {targetId}.")
    except (ConnectionRefusedError, OSError):
      print(
          f"[{self.getTime()}] [FAILURE] Node {targetId} is unreachable (Delivery failed).")
      # In a real system, the simulator might retry or report this

  def messageCounter(self):
    """Internal helper to count the incoming messages when enabled"""
    # If message counting is enabled, count each message as it arrives
    with self.queueLock:
      # check if any messages have been received
      self.messageCount += 1

  def getTime(self):
    return time.strftime("%H:%M:%S", time.localtime())

  def shutdown(self):
    self.alive = False


if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("Usage: python networkSimulator.py <Nodes> <minDelay> <maxDelay>")
    sys.exit(1)

  knownNodes = list(range(1, int(sys.argv[1]) + 1))  # Nodes are numbered 1..N
  minDelay = float(sys.argv[2]) if len(sys.argv) > 2 else MIN_DELAY
  maxDelay = float(sys.argv[3]) if len(sys.argv) > 3 else MAX_DELAY
  simulator = NetworkSimulator(knownNodes, minDelay, maxDelay)

  try:
    while True:
      cmd = input("").strip().lower()

      if cmd == "count":
        simulator.countMessagesBool = not simulator.countMessagesBool
        if simulator.countMessagesBool:
          simulator.messageCount = 0
          start_time = time.time()
          print("[COUNTER] Message counting enabled.")
        else:
          elapsed_time = time.time() - start_time
          print(f"[COUNTER] Total messages received: {simulator.messageCount}")
          print(f"[COUNTER] Elapsed time: {elapsed_time:.2f} seconds.")
          print("[COUNTER] Message counting disabled.")

      elif cmd == "exit":
        print("[SYSTEM] Shutting down simulator.")
        break

  except KeyboardInterrupt:
    print("[SYSTEM] Shutting down Network Simulator.")
    simulator.shutdown()
