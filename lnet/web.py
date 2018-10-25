from flask import Flask, current_app, Response
from flask import g
from flask_jsonrpc import JSONRPC
import os
import dot_parser
import pydot
from concurrent.futures import ThreadPoolExecutor
from lnet.utils import BitcoinD, NodeFactory
import json
import time
import socket
from lightning.lightning import UnixDomainSocketRpc

app = Flask(__name__)
jsonrpc = JSONRPC(app, '/api', enable_web_browsable_api=True)


def start_bitcoind(directory):
    print("Starting")
    bitcoind = BitcoinD(bitcoin_dir=directory)
    try:
        bitcoind.start()
    except Exception:
        bitcoind.stop()
        raise

    info = bitcoind.rpc.getnetworkinfo()

    if info['version'] < 160000:
        bitcoind.rpc.stop()
        raise ValueError("bitcoind is too old. At least version 16000 (v0.16.0)"
                         " is needed, current version is {}".format(info['version']))

    info = bitcoind.rpc.getblockchaininfo()
    # Make sure we have some spendable funds
    if info['blocks'] < 101:
        bitcoind.generate_block(101 - info['blocks'])
    elif bitcoind.rpc.getwalletinfo()['balance'] < 1:
        logging.debug("Insufficient balance, generating 1 block")
        bitcoind.generate_block(1)

    return bitcoind



@jsonrpc.method('shutdown')
def shutdown():
    stop()
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return u'Bye'


def get_node_by_name(name):
    for n in current_app.node_factory.nodes:
        if n.name == name:
            return n
    return None


@jsonrpc.method('start')
def start(dotfile):
    if getattr(current_app, 'started', False):
        return "Already started"

    current_app.started = True
    
    print("Starting", dotfile)
    directory = os.path.join(os.path.dirname(__file__), "run")
    current_app.src = open(dotfile).read()
    dot = dot_parser.parse_dot_data(current_app.src)
    graph = pydot.graph_from_dot_file(dotfile)[0]

    assert(len(dot) == 1)
    dot = dot[0]
    
    nodes = []
    for e in dot.get_edges():
        points = e.obj_dict['points']
        nodes.append(points[0])
        nodes.append(points[1])

    # Deduplicate nodes
    nodes = set(nodes)
    
    current_app.directory = directory
    current_app.executor = ThreadPoolExecutor(max_workers=50)
    current_app.bitcoind = start_bitcoind(directory)
    current_app.node_factory = NodeFactory(current_app.bitcoind, current_app.executor, current_app.directory)
    ex = current_app.executor
    nf = current_app.node_factory
    for n in nodes:
        print("Starting {}".format(n))
        current_app.node_factory.get_node(name=n, may_reconnect=True)

    def channel_confirming(src, dst):
        peers = src.rpc.listpeers(dst.info['id'])['peers']
        if not peers:
            return False

        peer = peers[0]
        if len(peer['channels']) != 1:
            return False

        channel = peer['channels'][0]
        if channel['state'] != 'CHANNELD_AWAITING_LOCKIN':
            return False
        return True
        
    for e in dot.get_edges():
        points = e.obj_dict['points']
        print("Connecting {} <-> {}".format(*points))
        src = get_node_by_name(points[0])
        dst = get_node_by_name(points[1])
        assert(src and dst)

        attrs = e.get_attributes()
        e.capacities = get_edge_capacity(attrs)
        ex.submit(src.openchannel, dst, connect=True, capacity=sum(e.capacities), announce=False, confirm=False)

    for e in graph.get_edges():
        points = e.obj_dict['points']
        src = get_node_by_name(points[0])
        dst = get_node_by_name(points[1])
        while not channel_confirming(src, dst):
            time.sleep(0.1)

    current_app.bitcoind.rpc.generate(6)
    print('Waiting for gossip to propagate')
    while True:
        count = sum([len(n.rpc.listnodes()['nodes']) for n in nf.nodes])
        expected = len(nf.nodes)**2
        
        if expected == count:
            break
        print("Gossip progress {:2f}%".format(100*count/expected))
        time.sleep(1)

    print("Rebalancing channels")
    for e in graph.get_edges():
        attrs = e.get_attributes()
        caps = get_edge_capacity(attrs)
        if caps[1] == 0:
            continue
        points = e.obj_dict['points']
        print("Rebalancing {} --{}-> {}".format(points[0], caps[1], points[1]))
        src = get_node_by_name(points[0])
        dst = get_node_by_name(points[1])
        bolt11 = dst.rpc.invoice(caps[1], 'rebalance-{}-{}'.format(*points), "Rebalancing")['bolt11']
        src.rpc.pay(bolt11)
    
    return {'dot': current_app.src, 'nodes': list(nodes)}


def get_edge_capacity(attrs):
    if 'capacity' not in attrs:
        return (10**6, 0)

    cap = attrs['capacity'].replace('"', '').replace('\'', '')
    if ':' in cap:
        return [int(s) for s in cap.split(':')]
    else:
        return (int(cap), 0)

    
@jsonrpc.method('node_rpc')
def node_rpc(node_name, method, params):
    print("Calling {} on {} with params {}".format(method, node_name, params))
    node = get_node_by_name(node_name)
    if not node:
        raise ValueError("No node with the given name")

    rpc = UnixDomainSocketRpc(node.rpc.socket_path)
    
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(node.rpc.socket_path)
    UnixDomainSocketRpc._writeobj(sock, {
        "method": method,
        "params": params,
        "id": 0
    })
    resp = UnixDomainSocketRpc._readobj(rpc, sock)
    sock.close()
    if "error" in resp:
        raise ValueError(resp['error'])
    elif "result" not in resp:
        raise ValueError("Malformed response, \"result\" missing.")
    return resp["result"]


@jsonrpc.method('alias')
def alias():
    return {n.name: os.path.dirname(n.rpc.socket_path) for n in current_app.node_factory.nodes}


@jsonrpc.method('stop')
def stop():
    if not getattr(current_app, 'started', False):
        return "Not started"

    print("Stopping nodes")
    nf = current_app.node_factory
    nf.stop(1)
    print("Stopping bitcoind")
    current_app.bitcoind.stop()
    print("Stopping executor")
    current_app.executor.shutdown(wait=False)
    current_app.started = False

@app.route("/")
def hello():
    return "Hello World!"


@app.route("/net")
def net():
    graph = pydot.graph_from_dot_data(current_app.src)
    assert(len(graph) == 1)
    graph = graph[0]
    graph.write_svg('/tmp/net.svg')
    return open('/tmp/net.svg', 'r').read()


@app.route("/<nodename>/getinfo")
def getinfo(nodename):
    nf = current_app.node_factory

    # Find the node with that name
    for n in nf.nodes:
        if n.name == nodename:
            break

    if n.name != nodename:
        return "No node with that name found"

    return Response(json.dumps(n.rpc.getinfo()), mimetype='text/plain')


def register(bitcoind, node_factory):
    g.bitcoind = bitcoind
    g.node_factory = node_factory


from flask import request

def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

    
@app.route('/shutdown', methods=['POST'])
def shutdown():
    shutdown_server()
    return 'Server shutting down...'

