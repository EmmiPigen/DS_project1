# tests/test_system_bully.py
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.message import Message

import unittest
from unittest.mock import patch
import threading
import time
from node import Node


class TestSystemBully(unittest.TestCase):
  def run_cluster(self, NodeClass, num_nodes=3):
    nodes = []
    known_nodes = list(range(1, num_nodes + 1))

    with patch("time.sleep", return_value=None):
      for i in known_nodes:
        n = NodeClass(i, known_nodes)
        nodes.append(n)

    time.sleep(0.1) # allow threads to start

    leader_ids = [n.leaderId for n in nodes if n.leaderId is not None]
    return nodes, leader_ids

  def test_original_cluster_election(self):
    nodes, leaders = self.run_cluster(Node, num_nodes=3)
    # In Bully algorithm, highest ID becomes leader
    expected = 3
    self.assertTrue(all(l == 3 for l in leaders),
                    f"Leaders elected: {leaders}, expected: {expected}")

    time.sleep(5) # allow some time for the message exchanges
    
    
    #Test failure of leader and re-election
    leader = max(nodes, key=lambda n: n.id)
    leader.alive = False
    leader.status = "Down"
    print(f"\nNode {leader.id} (Leader) is down.")

    #Node 1 sends request to node 3 and discover it's down
    nodes[0].sendAndWaitForReply(3, Message("REQUEST", nodes[0].id, 3))
    
    time.sleep(20)  # give time for election
    
    
    # New leader should be the next-highest
    expected = 2
    leaders = [n.leaderId for n in nodes if n.alive and n.leaderId is not None]
    self.assertTrue(all(l == expected for l in leaders))
