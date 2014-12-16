#!/usr/bin/env python3
import argparse
import sys
import time

from struct import unpack
from random import random
from ctypes import c_int
from collections import defaultdict

from math import ceil
import lt_sampler
 
#TODO: program output at termination to mirror TA binary


#FIXME: convert to namedtuple
class CheckNode(object):

    def __init__(self, src_nodes, check):
        self.check = check
        self.src_nodes = src_nodes

class BlockGraph(object):
    
    def __init__(self, num_blocks):
        self.checks = defaultdict(list)
        self.num_blocks = num_blocks
        self.eliminated = {}

    def add_block(self, nodes, data):
        
        if len(nodes) == 1:
            to_eliminate = list(self.eliminate(next(iter(nodes)), data))
            while len(to_eliminate):
                other, check = to_eliminate.pop()
                to_eliminate.extend(self.eliminate(other, check))
        else:
            for node in list(nodes):
                if node in self.eliminated:
                    nodes.remove(node)
                    data ^= self.eliminated[node]
            if len(nodes) == 1:
                return self.add_block(nodes, data)
            else:
                check = CheckNode(nodes, data)
                for node in nodes:
                    self.checks[node].append(check)
        return len(self.eliminated) >= self.num_blocks

    def eliminate(self, node, data):
        self.eliminated[node] = data
        others = self.checks[node]
        del self.checks[node]
        for check in others:
            check.check ^= data
            check.src_nodes.remove(node)
            if len(check.src_nodes) == 1:
                yield (next(iter(check.src_nodes)), check.check)

def read_header(stream):
    header_bytes = stream.read(12)
    return unpack('!III', header_bytes)

def read_block(blocksize, stream):
    blockdata = stream.read(blocksize)
    return int.from_bytes(blockdata, 'big')

def read_blocks(stream, drop_rate):
    while True:
        header = read_header(stream)
        block  = read_block(header[1], stream)
        yield (header, block)

def handle_block(src_blocks, block, block_graph):
    return block_graph.add_block(src_blocks, block)

def decode(drop_rate, stream=sys.stdin.buffer):

    # init stuff
    time_start = time.time()
    total_size = 0

    # data structures
    block_graph = None
    prng = None

    # counters
    blocks_received, blocks_dropped = 0, 0
    bytes_received = 0

    # Begin forever loop
    for (filesize, blocksize, blockseed), block in read_blocks(stream, drop_rate):

        # drop some packets
        if random() < drop_rate:
            blocks_dropped  += 1
            continue

        blocks_received += 1
        bytes_received += blocksize

        # first time around
        if not prng:
            total_size = filesize

            K = ceil(filesize/blocksize)
            prng = lt_sampler.PRNG(params=(K, lt_sampler.PRNG_DELTA, lt_sampler.PRNG_C))
            block_graph = BlockGraph(K)

        _, _, src_blocks = prng.get_src_blocks(seed=blockseed)

        # If BP is done, stop
        if handle_block(src_blocks, block, block_graph):
            break
    
    # Stop the timer
    time_end = time.time()

    # Iterate through blocks, stopping before padding junk
    for ix, block_str in enumerate(map(lambda p: int.to_bytes(p[1], blocksize, 'big').decode('utf8'), 
            sorted(block_graph.eliminated.items(), key = lambda p:p[0]))):
        if ix < K-1:
            sys.stdout.write(block_str)
        else:
            sys.stdout.write(block_str[:filesize%blocksize])

    # Compute some stats
    time_elapsed = (time_end - time_start) * 1000
    
    #NOTE: summary stats break when blocks are of different sizes
    rate = total_size / bytes_received
    # Report summary stats on transmission 
    if time_elapsed > 1000:
        print("Transmission Time: %.4fs" % (time_elapsed / 1000), file=sys.stderr)
    else:
        print("Transmission Time: %.4fms" % time_elapsed, file=sys.stderr)
    print("Total size:        %d" % total_size, file=sys.stderr)
    print("Packet Stats:", file=sys.stderr)
    print("\tPackets Received:  %d" % (blocks_received + blocks_dropped), file=sys.stderr)
    print("\tPackets Processed: %d" % blocks_received, file=sys.stderr)
    print("\tPackets Dropped:   %d" % blocks_dropped, file=sys.stderr)
    print("Data Stats", file=sys.stderr)
    print("\tBytes/packet: %d" % (bytes_received / blocks_received) , file=sys.stderr)
    print("\tBytes Total:  %d" % bytes_received, file=sys.stderr)
    print("Code Rate: %1.4f" % rate, file=sys.stderr)
       

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('drop_rate', type=float,
                                     help='the probability of a transmitted block being dropped')
    args = parser.parse_args()
    decode(args.drop_rate)