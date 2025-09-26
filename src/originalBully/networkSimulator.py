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
DROP_RATE = 0.1


class NetworkSimulator:
  def __init__(self, knownNodes):
    self.knownNodes = knownNodes
    self.messageQueue = []
    self.queueLock = threading.Lock()
    self.alive = True

    # Start listening and processing threads
    threading.Thread(target=self.listen, daemon=True).start()
    # Start thread that delivers messages
    threading.Thread(target=self.deliverMessages, daemon=True).start()

    print(f"Network Simulator is running on Port {SIM_PORT}")
    print(
        f"Latency: {MIN_DELAY}-{MAX_DELAY}s, Loss rate: {DROP_RATE*100}%")

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

      delay = random.uniform(MIN_DELAY, MAX_DELAY)
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

        print(
            f"[SCHEDULE] {msg_data['type']} from {msg_data['senderId']} to {msg_data['targetId']} scheduled for delivery in {delay:.2f}s."
        )

    except json.JSONDecodeError:
      print(f"Simulator: Received invalid JSON message: {raw_msg}")
    except Exception as e:
      print(f"Simulator: Error scheduling message: {e}")

  def deliverMessages(self):
    """Sends messages once their scheduled time is reached."""
    while self.alive:
      now = time.time()
      delivered_indices = []

      with self.queueLock:
          # Check messages and mark for delivery
        for i, msg in enumerate(self.messageQueue):
          if msg["deliveryTime"] <= now:
            self._forwardMessage(msg)
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
      print(f"[DELIVERED] {msg_data['type']} to Node {targetId}.")
    except (ConnectionRefusedError, OSError):
      print(
          f"[FAILURE] Node {targetId} is unreachable (Delivery failed).")
      # In a real system, the simulator might retry or report this

  def shutdown(self):
    self.alive = False


if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("Usage: python networkSimulator.py <knownNode1> <knownNode2> ...")
    sys.exit(1)

  knownNodes = list(map(int, sys.argv[1:]))
  simulator = NetworkSimulator(knownNodes)

  try:
    while True:
      time.sleep(1)
  except KeyboardInterrupt:
    print("Shutting down Network Simulator.")
    simulator.shutdown()
