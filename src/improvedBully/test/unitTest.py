# tests/test_node.py
from encodings.punycode import T
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.message import Message

import unittest
from unittest.mock import patch, MagicMock, call
import threading
import time
from src.improvedBully.node import Node


class TestNode(unittest.TestCase):

  def setUp(self):
    """ Set up a Node instance for testing. """
    print(f"\n=== Starting {self._testMethodName} ===")

    # Patch time.sleep so we don't actually wait
    patcher = patch("time.sleep", return_value=None)
    self.addCleanup(patcher.stop)
    self.mock_sleep = patcher.start()
    
    timeout_patcher = patch("threading.Event.wait", return_value=True)
    self.addCleanup(timeout_patcher.stop)
    self.mock_timeout = timeout_patcher.start()

    # Patch socket to avoid binding to real ports
    socket_patcher = patch("socket.socket")
    self.addCleanup(socket_patcher.stop)
    self.mock_socket = socket_patcher.start()
    
    self.threading_patcher = patch("threading.Thread")
    mock_thread_class = self.threading_patcher.start()
    
    def instant_thread(target, args=(), kwargs=None, daemon=True):
      if kwargs is None:
        kwargs = {}
      target(*args, **kwargs)
      return MagicMock()

    mock_thread_class.side_effect = instant_thread
    self.addCleanup(self.threading_patcher.stop)

    # Prevent real threads from spinning forever
    patcher_alive = patch.object(Node, "listen", return_value=None)
    self.addCleanup(patcher_alive.stop)
    patcher_alive.start()
    # autopep8: off
    patcher_process = patch.object(Node, "processMessages", return_value=None)
    # autopep8: on
    self.addCleanup(patcher_process.stop)
    patcher_process.start()

    self.node = Node(1, [1, 2, 3])
    self.node.electionEvent = threading.Event()  # ensure always available

  def tearDown(self):
    """ Clean up after tests. """
    # Default tearDown just marks test end
    print(f"=== Finished {self._testMethodName} ===\n")

  def test_01_get_id(self):
    """ Test that getId returns the correct ID. """
    print(f"Expected ID: 1. Node ID: {self.node.getId()}.")
    self.assertEqual(self.node.getId(), 1)

  def test_02_initial_leader_assignment(self):
    """ Test that the node with the highest ID becomes leader initially. """
    # Node with max ID should become leader
    n = Node(3, [1, 2, 3])
    print(f"Expected Leader ID: 3. Actual Leader ID: {n.leaderId}")
    self.assertEqual(n.leaderId, 3)

  def test_03_set_current_leader(self):
    """ Test that setCurrentLeader correctly sets the node as leader. """
    self.node.setCurrentLeader()
    print(f"Expected isLeader: True. Actual isLeader: {self.node.isLeader}")
    self.assertTrue(self.node.isLeader)
    print(f"Expected Leader ID: 1. Actual Leader ID: {self.node.leaderId}")
    self.assertEqual(self.node.leaderId, 1)
    print(f"Expected Status: Leader. Actual Status: {self.node.status}")
    self.assertEqual(self.node.status, "Leader")

  def test_04_start_election_no_higher_nodes(self):
    """ Test that startElection sets the node as leader if no higher nodes exist. """
    node = Node(5, [1, 5])  # highest ID
    with patch.object(node, "setCurrentLeader") as mock_set_leader:
      node.startElection(node.knownNodes)
      mock_set_leader.assert_called_once()

  def test_05_start_election_with_higher_nodes(self):
    """ Test that startElection sends election messages to higher nodes. """
    with patch.object(self.node, "sendMessage") as mock_send:
      # Ensure electionEvent exists before we test waiting
      self.node.electionEvent = threading.Event()
      self.node.startElection([1, 2, 3])
      # After election, status should be reset to Normal
      self.assertEqual(self.node.status, "Normal")
      calls = [call(3, Message("ELECTION", 1, 3)),  
               call(2, Message("ELECTION", 1, 2))]
      mock_send.assert_has_calls(calls, any_order=True) # Should have sent 2 election messages to nodes 2 and 3

  def test_06_acknowledge_election(self):
    """ Test that acknowledgeElection sends an OK message back. """
    with patch.object(self.node, "sendMessage") as mock_send:
      self.node.acknowledgeElection(2)
      
      mock_send.assert_called_once()

  def test_07_handle_message_election_from_lower_node(self):
    """ Test that handleMessage responds to ELECTION from lower ID node. """
    msg = Message("ELECTION", senderId=0, targetId=1)
    with patch.object(self.node, "acknowledgeElection") as mock_ack:
      self.node.handleMessage(msg)
      mock_ack.assert_called_once_with(0)
      self.assertTrue(self.node.electionRunning) # Check that election flag was raised

  def test_08_handle_message_ok(self):
    """ Test that handleMessage processes OK messages correctly. """
    msg = Message("OK", senderId=3, targetId=1)
    self.node.status = "Election"
    self.node.electionEvent = threading.Event()
    self.node.handleMessage(msg)
    self.assertEqual(self.node.gotAcknowledgementFrom, 3)
    
    msg2 = Message("OK", senderId=2, targetId=1)
    self.node.handleMessage(msg2)
    self.assertEqual(self.node.gotAcknowledgementFrom, 3)  # still highest

  def test_09_handle_message_coordinator(self):
    """ Test that handleMessage processes COORDINATOR messages correctly. """
    msg = Message("COORDINATOR", senderId=2, targetId=1)
    self.node.handleMessage(msg)
    self.assertEqual(self.node.leaderId, 2)
    self.assertFalse(self.node.isLeader)

  def test_10_handle_message_request_and_reply(self):
    """ Test that handleMessage processes REQUEST messages and sends a reply. """
    with patch.object(self.node, "sendMessage") as mock_send:
      msg = Message("REQUEST", senderId=2, targetId=1)
      self.node.handleMessage(msg)
      mock_send.assert_called_once()

  def test_11_broadcast_sends_to_all(self):
    """ Test that broadcast sends messages to all known nodes except self. """
    with patch.object(self.node, "sendMessage") as mock_send:
      msg = Message("COORDINATOR", 1, None)
      self.node.broadcast(msg)
      self.assertGreaterEqual(mock_send.call_count, 2)

  def test_12_send_and_wait_for_reply_success(self):
    """ Test that sendAndWaitForReply successfully waits for a reply. """
    self.node.leaderId = 2
    msg = Message("REQUEST", 1, 2)

    # Pretend we got a reply
    def fake_wait(timeout):
      self.node.requestReceived = True
      return True

    with patch.object(self.node.responseEvent, "wait", side_effect=fake_wait):
      with patch.object(self.node, "sendMessage"):
        result = self.node.sendAndWaitForReply(2, msg)
        self.assertTrue(result)

  def test_13_send_and_wait_for_reply_timeout_triggers_election(self):
    """ Test that if no reply is received, an election is started."""
    self.node.leaderId = 2
    msg = Message("REQUEST", 1, 2)

    with patch.object(self.node, "sendMessage"):
      with patch.object(self.node, "startElection") as mock_start:
        result = self.node.sendAndWaitForReply(2, msg)
        self.assertFalse(result)
        
        time.sleep(1)  # allow thread to start  
        
        mock_start.assert_called_once()

  def test_14_handle_message_GRANT_from_lower_node(self):
    """ Test that handleMessage processes GRANT messages correctly. """
    msg = Message("GRANT", senderId=0, targetId=1)
    self.node.status = "Election"
    self.node.electionRunning = True
    self.node.handleMessage(msg)
    self.assertEqual(self.node.leaderId, 1)
    
    
if __name__ == "__main__":
    unittest.main(verbosity=2)