# tests/test_system_bully.py


#!/usr/bin/env python3
"""
System Test for Improved Bully Algorithm
----------------------------------------
Tests leader election, leader failover, and restart behavior
using the real network simulator and Node implementation.
"""
# autopep8: off
import threading
import time
import json
import socket
import pytest
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.improvedBully.node import Node, PORT_BASE, SIM_PORT
from src.networkSimulator import NetworkSimulator
from src.message import Message
# autopep8: on

# --- Utility helpers ---------------------------------------------------------


def wait_until(condition_fn, timeout=10, poll=0.5):
  """Waits until condition_fn() returns True or timeout occurs."""
  start = time.time()
  while time.time() - start < timeout:
    if condition_fn():
      return True
    time.sleep(poll)
  return False


def count_leaders(nodes):
  return sum(1 for n in nodes if n.isLeader)


def get_current_leader(nodes):
  # All alive nodes should agree on the same leader
  leaders = [n.leaderId for n in nodes if n.alive]
  assert all(l == leaders[0] for l in leaders), "Nodes disagree on the leader!"
  # Get the node object for the leader
  return get_node_by_id(nodes, leaders[0])


def get_node_by_id(nodes, node_id):
  """Helper to retrieve a node object by its ID."""
  return next((n for n in nodes if n.id == node_id), None)


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture(scope="module")
def network_simulator():
  """Start the network simulator once for all tests."""
  known_nodes = [1, 2, 3]
  sim = NetworkSimulator(known_nodes, minDelay=0.1, maxDelay=0.2)
  time.sleep(1)
  yield sim
  # Teardown
  sim.shutdown()


@pytest.fixture(scope="module")
def node_cluster(network_simulator):
  """Start a small cluster of nodes and yield them (IDs 1, 2, 3)."""
  known_nodes = [1, 2, 3]
  nodes = [Node(i, known_nodes) for i in known_nodes]
  time.sleep(3)

  # Ensure initial election completes before tests
  # Node 1 starts the initial election to establish Node 3 as leader
  nodes[0].startElection(nodes[0].knownNodes)
  assert wait_until(lambda: all(n.leaderId == 3 for n in nodes),
                    timeout=15), "Initial leader election failed to stabilize."

  yield nodes
  # Teardown: Stop all nodes
  for n in nodes:
    n.alive = False
    


# --- Tests -------------------------------------------------------------------


def test_initial_leader_election(node_cluster):
  """Ensure that a leader is correctly elected (Node 3) and all nodes agree."""
  nodes = node_cluster

  # Leader election was handled in the fixture, so we just verify the state
  assert count_leaders(nodes) == 1, "Expected exactly one leader."

  leader = get_current_leader(nodes)
  # FIX: Add assertion to check if leader is None before accessing its attributes
  assert leader is not None, "Leader is None, indicating unstable cluster state."

  #
  assert wait_until(lambda: all(n.leaderId == leader.id for n in nodes if not n.isLeader),
                    timeout=10, poll=1
                    ), "Not all nodes agree on the leader."
# -----------------------------------------------------------------------------------

  # Verification: Node 3 (highest ID) must win
  print(f"✅ Leader found: Node {leader.id}")

  assert leader.id == 3, f"Expected leader Node 3, but found Node {leader.id}"
  assert leader.isLeader


def test_leader_failure_and_reelection(node_cluster):
  """Verify that when the current leader (Node 3) fails, Node 2 is elected."""
  nodes = node_cluster
  
  # Get current leader (should be Node 3)
  leader = get_current_leader(nodes)
  assert leader is not None  # Should be true from fixture setup
  assert leader.id == 3

  print(f"💥 Simulating failure of leader Node {leader.id}")
  leader.fail()
  assert wait_until(lambda: not leader.alive, timeout=5), "Leader did not fail as expected."

  # Trigger failure detection from Node 1
  node_1 = get_node_by_id(nodes, 1)
  assert node_1 is not None
  print(f"⚠️ Simulating Node {node_1.id} detecting failure and starting election.")
  threading.Thread(target=node_1.sendAndWaitForReply, args=(leader.id, Message("REQUEST", node_1.id, leader.id)), daemon=True).start()
  assert wait_until(lambda: node_1.leaderId is None, timeout=10), "Node 1 did not detect leader failure."

  # Node 2 is the highest remaining ID and will attempt to become leader.
  # Wait for a new leader election
  assert wait_until(lambda: all(n.leaderId == 2 for n in nodes if n.alive), timeout=20), "New leader election failed to stabilize."

  new_leader = get_current_leader(nodes)
  assert new_leader is not None, "New leader is None, indicating unstable cluster state."

  print(f"✅ New leader after failure: Node {new_leader.id}")
  assert new_leader.id == 2, f"Expected leader Node 2, but found Node {new_leader.id}"
  assert new_leader.isLeader


def test_node_restart_triggers_election(node_cluster):
  """Restart a failed leader (Node 3) and verify it triggers a fresh election and wins."""
  nodes = node_cluster
  
  # Ensure Node 2 is the current leader from previous test
  interim_leader = get_current_leader(nodes)
  assert interim_leader is not None  # Should be true from fixture setup
  assert interim_leader.id == 2 # Ensure starting from known state
  
  node_3 = get_node_by_id(nodes, 3)
  assert node_3 is not None
  assert not node_3.alive, "Node 3 should be failed before restart test."
  
  print(f"🔄 Restarting Node {node_3.id}. Current Leader: Node {interim_leader.id}")
  node_3.restart()
  assert wait_until(lambda: node_3.alive, timeout=5), "Node 3 did not restart as expected."
  
  # The restart automatically calls startElection()
  # Wait for election triggered by restart to stabilize (Node 3 should win)
  assert wait_until(lambda: all(n.leaderId == 3 for n in nodes if n.alive), timeout=20), "Node 3 did not win election after restart."
  
  final_leader = get_current_leader(nodes)
  assert final_leader is not None, "Final leader is None, indicating unstable cluster state."
    
  print(f"✅ Final Leader after restart: Node {final_leader.id}")
  assert final_leader.id == 3
  assert final_leader.isLeader
  assert interim_leader.id == 2  # Check that the former leader 2 is no longer the leader
  assert interim_leader.isLeader == False

# --- End of File -------------------------------------------------------------